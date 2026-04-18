using System.Text;
using System.Text.Json;
using Kingdee.SyncTool.Domain.Contracts;
using Kingdee.SyncTool.Domain.Enums;
using Kingdee.SyncTool.Domain.Models;
using Kingdee.SyncTool.Infrastructure.Security;

namespace Kingdee.SyncTool.Infrastructure.Configuration;

public sealed class IniConfigProvider : IConfigProvider
{
    private readonly Dictionary<string, Dictionary<string, string>> _sections =
        new(StringComparer.OrdinalIgnoreCase);

    private readonly string _tableMappingsPath;
    private readonly string _formQueriesPath;

    private IReadOnlyDictionary<string, string>? _cachedTableMappings;
    private IReadOnlyDictionary<string, string>? _cachedInsertMethodMappings;
    private IReadOnlyDictionary<string, FormQueryOptions>? _cachedFormQueries;

    public IniConfigProvider(string configPath)
    {
        ConfigPath = ResolveConfigPath(configPath);
        _tableMappingsPath = ResolveTableMappingsPath(ConfigPath);
        _formQueriesPath = ResolveFormQueriesPath(ConfigPath);
        LoadIni(ConfigPath);
    }

    public string ConfigPath { get; }

    public KingdeeApiOptions GetKingdeeOptions()
    {
        var section = GetSection("KINGDEE");
        var password = GetValue(section, "password");
        return new KingdeeApiOptions
        {
            LoginUrl = GetValue(section, "login_url"),
            QueryUrl = GetValue(section, "query_url"),
            AccountId = GetValue(section, "acct_id"),
            Username = GetValue(section, "username"),
            Password = ConfigCryptoUtil.DecryptIfNeeded(password, ConfigPath),
            Lcid = GetValue(section, "lcid", "2052"),
            KeepSessionAlive = ParseBool(GetValue(section, "keep_session_alive", "true"), true),
            KeepAliveIntervalSeconds = ParseInt(GetValue(section, "keep_alive_interval_secs", "600"), 600),
            AutoLogoutOnExit = ParseBool(GetValue(section, "auto_logout_on_exit", "false"), false),
            RateLimitQps = ParseDouble(GetValue(section, "rate_limit_qps", "2"), 2.0),
            RequestTimeoutSeconds = ParseInt(GetValue(section, "request_timeout", "0"), 0),
            PageSize = ParseInt(GetValue(section, "page_size", "20000"), 20000),
            MaxPages = ParseInt(GetValue(section, "max_pages", "100000"), 100000),
        };
    }

    public DatabaseOptions GetDatabaseOptions()
    {
        var dbType = GetValue(GetSection("DATABASE"), "type", "sqlserver").ToLowerInvariant();
        var sqlSection = GetSection("SQLSERVER");
        var mySection = GetSection("MYSQL");

        var sqlPassword = ConfigCryptoUtil.DecryptIfNeeded(GetValue(sqlSection, "password"), ConfigPath);
        var myPassword = ConfigCryptoUtil.DecryptIfNeeded(GetValue(mySection, "password"), ConfigPath);

        return new DatabaseOptions
        {
            Type = dbType,
            SqlServer = new SqlServerConnectionOptions
            {
                Host = GetValue(sqlSection, "host", "127.0.0.1"),
                Port = ParseInt(GetValue(sqlSection, "port", "1433"), 1433),
                Database = GetValue(sqlSection, "database"),
                User = GetValue(sqlSection, "user"),
                Password = sqlPassword,
                Driver = GetValue(sqlSection, "driver", "ODBC Driver 17 for SQL Server"),
                TrustedConnection = ParseBool(GetValue(sqlSection, "trusted_connection", "false"), false),
            },
            MySql = new MySqlConnectionOptions
            {
                Host = GetValue(mySection, "host", "127.0.0.1"),
                Port = ParseInt(GetValue(mySection, "port", "3306"), 3306),
                Database = GetValue(mySection, "database"),
                User = GetValue(mySection, "user"),
                Password = myPassword,
            },
        };
    }

