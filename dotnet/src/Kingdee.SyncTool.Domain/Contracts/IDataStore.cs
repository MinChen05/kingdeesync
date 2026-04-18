namespace Kingdee.SyncTool.Domain.Contracts;

public interface IDataStore
{
    Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default);

    Task<DateTimeOffset?> GetLastSyncTimeAsync(string tableName, CancellationToken cancellationToken = default);

    Task<int> UpsertBatchAsync(
        string tableName,
        IReadOnlyList<IDictionary<string, object?>> rows,
        CancellationToken cancellationToken = default);

    Task LogSyncOperationAsync(
        string tableName,
        string syncType,
        string status,
        int recordCount,
        string message,
        DateTimeOffset startTime,
        DateTimeOffset endTime,
        CancellationToken cancellationToken = default);
}
