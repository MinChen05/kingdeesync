package syncengine

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"log"
	"math"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jmoiron/sqlx"
	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
)

// SQLServerWriter writes data to SQL Server using staging tables + MERGE.
// Aligned with the Python upsert_engine_sqlserver.py logic.
type SQLServerWriter struct {
	cfg config.DatabaseConfig
}

func NewSQLServerWriter() *SQLServerWriter {
	cfg := config.Get()
	var dbCfg config.DatabaseConfig
	if cfg != nil {
		dbCfg = cfg.GetEffectiveDatabase()
	}
	return &SQLServerWriter{cfg: dbCfg}
}

func (w *SQLServerWriter) Upsert(ctx context.Context, tableName string, rows []map[string]interface{},
	cols []string, pkCols []string, fieldMap map[string]string) (UpsertResult, error) {

	if len(rows) == 0 {
		return UpsertResult{}, nil
	}
	// 纵深防御：表名与列名会拼接进 MERGE/暂存表 SQL，入口统一校验
	// （原因：防任意表单名经映射后透传注入）
	if err := config.ValidateSQLIdentifier(tableName); err != nil {
		return UpsertResult{}, err
	}
	for _, cols := range [][]string{cols, pkCols} {
		for _, col := range cols {
			if err := config.ValidateSQLIdentifier(col); err != nil {
				return UpsertResult{}, err
			}
		}
	}
	if ctx == nil {
		ctx = context.Background()
	}

	if db.DB == nil {
		return UpsertResult{}, fmt.Errorf("database not initialized")
	}

	// 为 SYNC_TIME 审计列注入写入时刻（原因：该列不来自金蝶字段，行数据中不存在，
	// 不注入则 staging 装载取到 NULL，MERGE 的 ISNULL 语义会保留旧值不刷新）
	injectSyncTime(rows, cols)

	// Check if this is a force-staging table
	forceStaging := w.isForceStagingTable(tableName)

	// For small datasets or non-staging tables, use direct upsert
	if !forceStaging && len(rows) < 5000 {
		return w.directUpsert(ctx, tableName, rows, cols, pkCols, fieldMap)
	}

	// Use staging + MERGE for large datasets
	return w.stagingUpsert(ctx, tableName, rows, cols, pkCols, fieldMap)
}

