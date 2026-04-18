using Kingdee.SyncTool.Domain.Contracts;

namespace Kingdee.SyncTool.Infrastructure.Data;

public sealed class DryRunDataStore : IDataStore
{
    private readonly string _logPath;
    private readonly Dictionary<string, DateTimeOffset> _lastSyncTimes = new(StringComparer.OrdinalIgnoreCase);

    public DryRunDataStore(string logPath)
    {
        _logPath = logPath;
    }

    public Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default)
    {
        // Dry-run datastore: always available.
        return Task.FromResult(true);
    }

    public Task<DateTimeOffset?> GetLastSyncTimeAsync(string tableName, CancellationToken cancellationToken = default)
    {
        return Task.FromResult(
            _lastSyncTimes.TryGetValue(tableName, out var dt)
                ? (DateTimeOffset?)dt
                : null);
    }

    public Task<int> UpsertBatchAsync(
        string tableName,
        IReadOnlyList<IDictionary<string, object?>> rows,
        CancellationToken cancellationToken = default)
    {
        _lastSyncTimes[tableName] = DateTimeOffset.Now;
        return Task.FromResult(rows.Count);
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
        var line =
            $"[{DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss}] table={tableName};syncType={syncType};status={status};records={recordCount};duration={(endTime - startTime).TotalSeconds:F2}s;message={message}";
        var dir = Path.GetDirectoryName(_logPath);
        if (!string.IsNullOrWhiteSpace(dir))
        {
            Directory.CreateDirectory(dir);
        }
        await File.AppendAllTextAsync(_logPath, line + Environment.NewLine, cancellationToken).ConfigureAwait(false);
    }
}
