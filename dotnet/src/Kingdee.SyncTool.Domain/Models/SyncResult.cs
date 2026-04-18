using Kingdee.SyncTool.Domain.Enums;

namespace Kingdee.SyncTool.Domain.Models;

public sealed class SyncResult
{
    public string RunId { get; init; } = Guid.NewGuid().ToString("N");

    public SyncStatus Status { get; set; } = SyncStatus.Running;

    public string Message { get; set; } = string.Empty;

    public DateTimeOffset StartTime { get; init; } = DateTimeOffset.Now;

    public DateTimeOffset EndTime { get; set; } = DateTimeOffset.Now;

    public int TotalSourceCount { get; set; }

    public int TotalInsertedCount { get; set; }

    public int TotalUpdatedCount { get; set; }

    public IReadOnlyDictionary<string, FormSyncDetail> Details { get; set; } =
        new Dictionary<string, FormSyncDetail>(StringComparer.OrdinalIgnoreCase);
}