func (w *SQLServerWriter) stagingUpsert(ctx context.Context, tableName string, rows []map[string]interface{},
	cols []string, pkCols []string, fieldMap map[string]string) (UpsertResult, error) {

	sqlDB := db.DB
	hash := sha256.Sum256([]byte(tableName + uuid.New().String()))
	stagingTable := "stg_" + hex.EncodeToString(hash[:8])

	defer func() {
		_, _ = sqlDB.ExecContext(ctx, fmt.Sprintf("IF OBJECT_ID(N'dbo.%s', 'U') IS NOT NULL DROP TABLE dbo.%s", stagingTable, stagingTable))
	}()

	// Build staging table DDL from target table structure.
	// Clustered index on PK columns is declared inline in CREATE TABLE,
	// so the data is inserted in key order and the later MERGE join is fast
	// — no separate CREATE INDEX round trip needed.
	// （原因：内联 CLUSTERED INDEX 一步完成建表+索引，省一次 DDL 往返）
	if err := w.createStagingTable(ctx, sqlDB, tableName, stagingTable, cols, pkCols); err != nil {
		return UpsertResult{}, fmt.Errorf("create staging table %s: %w", stagingTable, err)
	}

	// Batch insert into staging table
	stagingRows, err := w.batchInsertStaging(ctx, sqlDB, stagingTable, rows, cols, fieldMap)
	if err != nil {
		return UpsertResult{}, fmt.Errorf("batch insert staging %s: %w", stagingTable, err)
	}

	// Count PKs that already exist in the target BEFORE the MERGE, to split
	// inserted vs updated. After the MERGE every staged PK exists in the target,
	// so counting then would report all rows as "updated" (inserted stuck at 0).
	// （原因：MERGE 后所有 PK 都已存在于目标表，必须在 MERGE 前统计已有 PK 才能得到正确的 inserted/updated 拆分）
	updateEstimate := 0
	if len(pkCols) > 0 && stagingRows > 0 {
		pkConds := make([]string, len(pkCols))
		for i, pk := range pkCols {
			pkConds[i] = fmt.Sprintf("target.[%s] = source.[%s]", pk, pk)
		}
		countSQL := fmt.Sprintf(
			"SELECT COUNT(*) FROM dbo.%s AS target INNER JOIN dbo.%s AS source ON %s",
			tableName, stagingTable, strings.Join(pkConds, " AND "),
		)
		var count int
		if err := sqlDB.GetContext(ctx, &count, countSQL); err == nil {
			updateEstimate = count
		}
	}

	// Build and execute MERGE statement
	mergeSQL, args := w.buildMergeSQL(tableName, stagingTable, cols, pkCols)
	if mergeSQL == "" {
		return UpsertResult{}, fmt.Errorf("cannot build MERGE for %s (no PK columns)", tableName)
	}

	tx, err := sqlDB.BeginTxx(ctx, nil)
	if err != nil {
		return UpsertResult{}, fmt.Errorf("begin transaction: %w", err)
	}
	defer func() {
		if err != nil {
			tx.Rollback()
		}
	}()

	result, err := tx.ExecContext(ctx, mergeSQL, args...)
	if err != nil {
		return UpsertResult{}, fmt.Errorf("execute MERGE for %s: %w", tableName, err)
	}

	if err := tx.Commit(); err != nil {
		return UpsertResult{}, fmt.Errorf("commit MERGE for %s: %w", tableName, err)
	}

	affected, _ := result.RowsAffected()
	log.Printf("[SQLSERVER-MERGE] %s: merged %d rows via staging %s", tableName, affected, stagingTable)
	inserted := stagingRows - updateEstimate
	if inserted < 0 {
		inserted = 0
	}
	return UpsertResult{Inserted: inserted, Updated: updateEstimate, Total: stagingRows}, nil
}

