using Kingdee.SyncTool.Domain.Enums;

namespace Kingdee.SyncTool.Domain.Models;

public sealed class SchedulerStatusInfo
{
    public SchedulerState Status { get; init; } = SchedulerState.Stopped;

    public DateTimeOffset? LastExecutionTime { get; init; }

    public DateTimeOffset? NextExecutionTime { get; init; }

    public TimeSpan Interval { get; init; } = TimeSpan.FromMinutes(60);

    public string Message { get; init; } = string.Empty;
}
