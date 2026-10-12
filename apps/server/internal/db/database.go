package db

import (
	"database/sql"
	"fmt"
	"log"
	"net/url"
	"strings"

	_ "github.com/microsoft/go-mssqldb"
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
	"stk_inventory":         "FMATERIALID,FSTOCKID",
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

	// SQL Server uses go-mssqldb driver
	// （原因：同步目标为 SQL Server，使用 MERGE 写入）
	driverName := "sqlserver"
	user := url.QueryEscape(dbCfg.User)
	password := url.QueryEscape(dbCfg.Password)
	dsn := fmt.Sprintf("sqlserver://%s:%s@%s:%d?database=%s&encrypt=disable&TrustServerCertificate=true",
		user, password, dbCfg.Host, dbCfg.Port, dbCfg.DBName)

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
	// go-mssqldb 仅识别 @pN 命名参数，`?` 会原样透传给 SQL Server 导致语法错误
	rows, err := DB.Queryx(`
		SELECT COLUMN_NAME
		FROM INFORMATION_SCHEMA.COLUMNS
		WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = @p1
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
	// go-mssqldb 仅识别 @pN 命名参数，`?` 会原样透传给 SQL Server 导致语法错误
	rows, err := DB.Queryx(`
		SELECT c.COLUMN_NAME
			FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tk
			JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE c
				ON tk.TABLE_SCHEMA = c.TABLE_SCHEMA
				AND tk.TABLE_NAME = c.TABLE_NAME
				AND tk.CONSTRAINT_NAME = c.CONSTRAINT_NAME
			WHERE tk.TABLE_SCHEMA = 'dbo'
				AND tk.TABLE_NAME = @p1
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
// For SQL Server, reads from SYNC_TIME column.
func GetLastSyncTime(tableName string) (string, error) {
	if DB == nil {
		return "", fmt.Errorf("database not initialized")
	}
	// 表名拼接进 SELECT，入口校验（原因：防注入纵深防御）
	if err := config.ValidateSQLIdentifier(tableName); err != nil {
		return "", err
	}

	syncTimeCol := "SYNC_TIME"

	var lastTime sql.NullString
	query := fmt.Sprintf("SELECT CONVERT(varchar(19), MAX(%s), 120) FROM dbo.%s", syncTimeCol, tableName)
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