func (w *SQLServerWriter) directUpsert(ctx context.Context, tableName string, rows []map[string]interface{},
	cols []string, pkCols []string, fieldMap map[string]string) (UpsertResult, error) {

	if db.DB == nil {
		return UpsertResult{}, fmt.Errorf("database not initialized")
	}

	// Build reverse field map
	colToKingdee := make(map[string][]string)
	for kField, dbCol := range fieldMap {
		colToKingdee[strings.ToUpper(dbCol)] = append(colToKingdee[strings.ToUpper(dbCol)], kField)
	}

// Direct upsert without staging table: MERGE ... USING (VALUES ...)
		// with @pN named parameters (go-mssqldb rejects "?").
		// （原因：小批量直接写目标表，避免 staging 建表开销；@pN 是 mssql 唯一支持的占位符）
		totalInserted := 0
		totalUpdated := 0
	// SQL Server caps parameters at 2100, so at most 100 rows per batch.
	const batchRows = 100

	for start := 0; start < len(rows); start += batchRows {
		end := start + batchRows
		if end > len(rows) {
			end = len(rows)
		}
		batch := rows[start:end]

		// Normalize values per row
		normalized := make([][]interface{}, len(batch))
		for i, row := range batch {
			vals := make([]interface{}, len(cols))
			for j, col := range cols {
				v := w.lookupValue(row, col, colToKingdee)
				v = normalizeValue(v)
				if v == nil {
					v = ""
				}
				vals[j] = v
			}
			normalized[i] = vals
		}

		// Build MERGE with VALUES source: (@p1,@p2,...),(...),...
		colList := "[" + strings.Join(cols, "], [") + "]"
		var builder strings.Builder
		builder.WriteString("MERGE INTO dbo.")
		builder.WriteString(tableName)
		builder.WriteString(" AS target USING (VALUES ")
		paramIndex := 0
		for i := range normalized {
			if i > 0 {
				builder.WriteString(",")
			}
			builder.WriteString("(")
			for j := range cols {
				if j > 0 {
					builder.WriteString(",")
				}
				paramIndex++
				builder.WriteString(fmt.Sprintf("@p%d", paramIndex))
			}
			builder.WriteString(")")
		}
		builder.WriteString(") AS source (")
		builder.WriteString(colList)
		builder.WriteString(") ON ")
		for i, pk := range pkCols {
			if i > 0 {
				builder.WriteString(" AND ")
			}
			builder.WriteString("target.[")
			builder.WriteString(pk)
			builder.WriteString("] = source.[")
			builder.WriteString(pk)
			builder.WriteString("]")
		}
		builder.WriteString(" WHEN MATCHED THEN UPDATE SET ")
		updateParts := make([]string, 0, len(cols))
		for _, c := range cols {
			isPK := false
			for _, pk := range pkCols {
				if pk == c {
					isPK = true
					break
				}
			}
			if !isPK {
				// ISNULL prevents NULL from overwriting NOT NULL columns
				updateParts = append(updateParts, fmt.Sprintf("target.[%s] = ISNULL(source.[%s], target.[%s])", c, c, c))
			}
		}
		builder.WriteString(strings.Join(updateParts, ", "))
		builder.WriteString(" WHEN NOT MATCHED THEN INSERT (")
		builder.WriteString(colList)
		builder.WriteString(") VALUES (")
		// source column refs: source.[col]
		srcRefs := make([]string, len(cols))
		for i, c := range cols {
			srcRefs[i] = "source.[" + c + "]"
		}
		builder.WriteString(strings.Join(srcRefs, ", "))
		builder.WriteString(");")

		args := make([]interface{}, 0, len(normalized)*len(cols))
		for _, vals := range normalized {
			args = append(args, vals...)
		}

result, err := db.DB.ExecContext(ctx, builder.String(), args...)
			if err != nil {
				return UpsertResult{}, fmt.Errorf("direct MERGE for %s: %w", tableName, err)
			}
			affected, _ := result.RowsAffected()
			// For direct MERGE, estimate updated rows by checking PK overlap before this batch.
			// Simple heuristic: count PKs in target that match this batch.
			batchInserted := len(batch)
			if len(pkCols) > 0 && affected > 0 {
				// Build IN clause for first PK column values from this batch
				firstPk := pkCols[0]
				var pkVals []interface{}
				var pkPlaceholders []string
				for _, row := range batch {
					v := w.lookupValue(row, firstPk, colToKingdee)
					pkVals = append(pkVals, v)
					pkPlaceholders = append(pkPlaceholders, "@p"+fmt.Sprint(len(pkVals)))
				}
				countSQL := fmt.Sprintf("SELECT COUNT(*) FROM dbo.%s WHERE [%s] IN (%s)",
					tableName, firstPk, strings.Join(pkPlaceholders, ", "))
				var existingCount int
				if err := db.DB.GetContext(ctx, &existingCount, countSQL, pkVals...); err == nil {
					totalUpdated += existingCount
					batchInserted = len(batch) - existingCount
					if batchInserted < 0 {
						batchInserted = 0
					}
				}
			}
			totalInserted += batchInserted
		}

		return UpsertResult{Inserted: totalInserted, Updated: totalUpdated, Total: len(rows)}, nil
}