    public SyncRuntimeOptions GetSyncOptions()
    {
        var section = GetSection("SYNC");
        var formsRaw = GetValue(section, "default_forms", string.Empty);
        var forms = formsRaw
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(static x => !string.IsNullOrWhiteSpace(x))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();

        return new SyncRuntimeOptions
        {
            AutoSync = ParseBool(GetValue(section, "auto_sync", "false"), false),
            IntervalMinutes = ParseInt(GetValue(section, "sync_interval", "60"), 60),
            SyncType = ParseSyncType(GetValue(section, "sync_type", "incremental")),
            DefaultForms = forms,
            FetchConcurrency = ParseInt(GetValue(section, "fetch_concurrency", "1"), 1),
            TableConcurrency = ParseInt(GetValue(section, "table_concurrency", "1"), 1),
            TimeWindowDays = ParseInt(GetValue(section, "time_window_days", "30"), 30),
            FullStartDate = GetValue(section, "full_start_date", "2000-01-01"),
        };
    }

    public IReadOnlyDictionary<string, string> GetTableMappings()
    {
        EnsureMappingsLoaded();
        return _cachedTableMappings!;
    }

    public IReadOnlyDictionary<string, string> GetInsertMethodMappings()
    {
        EnsureMappingsLoaded();
        return _cachedInsertMethodMappings!;
    }

    public IReadOnlyDictionary<string, FormQueryOptions> GetFormQueries()
    {
        if (_cachedFormQueries is not null)
        {
            return _cachedFormQueries;
        }

        if (File.Exists(_formQueriesPath))
        {
            try
            {
                var json = File.ReadAllText(_formQueriesPath, Encoding.UTF8);
                using var doc = JsonDocument.Parse(json);
                var map = new Dictionary<string, FormQueryOptions>(StringComparer.OrdinalIgnoreCase);
                foreach (var formNode in doc.RootElement.EnumerateObject())
                {
                    if (formNode.Value.ValueKind != JsonValueKind.Object)
                    {
                        continue;
                    }

                    map[formNode.Name] = BuildFormQueryOptions(formNode.Name, formNode.Value);
                }

                if (map.Count > 0)
                {
                    _cachedFormQueries = map;
                    return _cachedFormQueries;
                }
            }
            catch
            {
                // Fallback below.
            }
        }

        var mappings = GetTableMappings();
        var fallbackMap = new Dictionary<string, FormQueryOptions>(StringComparer.OrdinalIgnoreCase);
        foreach (var formName in mappings.Keys)
        {
            var formId = FormIdFallback.TryGetValue(formName, out var knownFormId) ? knownFormId : formName;
            fallbackMap[formName] = new FormQueryOptions
            {
                FormId = formId,
                FieldKeys = string.Empty,
                FilterString = string.Empty,
                OrderString = string.Empty,
                TopRowCount = 0,
                StartRow = 0,
                Limit = 0,
                SubSystemId = string.Empty,
            };
        }

        _cachedFormQueries = fallbackMap;
        return _cachedFormQueries;
    }

    public string GetIncrementalField(string key)
    {
        if (string.IsNullOrWhiteSpace(key))
        {
            return string.Empty;
        }

        var section = GetSection("INCREMENTAL_FIELDS");
        return GetValue(section, key, string.Empty).Trim();
    }

    private void EnsureMappingsLoaded()
    {
        if (_cachedTableMappings is not null && _cachedInsertMethodMappings is not null)
        {
            return;
        }

        var tableMappings = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var methodMappings = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        if (File.Exists(_tableMappingsPath))
        {
            try
            {
                var json = File.ReadAllText(_tableMappingsPath, Encoding.UTF8);
                using var doc = JsonDocument.Parse(json);
                foreach (var item in doc.RootElement.EnumerateObject())
                {
                    if (item.Value.ValueKind != JsonValueKind.Object)
                    {
                        continue;
                    }

                    var table = item.Value.TryGetProperty("table", out var tableProp)
                        ? tableProp.GetString()
                        : null;
                    var insertMethod = item.Value.TryGetProperty("insert_method", out var methodProp)
                        ? methodProp.GetString()
                        : null;

                    if (!string.IsNullOrWhiteSpace(table))
                    {
                        tableMappings[item.Name] = table;
                    }

                    if (!string.IsNullOrWhiteSpace(insertMethod))
                    {
                        methodMappings[item.Name] = insertMethod;
                    }
                }
            }
            catch
            {
                // Fall back to hardcoded defaults.
            }
        }

        if (tableMappings.Count == 0)
        {
            foreach (var pair in FallbackTableMappings)
            {
                tableMappings[pair.Key] = pair.Value;
            }
        }

        _cachedTableMappings = tableMappings;
        _cachedInsertMethodMappings = methodMappings;
    }

