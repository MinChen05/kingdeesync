using Kingdee.SyncTool.Domain.Enums;

namespace Kingdee.SyncTool.Domain.Models;

public sealed class FormSyncDetail
{
    public string FormName { get; init; } = string.Empty;

    public string TableName { get; init; } = string.Empty;

    public SyncStatus Status { get; init; } = SyncStatus.Success;

    public int SourceCount { get; init; }

    public int InsertedCount { get; init; }

    public int UpdatedCount { get; init; }

    public string Message { get; init; } = string.Empty;

    public TimeSpan Duration { get; init; } = TimeSpan.Zero;
}