func (w *SQLServerWriter) createStagingTable(ctx context.Context, sqlDB *sqlx.DB,
	tableName, stagingTable string, cols []string, pkCols []string) error {

	// Get column types from target table
	// 表名参数绑定必须用 @p1 命名参数——go-mssqldb 不认 "?" 占位符，
	// 会原样透传导致"?'附近有语法错误"（与 orphan_reconcile.go createSourceKeyStaging 一致）。
	// （原因：mssql 路径无单测覆盖，此坑曾以生产 staging 建表失败暴露）
	rows, err := sqlDB.QueryxContext(ctx, `
		SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
		FROM INFORMATION_SCHEMA.COLUMNS
		WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = @p1
		ORDER BY ORDINAL_POSITION
	`, tableName)
	if err != nil {
		return fmt.Errorf("query column types for %s: %w", tableName, err)
	}
	defer rows.Close()

	colTypes := make(map[string]string)
	for rows.Next() {
		var colName, dataType string
		var maxLen sql.NullInt64
		var precision, scale sql.NullInt64
		if err := rows.Scan(&colName, &dataType, &maxLen, &precision, &scale); err != nil {
			continue
		}
		tsqlType := w.mapDataType(dataType, maxLen, precision, scale)
		colTypes[strings.ToUpper(colName)] = tsqlType
	}

	// Build column definitions for staging table — all columns nullable
	// so NOT NULL constraints in the target table don't block staging inserts.
	// （原因：直接在 DDL 声明 NULL，避免 SELECT * INTO 后再逐列 ALTER 的 19 次 DDL 往返）
	var colDefs []string
	for _, col := range cols {
		tsqlType, ok := colTypes[strings.ToUpper(col)]
		if !ok {
			tsqlType = "NVARCHAR(500)"
		}
		colDefs = append(colDefs, fmt.Sprintf("[%s] %s NULL", col, tsqlType))
	}

	// Inline CLUSTERED INDEX on the PK columns: one DDL statement builds the
	// table and orders it by the merge key, so the later MERGE join against
	// the large target table uses ordered seeks. Nullable key columns are fine
	// for a non-unique clustered index.
	// （原因：合并建表+聚集索引为一条语句，省一次独立 CREATE INDEX 往返；
	// 对齐 Python _maybe_create_stage_index 的索引收益）
	indexDef := ""
	if len(pkCols) > 0 {
		quoted := make([]string, len(pkCols))
		for i, pk := range pkCols {
			quoted[i] = "[" + pk + "]"
		}
		indexDef = fmt.Sprintf(", INDEX [IX_%s] CLUSTERED (%s)", stagingTable, strings.Join(quoted, ", "))
	}

	// CREATE TABLE with explicit nullable columns (fast path vs SELECT INTO + ALTER)
	createSQL := fmt.Sprintf(
		"CREATE TABLE dbo.%s (%s%s)",
		stagingTable, strings.Join(colDefs, ", "), indexDef,
	)
	_, err = sqlDB.ExecContext(ctx, createSQL)
	if err != nil {
		return fmt.Errorf("create staging table via CREATE TABLE: %w", err)
	}
	return nil
}

func (w *SQLServerWriter) batchInsertStaging(ctx context.Context, sqlDB *sqlx.DB,
	stagingTable string, rows []map[string]interface{}, cols []string, fieldMap map[string]string) (int, error) {

	colToKingdee := make(map[string][]string)
	for kField, dbCol := range fieldMap {
		colToKingdee[strings.ToUpper(dbCol)] = append(colToKingdee[strings.ToUpper(dbCol)], kField)
	}

	// Batch insert using VALUES text constructor.
	// Parameterized @pN inserts were 10x slower (100 round trips vs 10 for
	// the same 10000 rows), so we keep VALUES text which batches 1000 rows.
	// （原因：实测 100 批参数化比 10 批 VALUES 文本慢约 10 倍）
	const batchSize = 1000 // SQL Server VALUES constructor caps at 1000 rows per statement
	total := 0

	colList := "[" + strings.Join(cols, "], [") + "]"

	for start := 0; start < len(rows); start += batchSize {
		end := start + batchSize
		if end > len(rows) {
			end = len(rows)
		}
		batch := rows[start:end]

		// Build VALUES using table-value constructor with escaped literals
		var builder strings.Builder
		builder.WriteString("INSERT INTO dbo.")
		builder.WriteString(stagingTable)
		builder.WriteString(" (")
		builder.WriteString(colList)
		builder.WriteString(") VALUES ")
		for i, row := range batch {
			if i > 0 {
				builder.WriteString(",")
			}
			builder.WriteString("(")
			for j, col := range cols {
				if j > 0 {
					builder.WriteString(",")
				}
				v := w.lookupValue(row, col, colToKingdee)
				v = normalizeValue(v)
				// Replace nil with empty string to avoid NOT NULL constraint errors
				if v == nil {
					v = ""
				}
				builder.WriteString(w.sqlLiteral(v))
			}
			builder.WriteString(")")
		}

		_, err := sqlDB.ExecContext(ctx, builder.String())
		if err != nil {
			return total, fmt.Errorf("batch insert into staging %s: %w", stagingTable, err)
		}
		total += len(batch)
	}

	return total, nil
}

