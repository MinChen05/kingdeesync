using Kingdee.SyncTool.Domain.Enums;

namespace Kingdee.SyncTool.Domain.Contracts;

public interface IApiClient
{
    Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default);

    Task<bool> EnsureAuthenticatedAsync(CancellationToken cancellationToken = default);

    Task<IReadOnlyList<IDictionary<string, object?>>> QueryFormAsync(
        string formName,
        SyncType syncType,
        string? filterString,
        int startRow,
        int limit,
        CancellationToken cancellationToken = default);

    Task LogoutAsync(CancellationToken cancellationToken = default);
}
