namespace Kingdee.SyncTool.Domain.Models;

public sealed class FormQueryOptions
{
    public string FormId { get; init; } = string.Empty;

    public string FieldKeys { get; init; } = string.Empty;

    public object? FilterString { get; init; } = string.Empty;

    public string OrderString { get; init; } = string.Empty;

    public int TopRowCount { get; init; }

    public int StartRow { get; init; }

    public int Limit { get; init; }

    public string SubSystemId { get; init; } = string.Empty;

    public IReadOnlyDictionary<string, object?> ExtraParameters { get; init; } =
        new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
}