// sqlLiteral renders a Go value as a SQL Server literal for VALUES text inserts.
func (w *SQLServerWriter) sqlLiteral(v interface{}) string {
	switch val := v.(type) {
	case string:
		escaped := strings.ReplaceAll(val, "'", "''")
		return fmt.Sprintf("N'%s'", escaped)
	case int64:
		return fmt.Sprintf("%d", val)
	case float64:
		if math.IsNaN(val) || math.IsInf(val, 0) {
			return "NULL"
		}
		return fmt.Sprintf("%v", val)
	case bool:
		if val {
			return "1"
		}
		return "0"
	case time.Time:
		return fmt.Sprintf("'%s'", val.Format("2006-01-02 15:04:05"))
	default:
		s := fmt.Sprintf("%v", val)
		escaped := strings.ReplaceAll(s, "'", "''")
		return fmt.Sprintf("N'%s'", escaped)
	}
}

func (w *SQLServerWriter) createStagingIndex(ctx context.Context, sqlDB *sqlx.DB,
	stagingTable string, pkCols []string, rowCount int) {

	if rowCount < 1000 || len(pkCols) == 0 {
		return
	}
	// Cap index columns at 3, aligned with stage_index_max_columns config.
	cols := pkCols
	if len(cols) > 3 {
		cols = cols[:3]
	}
	quoted := make([]string, len(cols))
	for i, c := range cols {
		quoted[i] = "[" + c + "]"
	}
	// stagingTable name is unique per call (random hash), so the index name is unique too.
	idxName := "IX_STAGE_" + stagingTable
	createSQL := fmt.Sprintf("CREATE CLUSTERED INDEX [%s] ON dbo.%s (%s)",
		idxName, stagingTable, strings.Join(quoted, ", "))
	if _, err := sqlDB.ExecContext(ctx, createSQL); err != nil {
		log.Printf("[SQLSERVER-STAGING] Failed to create clustered index on %s: %v", stagingTable, err)
		return
	}
	log.Printf("[SQLSERVER-STAGING] Created clustered index %s on %s (%s)", idxName, stagingTable, strings.Join(cols, ","))
}

func (w *SQLServerWriter) buildMergeSQL(tableName, stagingTable string,
	cols []string, pkCols []string) (string, []interface{}) {

	if len(pkCols) == 0 {
		// Fallback: INSERT OR IGNORE (no PK to match)
		insertCols := make([]string, len(cols))
		for i, c := range cols {
			insertCols[i] = fmt.Sprintf("[%s]", c)
		}
		sql := fmt.Sprintf(
			"INSERT INTO dbo.%s (%s) SELECT %s FROM dbo.%s",
			tableName, strings.Join(insertCols, ", "),
			strings.Join(insertCols, ", "), stagingTable,
		)
		return sql, nil
	}

	// Build MERGE statement
	matchConditions := make([]string, len(pkCols))
	for i, pk := range pkCols {
		matchConditions[i] = fmt.Sprintf("target.[%s] = source.[%s]", pk, pk)
	}

updateSet := make([]string, len(cols))
		for i, c := range cols {
			// Skip PK columns in UPDATE
			isPK := false
			for _, pk := range pkCols {
				if pk == c {
					isPK = true
					break
				}
			}
			if !isPK {
				// Use ISNULL to prevent NULL being written to NOT NULL columns
				// （原因：staging 表允许 NULL，但目标表列可能为 NOT NULL）
				updateSet[i] = fmt.Sprintf("target.[%s] = ISNULL(source.[%s], target.[%s])", c, c, c)
			}
		}
	// Remove empty entries
	updateSetClean := make([]string, 0, len(updateSet))
	for _, s := range updateSet {
		if s != "" {
			updateSetClean = append(updateSetClean, s)
		}
	}

	insertCols := make([]string, len(cols))
	for i, c := range cols {
		insertCols[i] = fmt.Sprintf("[%s]", c)
	}

	mergeSQL := fmt.Sprintf(
		"MERGE INTO dbo.%s AS target "+
			"USING dbo.%s AS source "+
			"ON %s "+
			"WHEN MATCHED THEN UPDATE SET %s "+
			"WHEN NOT MATCHED THEN INSERT (%s) VALUES (%s);",
		tableName, stagingTable,
		strings.Join(matchConditions, " AND "),
		strings.Join(updateSetClean, ", "),
		strings.Join(insertCols, ", "),
		strings.Join(insertCols, ", "),
	)

	return mergeSQL, nil
}