    private static string ResolveConfigPath(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
        {
            return ResolveConfigPath("config.ini");
        }

        if (Path.IsPathRooted(input))
        {
            return input;
        }

        var fromWorkingDir = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), input));
        if (File.Exists(fromWorkingDir))
        {
            return fromWorkingDir;
        }

        var fromAppDir = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, input));
        return fromAppDir;
    }

    private static string ResolveTableMappingsPath(string configPath)
    {
        var configDir = Path.GetDirectoryName(configPath) ?? Directory.GetCurrentDirectory();
        var candidates = new[]
        {
            Path.Combine(configDir, "tables.json"),
            Path.Combine(configDir, "src", "config", "tables.json"),
            Path.GetFullPath(Path.Combine(configDir, "..", "src", "config", "tables.json")),
        };

        return candidates.FirstOrDefault(File.Exists) ?? candidates[1];
    }

    private static string ResolveFormQueriesPath(string configPath)
    {
        var configDir = Path.GetDirectoryName(configPath) ?? Directory.GetCurrentDirectory();
        var candidates = new[]
        {
            Path.Combine(configDir, "form-queries.json"),
            Path.Combine(configDir, "src", "config", "form-queries.json"),
            Path.Combine(configDir, "dotnet", "form-queries.json"),
            Path.GetFullPath(Path.Combine(configDir, "..", "src", "config", "form-queries.json")),
            Path.GetFullPath(Path.Combine(configDir, "..", "dotnet", "form-queries.json")),
        };

        return candidates.FirstOrDefault(File.Exists) ?? candidates[1];
    }

    private void LoadIni(string path)
    {
        if (!File.Exists(path))
        {
            throw new FileNotFoundException($"Config file not found: {path}");
        }

        var currentSection = "DEFAULT";
        _sections[currentSection] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var raw in File.ReadLines(path, Encoding.UTF8))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#') || line.StartsWith(';'))
            {
                continue;
            }

            if (line.StartsWith('[') && line.EndsWith(']'))
            {
                currentSection = line[1..^1].Trim();
                if (!_sections.ContainsKey(currentSection))
                {
                    _sections[currentSection] = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                }
                continue;
            }

            var idx = line.IndexOf('=');
            if (idx <= 0)
            {
                continue;
            }

            var key = line[..idx].Trim();
            var value = line[(idx + 1)..].Trim();
            _sections[currentSection][key] = value;
        }
    }

    private Dictionary<string, string> GetSection(string sectionName)
    {
        return _sections.TryGetValue(sectionName, out var section)
            ? section
            : new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    }

    private static string GetValue(Dictionary<string, string> section, string key, string defaultValue = "")
    {
        return section.TryGetValue(key, out var value) ? value : defaultValue;
    }

    private static bool ParseBool(string raw, bool defaultValue)
    {
        if (string.IsNullOrWhiteSpace(raw))
        {
            return defaultValue;
        }

        return raw.Trim().ToLowerInvariant() switch
        {
            "true" or "1" or "yes" or "y" => true,
            "false" or "0" or "no" or "n" => false,
            _ => defaultValue,
        };
    }

    private static int ParseInt(string raw, int defaultValue)
    {
        return int.TryParse(raw, out var value) ? value : defaultValue;
    }

    private static double ParseDouble(string raw, double defaultValue)
    {
        return double.TryParse(raw, out var value) ? value : defaultValue;
    }

    private static SyncType ParseSyncType(string value)
    {
        return value.Trim().ToLowerInvariant() switch
        {
            "full" => SyncType.Full,
            "complete" or "reset" => SyncType.Complete,
            _ => SyncType.Incremental,
        };
    }

    private static readonly Dictionary<string, string> FallbackTableMappings = new(StringComparer.OrdinalIgnoreCase)
    {
        ["销售订单"] = "saleorder",
        ["销售出库单"] = "sal_outstock",
        ["销售退货单"] = "sal_returnstock",
        ["预测订单"] = "pln_forecast",
        ["发货通知单"] = "sal_deliverynotice",
        ["生产入库单"] = "prd_instock",
        ["生产订单主表"] = "prd_mo",
        ["生产订单明细"] = "prd_moentry",
        ["客户资料"] = "customer",
        ["生产用料清单主表"] = "prd_ppbom",
        ["生产用料清单明细表"] = "prd_ppbomentry",
        ["即时库存"] = "stk_inventory",
        ["物料"] = "bd_material",
        ["物料清单"] = "eng_bom",
        ["物料清单子项"] = "eng_bomchild",
        ["仓库"] = "bd_stock",
        ["采购订单"] = "PUR_PurchaseOrder",
        ["委外订单"] = "sub_subreqorder",
        ["科目余额表"] = "GL_RPT_AccountBalance",
        ["应付单"] = "AP_Payable",
    };

    private static readonly Dictionary<string, string> FormIdFallback = new(StringComparer.OrdinalIgnoreCase)
    {
        ["销售订单"] = "SAL_SaleOrder",
        ["销售出库单"] = "SAL_OUTSTOCK",
        ["销售退货单"] = "SAL_RETURNSTOCK",
        ["预测订单"] = "PLN_FORECAST",
        ["发货通知单"] = "SAL_DELIVERYNOTICE",
        ["生产入库单"] = "PRD_INSTOCK",
        ["生产订单主表"] = "PRD_MO",
        ["生产订单明细"] = "PRD_MO",
        ["客户资料"] = "BD_Customer",
        ["生产用料清单主表"] = "PRD_PPBOM",
        ["生产用料清单明细表"] = "PRD_PPBOM",
        ["即时库存"] = "STK_Inventory",
        ["物料"] = "BD_MATERIAL",
        ["物料清单"] = "ENG_BOM",
        ["物料清单子项"] = "ENG_BOM",
        ["仓库"] = "BD_STOCK",
        ["采购订单"] = "PUR_PurchaseOrder",
        ["委外订单"] = "SUB_SUBREQORDER",
        ["科目余额表"] = "GL_RPT_AccountBalance",
        ["应付单"] = "AP_Payable",
    };

    private static string GetJsonString(JsonElement element, string propertyName)
    {
        if (element.TryGetProperty(propertyName, out var node) && node.ValueKind == JsonValueKind.String)
        {
            return node.GetString() ?? string.Empty;
        }

        return string.Empty;
    }

    private static int GetJsonInt(JsonElement element, string propertyName, int defaultValue)
    {
        if (element.TryGetProperty(propertyName, out var node))
        {
            if (node.ValueKind == JsonValueKind.Number && node.TryGetInt32(out var number))
            {
                return number;
            }

            if (node.ValueKind == JsonValueKind.String &&
                int.TryParse(node.GetString(), out var parsed))
            {
                return parsed;
            }
        }

        return defaultValue;
    }

    private static FormQueryOptions BuildFormQueryOptions(string formName, JsonElement element)
    {
        var formId = GetJsonString(element, "FormId");
        if (string.IsNullOrWhiteSpace(formId))
        {
            formId = FormIdFallback.TryGetValue(formName, out var knownFormId) ? knownFormId : formName;
        }

        var extra = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
        foreach (var property in element.EnumerateObject())
        {
            if (KnownFormQueryProperties.Contains(property.Name))
            {
                continue;
            }

            extra[property.Name] = JsonToObject(property.Value);
        }

        return new FormQueryOptions
        {
            FormId = formId,
            FieldKeys = GetJsonString(element, "FieldKeys"),
            FilterString = GetJsonValue(element, "FilterString", string.Empty),
            OrderString = GetJsonString(element, "OrderString"),
            TopRowCount = GetJsonInt(element, "TopRowCount", 0),
            StartRow = GetJsonInt(element, "StartRow", 0),
            Limit = GetJsonInt(element, "Limit", 0),
            SubSystemId = GetJsonString(element, "SubSystemId"),
            ExtraParameters = extra,
        };
    }

    private static object? GetJsonValue(JsonElement element, string propertyName, object? defaultValue = null)
    {
        if (element.TryGetProperty(propertyName, out var node))
        {
            return JsonToObject(node);
        }

        return defaultValue;
    }

    private static object? JsonToObject(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Number when element.TryGetInt64(out var number) => number,
            JsonValueKind.Number when element.TryGetDecimal(out var decimalNumber) => decimalNumber,
            JsonValueKind.Number when element.TryGetDouble(out var doubleNumber) => doubleNumber,
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            JsonValueKind.Undefined => null,
            JsonValueKind.Array => element.EnumerateArray().Select(JsonToObject).ToArray(),
            JsonValueKind.Object => element.EnumerateObject().ToDictionary(
                static x => x.Name,
                static x => JsonToObject(x.Value),
                StringComparer.OrdinalIgnoreCase),
            _ => element.ToString(),
        };
    }

    private static readonly HashSet<string> KnownFormQueryProperties = new(StringComparer.OrdinalIgnoreCase)
    {
        "FormId",
        "FieldKeys",
        "FilterString",
        "OrderString",
        "TopRowCount",
        "StartRow",
        "Limit",
        "SubSystemId",
    };
}
