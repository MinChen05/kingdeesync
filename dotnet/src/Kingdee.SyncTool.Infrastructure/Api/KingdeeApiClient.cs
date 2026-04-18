using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Kingdee.SyncTool.Domain.Contracts;
using Kingdee.SyncTool.Domain.Enums;
using Kingdee.SyncTool.Domain.Models;

namespace Kingdee.SyncTool.Infrastructure.Api;

public sealed class KingdeeApiClient : IApiClient, IDisposable
{
    private readonly IConfigProvider _configProvider;
    private readonly HttpClient _httpClient;
    private readonly SemaphoreSlim _authGate = new(1, 1);

    private bool _isAuthenticated;

    public KingdeeApiClient(IConfigProvider configProvider)
    {
        _configProvider = configProvider;
        var options = _configProvider.GetKingdeeOptions();

        var handler = new HttpClientHandler
        {
            UseCookies = true,
            CookieContainer = new CookieContainer(),
            AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate,
            ServerCertificateCustomValidationCallback = static (_, _, _, _) => true,
        };

        _httpClient = new HttpClient(handler);
        if (options.RequestTimeoutSeconds > 0)
        {
            _httpClient.Timeout = TimeSpan.FromSeconds(options.RequestTimeoutSeconds);
        }
        _httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
    }