func (w *SQLServerWriter) mapDataType(dataType string, maxLen sql.NullInt64,
	precision, scale sql.NullInt64) string {

	switch strings.ToLower(dataType) {
	case "nvarchar":
		if maxLen.Valid && maxLen.Int64 > 0 && maxLen.Int64 != 2147483647 {
			return fmt.Sprintf("NVARCHAR(%d)", maxLen.Int64)
		}
		return "NVARCHAR(MAX)"
	case "varchar":
		if maxLen.Valid && maxLen.Int64 > 0 && maxLen.Int64 != 2147483647 {
			return fmt.Sprintf("VARCHAR(%d)", maxLen.Int64)
		}
		return "VARCHAR(MAX)"
	case "nchar", "char":
		if maxLen.Valid && maxLen.Int64 > 0 {
			if strings.HasPrefix(dataType, "n") {
				return fmt.Sprintf("NCHAR(%d)", maxLen.Int64)
			}
			return fmt.Sprintf("CHAR(%d)", maxLen.Int64)
		}
		return "NVARCHAR(500)"
	case "int":
		return "INT"
	case "bigint":
		return "BIGINT"
	case "smallint":
		return "SMALLINT"
	case "tinyint":
		return "TINYINT"
	case "decimal", "numeric":
		if precision.Valid && scale.Valid {
			return fmt.Sprintf("DECIMAL(%d,%d)", precision.Int64, scale.Int64)
		}
		return "DECIMAL(18,4)"
	case "float":
		return "FLOAT"
	case "real":
		return "REAL"
	case "datetime", "datetime2":
		return "DATETIME2"
	case "date":
		return "DATE"
	case "time":
		return "TIME"
	case "bit":
		return "BIT"
	case "uniqueidentifier":
		return "UNIQUEIDENTIFIER"
	case "text", "ntext":
		return "NVARCHAR(MAX)"
	case "xml":
		return "NVARCHAR(MAX)"
	default:
		return "NVARCHAR(500)"
	}
}

// appendSyncTimeCol 在目标表存在 SYNC_TIME 列时把它追加进写列白名单。
// existingCols 的 key 为大写列名、value 为实际列名。
func appendSyncTimeCol(cols []string, existingCols map[string]string) []string {
	actual, ok := existingCols["SYNC_TIME"]
	if !ok || containsStringFold(cols, actual) {
		return cols
	}
	return append(cols, actual)
}

// injectSyncTime 在写列包含 SYNC_TIME 时为每行注入当前写入时刻。
// 格式与本地时区约定同 normalization.go（容器与金蝶修改时间字段同为东八区），
// 保证 GetLastSyncTime 的 MAX(SYNC_TIME) 能作为增量窗口下界正常推进。
func injectSyncTime(rows []map[string]interface{}, cols []string) {
	if !containsStringFold(cols, "SYNC_TIME") {
		return
	}
	now := time.Now().Format("2006-01-02 15:04:05")
	for _, row := range rows {
		row["SYNC_TIME"] = now
	}
}

func containsStringFold(list []string, target string) bool {
	for _, s := range list {
		if strings.EqualFold(s, target) {
			return true
		}
	}
	return false
}

