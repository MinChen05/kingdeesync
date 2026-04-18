using Kingdee.SyncTool.Domain.Contracts;
using Kingdee.SyncTool.Domain.Models;
using System.Collections.Concurrent;
using System.Data.Odbc;

namespace Kingdee.SyncTool.Infrastructure.Data;

public sealed class SqlServerDataStore : IDataStore
{
    private readonly string _connectionString;
    private readonly ConcurrentDictionary<string, TableMetadata> _metadataCache =
        new(StringComparer.OrdinalIgnoreCase);

    public SqlServerDataStore(DatabaseOptions databaseOptions)
    {
        _connectionString = BuildConnectionString(databaseOptions.SqlServer);
    }

    public async Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            await using var conn = new OdbcConnection(_connectionString);
            await conn.OpenAsync(cancellationToken).ConfigureAwait(false);
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT 1";
            var value = await cmd.ExecuteScalarAsync(cancellationToken).ConfigureAwait(false);
            return value is not null;
        }
        catch
        {
            return false;
        }
    }

    public async Task<DateTimeOffset?> GetLastSyncTimeAsync(string tableName, CancellationToken cancellationToken = default)
    {
        const string sql = @"
SELECT MAX(start_time)
FROM sync_logs
WHERE table_name = ? AND status = 'success'";

        try
        {
            await using var conn = new OdbcConnection(_connectionString);
            await conn.OpenAsync(cancellationToken).ConfigureAwait(false);
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = sql;
            cmd.Parameters.Add(new OdbcParameter("@table_name", tableName));

            var value = await cmd.ExecuteScalarAsync(cancellationToken).ConfigureAwait(false);
            if (value is null || value is DBNull)
            {
                return null;
            }

            if (value is DateTime dateTime)
            {
                return new DateTimeOffset(dateTime);
            }

            if (DateTimeOffset.TryParse(value.ToString(), out var parsed))
            {
                return parsed;
            }
        }
        catch
        {
            // Ignore query failure and fallback to null.
        }

        return null;
    }

    public Task<int> UpsertBatchAsync(
        string tableName,
        IReadOnlyList<IDictionary<string, object?>> rows,
        CancellationToken cancellationToken = default)
    {
        return UpsertBatchInternalAsync(tableName, rows, cancellationToken);
    }

    public async Task LogSyncOperationAsync(
        string tableName,
        string syncType,
        string status,
        int recordCount,
        string message,
        DateTimeOffset startTime,
        DateTimeOffset endTime,
        CancellationToken cancellationToken = default)
    {
        const string sql = @"
INSERT INTO sync_logs
    (sync_type, table_name, operation, record_count, status, message, start_time, end_time, duration)
VALUES
    (?, ?, 'sync', ?, ?, ?, ?, ?, ?)";

        await using var conn = new OdbcConnection(_connectionString);
        await conn.OpenAsync(cancellationToken).ConfigureAwait(false);
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        cmd.Parameters.Add(new OdbcParameter("@sync_type", syncType));
        cmd.Parameters.Add(new OdbcParameter("@table_name", tableName));
        cmd.Parameters.Add(new OdbcParameter("@record_count", recordCount));
        cmd.Parameters.Add(new OdbcParameter("@status", status));
        cmd.Parameters.Add(new OdbcParameter("@message", message));
        cmd.Parameters.Add(new OdbcParameter("@start_time", startTime.LocalDateTime));
        cmd.Parameters.Add(new OdbcParameter("@end_time", endTime.LocalDateTime));
        cmd.Parameters.Add(new OdbcParameter("@duration", (endTime - startTime).TotalSeconds));

        await cmd.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
    }

    private static string BuildConnectionString(SqlServerConnectionOptions options)
    {
        var segments = new List<string>();

        var driver = string.IsNullOrWhiteSpace(options.Driver) ? "ODBC Driver 17 for SQL Server" : options.Driver;
        segments.Add($"Driver={{{driver}}}");
        segments.Add($"Server={options.Host},{options.Port}");
        segments.Add($"Database={options.Database}");

        if (options.TrustedConnection)
        {
            segments.Add("Trusted_Connection=Yes");
        }
        else
        {
            segments.Add($"Uid={options.User}");
            segments.Add($"Pwd={options.Password}");
            segments.Add("Trusted_Connection=No");
        }

        segments.Add("Encrypt=No");
        segments.Add("TrustServerCertificate=Yes");
        return string.Join(';', segments);
    }

    private async Task<int> UpsertBatchInternalAsync(
        string tableName,
        IReadOnlyList<IDictionary<string, object?>> rows,
        CancellationToken cancellationToken)
    {
        if (rows.Count == 0)
        {
            return 0;
        }

        var metadata = await GetTableMetadataAsync(tableName, cancellationToken).ConfigureAwait(false);
        if (metadata.Columns.Count == 0)
        {
            return 0;
        }

        var normalizedRows = rows
            .Select(row => new Dictionary<string, object?>(row, StringComparer.OrdinalIgnoreCase))
            .ToArray();

        var sourceColumns = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var row in normalizedRows)
        {
            foreach (var key in row.Keys)
            {
                if (!metadata.ColumnsSet.Contains(key))
                {
                    continue;
                }

                if (metadata.IdentityColumnsSet.Contains(key))
                {
                    continue;
                }

                sourceColumns.Add(key);
            }
        }

        var candidateColumns = metadata.Columns
            .Where(sourceColumns.Contains)
            .ToArray();

        if (candidateColumns.Length == 0)
        {
            return 0;
        }

        var pkColumns = metadata.PrimaryKeys
            .Where(pk => candidateColumns.Contains(pk, StringComparer.OrdinalIgnoreCase))
            .ToArray();

        await using var conn = new OdbcConnection(_connectionString);
        await conn.OpenAsync(cancellationToken).ConfigureAwait(false);
        using var tx = conn.BeginTransaction();

        try
        {
            var affected = pkColumns.Length > 0
                ? await ExecuteUpsertByPrimaryKeyAsync(
                    conn,
                    tx,
                    metadata,
                    candidateColumns,
                    pkColumns,
                    normalizedRows,
                    cancellationToken).ConfigureAwait(false)
                : await ExecuteInsertOnlyAsync(
                    conn,
                    tx,
                    metadata.FullName,
                    candidateColumns,
                    normalizedRows,
                    cancellationToken).ConfigureAwait(false);

            tx.Commit();
            return affected;
        }
        catch
        {
            tx.Rollback();
            throw;
        }
    }

    private async Task<int> ExecuteInsertOnlyAsync(
        OdbcConnection conn,
        OdbcTransaction tx,
        string fullTableName,
        IReadOnlyList<string> insertColumns,
        IReadOnlyList<Dictionary<string, object?>> rows,
        CancellationToken cancellationToken)
    {
        if (rows.Count == 0)
        {
            return 0;
        }

        var insertSql = BuildInsertSql(fullTableName, insertColumns);
        await using var cmd = conn.CreateCommand();
        cmd.Transaction = tx;
        cmd.CommandText = insertSql;
        for (var i = 0; i < insertColumns.Count; i++)
        {
            cmd.Parameters.Add(new OdbcParameter($"@p{i}", DBNull.Value));
        }

        var affected = 0;
        foreach (var row in rows)
        {
            ApplyParameterValues(cmd, insertColumns, row, 0);
            affected += await cmd.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
        }

        return affected;
    }

    private async Task<int> ExecuteUpsertByPrimaryKeyAsync(
        OdbcConnection conn,
        OdbcTransaction tx,
        TableMetadata metadata,
        IReadOnlyList<string> allColumns,
        IReadOnlyList<string> pkColumns,
        IReadOnlyList<Dictionary<string, object?>> rows,
        CancellationToken cancellationToken)
    {
        var withPk = new List<Dictionary<string, object?>>(rows.Count);
        var withoutPk = new List<Dictionary<string, object?>>();
        foreach (var row in rows)
        {
            if (HasAllPrimaryKeyValues(row, pkColumns))
            {
                withPk.Add(row);
            }
            else
            {
                withoutPk.Add(row);
            }
        }

        var affected = 0;
        if (withoutPk.Count > 0)
        {
            affected += await ExecuteInsertOnlyAsync(
                conn,
                tx,
                metadata.FullName,
                allColumns,
                withoutPk,
                cancellationToken).ConfigureAwait(false);
        }

        if (withPk.Count == 0)
        {
            return affected;
        }

        var stageTableName = $"#kg_stage_{Guid.NewGuid():N}";

        try
        {
            await using (var createCmd = conn.CreateCommand())
            {
                createCmd.Transaction = tx;
                createCmd.CommandText = BuildStageCreateSql(stageTableName, metadata.FullName, allColumns);
                await createCmd.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
            }

            // Batch insert all rows into staging first.
            await ExecuteInsertOnlyAsync(
                conn,
                tx,
                stageTableName,
                allColumns,
                withPk,
                cancellationToken).ConfigureAwait(false);

            if (withPk.Count > 1)
            {
                await using var dedupeCmd = conn.CreateCommand();
                dedupeCmd.Transaction = tx;
                dedupeCmd.CommandText = BuildStageDeduplicateSql(stageTableName, pkColumns);
                await dedupeCmd.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
            }

            var updateColumns = allColumns
                .Where(column => !pkColumns.Contains(column, StringComparer.OrdinalIgnoreCase))
                .ToArray();

            await using var mergeCmd = conn.CreateCommand();
            mergeCmd.Transaction = tx;
            mergeCmd.CommandText = BuildMergeFromStageSql(
                metadata.FullName,
                stageTableName,
                allColumns,
                pkColumns,
                updateColumns);
            affected += await mergeCmd.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            try
            {
                await using var dropCmd = conn.CreateCommand();
                dropCmd.Transaction = tx;
                dropCmd.CommandText = $"DROP TABLE {stageTableName};";
                await dropCmd.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
            }
            catch
            {
                // Temp table will be dropped when the connection closes.
            }
        }

        return affected;
    }

    private static string BuildInsertSql(string fullTableName, IReadOnlyList<string> insertColumns)
    {
        var cols = string.Join(", ", insertColumns.Select(QuoteIdentifier));
        var values = string.Join(", ", Enumerable.Repeat("?", insertColumns.Count));
        return $"INSERT INTO {fullTableName} ({cols}) VALUES ({values})";
    }

    private static string BuildStageCreateSql(
        string stageTableName,
        string fullTableName,
        IReadOnlyList<string> columns)
    {
        var columnList = string.Join(", ", columns.Select(QuoteIdentifier));
        return $"SELECT TOP 0 {columnList} INTO {stageTableName} FROM {fullTableName};";
    }

    private static string BuildStageDeduplicateSql(string stageTableName, IReadOnlyList<string> pkColumns)
    {
        var partitionBy = string.Join(", ", pkColumns.Select(QuoteIdentifier));
        return $@"
;WITH dedupe AS
(
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY {partitionBy} ORDER BY (SELECT 0)) AS __rn
    FROM {stageTableName}
)
DELETE FROM dedupe
WHERE __rn > 1;";
    }

    private static string BuildMergeFromStageSql(
        string fullTableName,
        string stageTableName,
        IReadOnlyList<string> allColumns,
        IReadOnlyList<string> pkColumns,
        IReadOnlyList<string> updateColumns)
    {
        var mergeOn = string.Join(
            " AND ",
            pkColumns.Select(column => $"t.{QuoteIdentifier(column)} = s.{QuoteIdentifier(column)}"));

        var insertCols = string.Join(", ", allColumns.Select(QuoteIdentifier));
        var insertValues = string.Join(", ", allColumns.Select(column => $"s.{QuoteIdentifier(column)}"));

        if (updateColumns.Count == 0)
        {
            return $@"
MERGE INTO {fullTableName} WITH (HOLDLOCK) AS t
USING {stageTableName} AS s
ON {mergeOn}
WHEN NOT MATCHED BY TARGET THEN
    INSERT ({insertCols})
    VALUES ({insertValues});";
        }

        var updateSet = string.Join(
            ", ",
            updateColumns.Select(column => $"t.{QuoteIdentifier(column)} = s.{QuoteIdentifier(column)}"));

        return $@"
MERGE INTO {fullTableName} WITH (HOLDLOCK) AS t
USING {stageTableName} AS s
ON {mergeOn}
WHEN MATCHED THEN
    UPDATE SET {updateSet}
WHEN NOT MATCHED BY TARGET THEN
    INSERT ({insertCols})
    VALUES ({insertValues});";
    }

    private static bool HasAllPrimaryKeyValues(
        IReadOnlyDictionary<string, object?> row,
        IReadOnlyList<string> pkColumns)
    {
        foreach (var pk in pkColumns)
        {
            if (!row.TryGetValue(pk, out var value))
            {
                return false;
            }

            if (value is null || value is DBNull)
            {
                return false;
            }
        }

        return true;
    }

    private static void ApplyParameterValues(
        OdbcCommand cmd,
        IReadOnlyList<string> parameterColumns,
        IReadOnlyDictionary<string, object?> row,
        int startIndex)
    {
        for (var i = 0; i < parameterColumns.Count; i++)
        {
            var col = parameterColumns[i];
            var value = row.TryGetValue(col, out var rawValue) ? rawValue : null;
            cmd.Parameters[startIndex + i].Value = value ?? DBNull.Value;
        }
    }

    private async Task<TableMetadata> GetTableMetadataAsync(string tableName, CancellationToken cancellationToken)
    {
        var (schema, table) = ParseTableName(tableName);
        var cacheKey = $"{schema}.{table}";
        if (_metadataCache.TryGetValue(cacheKey, out var cached))
        {
            return cached;
        }

        await using var conn = new OdbcConnection(_connectionString);
        await conn.OpenAsync(cancellationToken).ConfigureAwait(false);

        var columns = await QueryColumnsAsync(conn, schema, table, cancellationToken).ConfigureAwait(false);
        var primaryKeys = await QueryPrimaryKeysAsync(conn, schema, table, cancellationToken).ConfigureAwait(false);
        var identityColumns = await QueryIdentityColumnsAsync(conn, schema, table, cancellationToken).ConfigureAwait(false);

        var metadata = new TableMetadata(
            schema: schema,
            table: table,
            fullName: $"{QuoteIdentifier(schema)}.{QuoteIdentifier(table)}",
            columns: columns,
            primaryKeys: primaryKeys,
            identityColumns: identityColumns);

        _metadataCache.TryAdd(cacheKey, metadata);
        return metadata;
    }

    private static async Task<string[]> QueryColumnsAsync(
        OdbcConnection conn,
        string schema,
        string table,
        CancellationToken cancellationToken)
    {
        const string sql = @"
SELECT COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
ORDER BY ORDINAL_POSITION";

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        cmd.Parameters.Add(new OdbcParameter("@schema", schema));
        cmd.Parameters.Add(new OdbcParameter("@table", table));

        var list = new List<string>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
        while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
        {
            list.Add(reader.GetString(0));
        }
        return list.ToArray();
    }

    private static async Task<string[]> QueryPrimaryKeysAsync(
        OdbcConnection conn,
        string schema,
        string table,
        CancellationToken cancellationToken)
    {
        const string sql = @"
SELECT k.COLUMN_NAME
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS t
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
    ON t.CONSTRAINT_NAME = k.CONSTRAINT_NAME
   AND t.TABLE_SCHEMA = k.TABLE_SCHEMA
   AND t.TABLE_NAME = k.TABLE_NAME
WHERE t.TABLE_SCHEMA = ?
  AND t.TABLE_NAME = ?
  AND t.CONSTRAINT_TYPE = 'PRIMARY KEY'
ORDER BY k.ORDINAL_POSITION";

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        cmd.Parameters.Add(new OdbcParameter("@schema", schema));
        cmd.Parameters.Add(new OdbcParameter("@table", table));

        var list = new List<string>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
        while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
        {
            list.Add(reader.GetString(0));
        }
        return list.ToArray();
    }

    private static async Task<string[]> QueryIdentityColumnsAsync(
        OdbcConnection conn,
        string schema,
        string table,
        CancellationToken cancellationToken)
    {
        const string sql = @"
SELECT c.name
FROM sys.columns c
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = ? AND t.name = ? AND c.is_identity = 1";

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        cmd.Parameters.Add(new OdbcParameter("@schema", schema));
        cmd.Parameters.Add(new OdbcParameter("@table", table));

        var list = new List<string>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
        while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
        {
            list.Add(reader.GetString(0));
        }
        return list.ToArray();
    }

    private static (string Schema, string Table) ParseTableName(string tableName)
    {
        if (string.IsNullOrWhiteSpace(tableName))
        {
            throw new ArgumentException("Table name is required.", nameof(tableName));
        }

        var cleaned = tableName.Trim().Trim('[', ']');
        var parts = cleaned.Split('.', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (parts.Length == 2)
        {
            return (parts[0], parts[1]);
        }

        return ("dbo", parts[0]);
    }

    private static string QuoteIdentifier(string identifier)
    {
        return $"[{identifier.Replace("]", "]]", StringComparison.Ordinal)}]";
    }

    private sealed class TableMetadata
    {
        public TableMetadata(
            string schema,
            string table,
            string fullName,
            IReadOnlyList<string> columns,
            IReadOnlyList<string> primaryKeys,
            IReadOnlyList<string> identityColumns)
        {
            Schema = schema;
            Table = table;
            FullName = fullName;
            Columns = columns;
            PrimaryKeys = primaryKeys;
            IdentityColumns = identityColumns;
            ColumnsSet = new HashSet<string>(columns, StringComparer.OrdinalIgnoreCase);
            IdentityColumnsSet = new HashSet<string>(identityColumns, StringComparer.OrdinalIgnoreCase);
        }

        public string Schema { get; }

        public string Table { get; }

        public string FullName { get; }

        public IReadOnlyList<string> Columns { get; }

        public IReadOnlyList<string> PrimaryKeys { get; }

        public IReadOnlyList<string> IdentityColumns { get; }

        public IReadOnlySet<string> ColumnsSet { get; }

        public IReadOnlySet<string> IdentityColumnsSet { get; }
    }
}
