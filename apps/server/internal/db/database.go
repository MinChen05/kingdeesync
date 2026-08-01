package db

import (
	"database/sql"
	"fmt"
	"log"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	"github.com/jmoiron/sqlx"
	"github.com/kingdee-sync/go/internal/config"
)

var DB *sqlx.DB

// PK mapping mirrors the versioned MSSQL business-key contract.
var primaryKeyMap = map[string]string{
	"ap_payable":            "FID,FENTRYID",
	"ar_receivable":         "FID,FENTRYID",
	"bd_material":           "FNUMBER",
	"bd_stock":              "FSTOCKID",
	"customer":              "FNUMBER",
	"eng_bom":               "FID",
	"eng_bomchild":          "FID,FENTRYID",
	"gl_rpt_accountbalance": "FBALANCEID",
	"pln_forecast":          "FENTRYID",
	"prd_instock":           "FID,FENTRYID",
	"prd_mo":                "FID",
	"prd_moentry":           "FID,FENTRYID",
	"prd_ppbom":             "FID",
	"prd_ppbomentry":        "FID,FENTRYID",
	"pur_purchaseorder":     "FID,FENTRYID",
	"sal_deliverynotice":    "FID,FENTRYID",
	"sal_outstock":          "FENTRYID",
	"sal_returnstock":       "FENTRYID",
	"saleorder":             "FID,FENTRYID",
	"stk_instock":           "FID,FENTRYID",
	"stk_inventory":         "FID",
	"sub_subreqorder":       "FID,FENTRYID",
}

func Init() error {
	cfg := config.Get()
	if cfg == nil {
		return fmt.Errorf("config not loaded")
	}

	dbCfg := cfg.GetEffectiveDatabase()

	log.Printf("[DB] Effective config: type=%s, host=%s, port=%d, user=%s, db=%s, password_len=%d",
		dbCfg.Type, dbCfg.Host, dbCfg.Port, dbCfg.User, dbCfg.DBName, len(dbCfg.Password))

	// Doris uses MySQL protocol, so we connect with the mysql driver.
	// （原因：已移除 SQL Server 支持，Go 后端仅对接 Doris/MySQL）
	driverName := "mysql"
	dsn := fmt.Sprintf(
		"%s:%s@tcp(%s:%d)/%s?parseTime=true&loc=Local&charset=utf8mb4",
		dbCfg.User,
		dbCfg.Password,
		dbCfg.Host,
		dbCfg.Port,
		dbCfg.DBName,
	)

	sqlDB, err := OpenDB(driverName, dsn)
	if err != nil {
		return err
	}

	DB = sqlx.NewDb(sqlDB, driverName)
	log.Printf("Database connected: %s://%s:%d/%s", dbCfg.Type, dbCfg.Host, dbCfg.Port, dbCfg.DBName)
	return nil
}

func OpenDB(driverName, dsn string) (*sql.DB, error) {
	sqlDB, err := sql.Open(driverName, dsn)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	if err := sqlDB.Ping(); err != nil {
		sqlDB.Close()
		return nil, fmt.Errorf("ping database: %w", err)
	}
	sqlDB.SetMaxOpenConns(20)
	sqlDB.SetMaxIdleConns(5)
	return sqlDB, nil
}

func Close() {
	if DB != nil {
		DB.Close()
	}
}

// GetPrimaryKey returns the PK column(s) for a table, mirroring Python logic.
// Composite keys are returned comma-separated, e.g. "FID,FENTRYID".
func GetPrimaryKey(tableName string) string {
	key, ok := primaryKeyMap[strings.ToLower(strings.TrimSpace(tableName))]
	if ok {
		return key
	}
	// Fallback: try to read from DB metadata
	if DB != nil {
		if pk, err := getPrimaryKeyFromDB(tableName); err == nil && pk != "" {
			return pk
		}
	}
	// Last resort: first column
	return ""
}

// GetTableColumns returns uppercased column names mapped to their stored names.
// Window validation uses this metadata to preserve the same field mapping as the
// normal synchronization engine.
func GetTableColumns(tableName string) (map[string]string, error) {
	if DB == nil {
		return nil, fmt.Errorf("database not initialized")
	}
	rows, err := DB.Queryx(`
		SELECT COLUMN_NAME
		FROM INFORMATION_SCHEMA.COLUMNS
		WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?
		ORDER BY ORDINAL_POSITION
	`, tableName)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	columns := make(map[string]string)
	for rows.Next() {
		var column string
		if err := rows.Scan(&column); err != nil {
			return nil, err
		}
		columns[strings.ToUpper(column)] = column
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(columns) == 0 {
		return nil, fmt.Errorf("no columns found for table %s", tableName)
	}
	return columns, nil
}

func getPrimaryKeyFromDB(tableName string) (string, error) {
	var cols []string
	rows, err := DB.Queryx(`
		SELECT c.COLUMN_NAME
			FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tk
			JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c
				ON tk.TABLE_SCHEMA = c.TABLE_SCHEMA
				AND tk.TABLE_NAME = c.TABLE_NAME
				AND tk.CONSTRAINT_NAME = c.CONSTRAINT_NAME
			WHERE tk.TABLE_SCHEMA = DATABASE()
				AND tk.TABLE_NAME = ?
				AND tk.CONSTRAINT_TYPE = 'PRIMARY KEY'
			ORDER BY c.ORDINAL_POSITION
		`, tableName)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	for rows.Next() {
		var col string
		if err := rows.Scan(&col); err != nil {
			return "", err
		}
		cols = append(cols, col)
	}
	if rows.Err() != nil {
		return "", rows.Err()
	}
	if len(cols) == 0 {
		return "", fmt.Errorf("no primary key found for %s", tableName)
	}
	return strings.Join(cols, ","), nil
}

// GetLastSyncTime returns the maximum sync time from a table, used for incremental sync.
// For Doris (mysql type), reads from _sync_time column.
// Returns "YYYY-MM-DD HH:MM:SS" format for Kingdee API filter compatibility.
// （原因：按数据库类型动态选择列名，Doris 用 _sync_time；格式需与金蝶 API 兼容）
func GetLastSyncTime(tableName string) (string, error) {
	if DB == nil {
		return "", fmt.Errorf("database not initialized")
	}

	// Doris uses SYNC_TIME column (as defined in DDL).
	syncTimeCol := "SYNC_TIME"

	// Use DATE_FORMAT to ensure consistent output format regardless of driver behavior.
	var lastTime sql.NullString
	query := fmt.Sprintf("SELECT DATE_FORMAT(MAX(%s), '%%Y-%%m-%%d %%H:%%i:%%s') FROM `%s`", syncTimeCol, tableName)
	err := DB.Get(&lastTime, query)
	if err != nil {
		return "", err
	}
	if !lastTime.Valid {
		return "", nil
	}

	t := lastTime.String
	// Fallback cleanup: remove timezone and microseconds if present.
	t = strings.ReplaceAll(t, "T", " ")
	t = strings.TrimSuffix(t, "Z")
	if idx := strings.Index(t, "."); idx != -1 {
		t = t[:idx]
	}
	// Remove timezone offset like +08:00
	if idx := strings.Index(t, "+"); idx != -1 {
		t = t[:idx]
	}
	return t, nil
}