func (w *SQLServerWriter) lookupValue(row map[string]interface{}, col string, colToKingdee map[string][]string) interface{} {
	if v, ok := row[col]; ok && v != nil {
		return v
	}
	if v, ok := row[strings.ToUpper(col)]; ok && v != nil {
		return v
	}
	for _, kf := range colToKingdee[strings.ToUpper(col)] {
		if v, ok := row[kf]; ok && v != nil {
			return v
		}
	}
	// Case-insensitive fallback
	for key, value := range row {
		if value != nil && strings.EqualFold(key, col) {
			return value
		}
	}
	return nil
}

func (w *SQLServerWriter) isForceStagingTable(tableName string) bool {
	cfg := config.Get()
	if cfg == nil {
		return false
	}
	// Read force_staging_tables from config
	// For now, use a hardcoded list aligned with the Python config
	forceStaging := []string{
		"saleorder", "sal_outstock", "sal_returnstock", "sal_deliverynotice",
		"pln_forecast", "prd_instock", "prd_mo", "prd_moentry",
		"prd_ppbom", "prd_ppbomentry", "eng_bom", "eng_bomchild",
		"stk_inventory", "pur_purchaseorder", "sub_subreqorder", "bd_material",
	}
	for _, t := range forceStaging {
		if strings.EqualFold(tableName, t) {
			return true
		}
	}
	return false
}

// DeleteOrphaned deletes rows from SQL Server that are not in the provided source data.
func (w *SQLServerWriter) DeleteOrphaned(ctx context.Context, tableName string, rows []map[string]interface{},
	pkCols []string) (int, error) {

	if len(rows) == 0 || len(pkCols) == 0 {
		return 0, nil
	}
	// 纵深防御：表名/主键列名拼接进 DELETE SQL（原因：同 Upsert）
	if err := config.ValidateSQLIdentifier(tableName); err != nil {
		return 0, err
	}
	for _, col := range pkCols {
		if err := config.ValidateSQLIdentifier(col); err != nil {
			return 0, err
		}
	}
	if db.DB == nil {
		return 0, fmt.Errorf("database not initialized")
	}

	// Collect distinct PK tuples
	pkSet := make(map[string][]interface{})
	for _, row := range rows {
		vals := make([]interface{}, len(pkCols))
		keyParts := make([]string, len(pkCols))
		for i, col := range pkCols {
			v := w.lookupValueByCol(row, col)
			vals[i] = v
			keyParts[i] = fmt.Sprintf("%v", v)
		}
		key := strings.Join(keyParts, "|")
		pkSet[key] = vals
	}

	if len(pkSet) == 0 {
		return 0, nil
	}

	// Safety limit
	if len(pkSet) > 500000 {
		return 0, fmt.Errorf("PK count %d exceeds safe limit; orphan deletion refused", len(pkSet))
	}

	// Build NOT IN with concatenated key tuples
	tuples := make([][]interface{}, 0, len(pkSet))
	for _, vals := range pkSet {
		tuples = append(tuples, vals)
	}

	inValues := make([]string, 0, len(tuples))
	for _, vals := range tuples {
		var parts []string
		for _, v := range vals {
			switch val := v.(type) {
			case string:
				parts = append(parts, fmt.Sprintf("N'%s'", strings.ReplaceAll(val, "'", "''")))
			case int64:
				parts = append(parts, fmt.Sprintf("%d", val))
			case float64:
				parts = append(parts, fmt.Sprintf("%v", val))
			default:
				parts = append(parts, fmt.Sprintf("N'%s'", strings.ReplaceAll(fmt.Sprint(val), "'", "''")))
			}
		}
		inValues = append(inValues, fmt.Sprintf("'%s'", strings.Join(parts, "|")))
	}

	// Key expression: concatenate ISNULL'd columns with the same "|" separator.
	// Do NOT use CONCAT() — it requires 2..254 arguments and fails for 1-column keys.
	// （原因：单列主键时 CONCAT 只有一个参数会语法错误；+ 拼接无此限制）
	colExprs := make([]string, len(pkCols))
	for i, c := range pkCols {
		colExprs[i] = fmt.Sprintf("ISNULL(CAST([%s] AS NVARCHAR(4000)), '')", c)
	}

	deleteSQL := fmt.Sprintf(
		"DELETE FROM dbo.%s WHERE (%s) NOT IN (%s)",
		tableName, strings.Join(colExprs, " + '|' + "), strings.Join(inValues, ", "),
	)

	result, err := db.DB.ExecContext(ctx, deleteSQL)
	if err != nil {
		return 0, fmt.Errorf("execute DELETE for %s: %w", tableName, err)
	}
	n, _ := result.RowsAffected()
	log.Printf("[SQLSERVER-DELETE] Deleted %d orphaned rows from %s (source has %d distinct PKs)", n, tableName, len(pkSet))
	return int(n), nil
}