    public async Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default)
    {
        return await EnsureAuthenticatedAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task<bool> EnsureAuthenticatedAsync(CancellationToken cancellationToken = default)
    {
        if (_isAuthenticated)
        {
            return true;
        }

        await _authGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_isAuthenticated)
            {
                return true;
            }

            var options = _configProvider.GetKingdeeOptions();
            var payload = new Dictionary<string, object?>
            {
                ["acctID"] = options.AccountId,
                ["username"] = options.Username,
                ["password"] = options.Password.StartsWith("encrypted:", StringComparison.OrdinalIgnoreCase)
                    ? string.Empty
                    : options.Password,
                ["lcid"] = options.Lcid,
            };

            var response = await PostJsonAsync(options.LoginUrl, payload, cancellationToken).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                return false;
            }

            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            using var doc = JsonDocument.Parse(body);
            var root = doc.RootElement;

            var loginResultType = root.TryGetProperty("LoginResultType", out var loginTypeNode)
                ? loginTypeNode.GetInt32()
                : 0;

            _isAuthenticated = loginResultType == 1;
            return _isAuthenticated;
        }
        catch
        {
            _isAuthenticated = false;
            return false;
        }
        finally
        {
            _authGate.Release();
        }
    }

    public async Task<IReadOnlyList<IDictionary<string, object?>>> QueryFormAsync(
        string formName,
        SyncType syncType,
        string? filterString,
        int startRow,
        int limit,
        CancellationToken cancellationToken = default)
    {
        var authed = await EnsureAuthenticatedAsync(cancellationToken).ConfigureAwait(false);
        if (!authed)
        {
            return Array.Empty<IDictionary<string, object?>>();
        }

        var options = _configProvider.GetKingdeeOptions();
        var queryTemplates = _configProvider.GetFormQueries();
        var template = queryTemplates.TryGetValue(formName, out var formQuery)
            ? formQuery
            : new FormQueryOptions { FormId = formName };

        var effectiveFilter = MergeFilter(template.FilterString, filterString);
        var fieldKeys = template.FieldKeys
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(static x => x.Contains('.') ? x.Split('.').Last() : x)
            .ToArray();

        var requestData = new Dictionary<string, object?>(template.ExtraParameters, StringComparer.OrdinalIgnoreCase)
        {
            ["FormId"] = template.FormId,
            ["FieldKeys"] = template.FieldKeys,
            ["FilterString"] = effectiveFilter,
            ["OrderString"] = template.OrderString,
            ["TopRowCount"] = template.TopRowCount,
            ["StartRow"] = startRow,
            ["Limit"] = limit > 0 ? limit : template.Limit,
            ["SubSystemId"] = template.SubSystemId,
        };

        var payload = new Dictionary<string, object?>
        {
            ["data"] = requestData,
        };

        var targetUrl = options.QueryUrl;
        if (IsReportForm(template.FormId))
        {
            targetUrl = options.QueryUrl.Replace(
                "ExecuteBillQuery",
                "GetSysReportData",
                StringComparison.OrdinalIgnoreCase);

            var reportData = new Dictionary<string, object?>(requestData, StringComparer.OrdinalIgnoreCase);
            reportData.Remove("FilterString");

            payload = new Dictionary<string, object?>
            {
                ["formId"] = template.FormId,
                ["data"] = JsonSerializer.Serialize(reportData),
            };
        }

        var response = await PostJsonAsync(targetUrl, payload, cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
        {
            return Array.Empty<IDictionary<string, object?>>();
        }

        var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
        using var doc = JsonDocument.Parse(body);
        var arrayNode = FindFirstArray(doc.RootElement);
        if (!arrayNode.HasValue)
        {
            return Array.Empty<IDictionary<string, object?>>();
        }

        return ParseRows(arrayNode.Value, fieldKeys);
    }

    public Task LogoutAsync(CancellationToken cancellationToken = default)
    {
        _isAuthenticated = false;
        return Task.CompletedTask;
    }

    public void Dispose()
    {
        _authGate.Dispose();
        _httpClient.Dispose();
    }

    private async Task<HttpResponseMessage> PostJsonAsync(
        string url,
        object payload,
        CancellationToken cancellationToken)
    {
        var json = JsonSerializer.Serialize(payload);
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        return await _httpClient.PostAsync(url, content, cancellationToken).ConfigureAwait(false);
    }

    private static object? MergeFilter(object? baseFilter, string? extraFilter)
    {
        var right = string.IsNullOrWhiteSpace(extraFilter) ? string.Empty : extraFilter.Trim();

        if (right.Length == 0)
        {
            return baseFilter ?? string.Empty;
        }

        if (baseFilter is not string left || string.IsNullOrWhiteSpace(left))
        {
            return right;
        }

        return $"{left.Trim()} and {right}";
    }

    private static JsonElement? FindFirstArray(JsonElement node)
    {
        if (node.ValueKind == JsonValueKind.Array)
        {
            return node;
        }

        if (node.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        foreach (var property in node.EnumerateObject())
        {
            if (property.Value.ValueKind == JsonValueKind.Array)
            {
                return property.Value;
            }

            var nested = FindFirstArray(property.Value);
            if (nested.HasValue)
            {
                return nested.Value;
            }
        }

        return null;
    }

    private static IReadOnlyList<IDictionary<string, object?>> ParseRows(JsonElement rows, IReadOnlyList<string> fieldKeys)
    {
        var list = new List<IDictionary<string, object?>>();
        foreach (var row in rows.EnumerateArray())
        {
            if (row.ValueKind == JsonValueKind.Object)
            {
                var mapped = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
                foreach (var property in row.EnumerateObject())
                {
                    mapped[property.Name] = JsonToObject(property.Value);
                }
                list.Add(mapped);
                continue;
            }

            if (row.ValueKind == JsonValueKind.Array)
            {
                var values = row.EnumerateArray().ToArray();
                var mapped = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
                for (var i = 0; i < values.Length; i++)
                {
                    var key = i < fieldKeys.Count && !string.IsNullOrWhiteSpace(fieldKeys[i])
                        ? fieldKeys[i]
                        : $"F{i + 1}";
                    mapped[key] = JsonToObject(values[i]);
                }
                list.Add(mapped);
            }
        }
        return list;
    }

    private static object? JsonToObject(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Number when element.TryGetInt64(out var value) => value,
            JsonValueKind.Number when element.TryGetDecimal(out var decimalValue) => decimalValue,
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            _ => element.ToString(),
        };
    }

    private static bool IsReportForm(string formId)
    {
        return ReportFormIds.Contains(formId);
    }

    private static readonly HashSet<string> ReportFormIds = new(StringComparer.OrdinalIgnoreCase)
    {
        "GL_RPT_AccountBalance",
    };
}
