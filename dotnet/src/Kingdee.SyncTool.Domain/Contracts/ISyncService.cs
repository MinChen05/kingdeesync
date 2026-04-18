using Kingdee.SyncTool.Domain.Models;

namespace Kingdee.SyncTool.Domain.Contracts;

public interface ISyncService
{
    event Action<string, int>? ProgressChanged;

    Task<bool> TestConnectionsAsync(CancellationToken cancellationToken = default);

    Task<SyncResult> ExecuteAsync(SyncRequest request, CancellationToken cancellationToken = default);
}