func (w *SQLServerWriter) lookupValueByCol(row map[string]interface{}, col string) interface{} {
	if v, ok := row[col]; ok && v != nil {
		return v
	}
	if v, ok := row[strings.ToUpper(col)]; ok && v != nil {
		return v
	}
	for key, value := range row {
		if value != nil && strings.EqualFold(key, col) {
			return value
		}
	}
	return nil
}

func (w *SQLServerWriter) Close() error {
	return nil
}
// getSQLTarget returns the SQL Server connection target.
func (w *SQLServerWriter) getSQLTarget() (host, user, password string, err error) {
	if w.cfg.Host == "" {
		return "", "", "", fmt.Errorf("SQL Server target not configured")
	}
	return w.cfg.Host, w.cfg.User, w.cfg.Password, nil
}

// DeleteKeys marks specific PK rows as deleted in SQL Server.
func (w *SQLServerWriter) DeleteKeys(ctx context.Context, tableName string, rows []map[string]interface{}, keyCols []string) (int, error) {
	if len(rows) == 0 {
		return 0, nil
	}
	if len(keyCols) == 0 {
		return 0, fmt.Errorf("delete keys require at least one key column")
	}
	if db.DB == nil {
		return 0, fmt.Errorf("database not initialized")
	}

	// Deduplicate by key tuple
	seen := make(map[string]bool)
	uniqueRows := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		parts := make([]string, len(keyCols))
		for i, col := range keyCols {
			v := w.lookupValueByCol(row, col)
			parts[i] = fmt.Sprint(v)
		}
		key := strings.Join(parts, "|")
		if !seen[key] {
			seen[key] = true
			uniqueRows = append(uniqueRows, row)
		}
	}

	// Build DELETE with OR-combined key tuples so composite keys
	// (e.g. FID,FENTRYID) match exactly instead of only the first column.
	// （原因：之前只按第一列 IN 删除，复合主键会误删同第一列值的所有行）
	if len(keyCols) == 0 {
		return 0, nil
	}

	var orConditions []string
	for _, row := range uniqueRows {
		var conds []string
		for _, col := range keyCols {
			v := w.lookupValueByCol(row, col)
			switch val := v.(type) {
			case string:
				conds = append(conds, fmt.Sprintf("[%s] = N'%s'", col, strings.ReplaceAll(val, "'", "''")))
			case int64:
				conds = append(conds, fmt.Sprintf("[%s] = %d", col, val))
			case float64:
				conds = append(conds, fmt.Sprintf("[%s] = %v", col, val))
			default:
				conds = append(conds, fmt.Sprintf("[%s] = N'%s'", col, strings.ReplaceAll(fmt.Sprint(val), "'", "''")))
			}
		}
		orConditions = append(orConditions, "("+strings.Join(conds, " AND ")+")")
	}

	deleteSQL := fmt.Sprintf("DELETE FROM dbo.%s WHERE %s", tableName, strings.Join(orConditions, " OR "))
	result, err := db.DB.ExecContext(ctx, deleteSQL)
	if err != nil {
		return 0, fmt.Errorf("execute DELETE keys for %s: %w", tableName, err)
	}
	n, _ := result.RowsAffected()
	log.Printf("[SQLSERVER-DELETE-KEYS] Deleted %d rows from %s", n, tableName)
	return int(n), nil
}

