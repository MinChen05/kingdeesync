using Kingdee.SyncTool.Domain.Models;

namespace Kingdee.SyncTool.Domain.Contracts;

public interface ISchedulerService
{
    event Action<SyncResult>? SyncCompleted;

    SchedulerStatusInfo Status { get; }

    void Configure(TimeSpan interval, SyncRequest request);

    Task StartAsync(CancellationToken cancellationToken = default);

    Task StopAsync(CancellationToken cancellationToken = default);
}
