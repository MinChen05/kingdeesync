using Kingdee.SyncTool.Domain.Enums;

namespace Kingdee.SyncTool.Domain.Models;

public sealed class SyncRequest
{
    public IReadOnlyList<string> Forms { get; init; } = Array.Empty<string>();

    public SyncType Type { get; init; } = SyncType.Incremental;

    public bool UseDefaultFormsWhenEmpty { get; init; } = true;
}
