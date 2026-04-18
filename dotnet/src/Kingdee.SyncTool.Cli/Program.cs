using Kingdee.SyncTool.Application.Services;
using Kingdee.SyncTool.Domain.Contracts;
using Kingdee.SyncTool.Domain.Enums;
using Kingdee.SyncTool.Domain.Models;
using Kingdee.SyncTool.Infrastructure.Api;
using Kingdee.SyncTool.Infrastructure.Configuration;
using Kingdee.SyncTool.Infrastructure.Data;
using System.Collections;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Kingdee.SyncTool.Cli;

internal static class Program
{
    private static async Task<int> Main(string[] args)
    {
        if (args.Length == 0 || HasFlag(args, "--help") || HasFlag(args, "-h"))
        {
            PrintUsage();
            return 0;
        }

        var configPath = GetOption(args, "--config") ?? ResolveDefaultConfigPath();
        if (!File.Exists(configPath))
        {
            Console.Error.WriteLine($"Config not found: {configPath}");
            return 2;
        }

        var configProvider = new IniConfigProvider(configPath);
        using var apiClient = new KingdeeApiClient(configProvider);

        var logsDir = Path.Combine(Path.GetDirectoryName(configPath) ?? Directory.GetCurrentDirectory(), "logs");
        var dryRun = ParseBool(GetOption(args, "--dry-run"), defaultValue: true);
        IDataStore dataStore = dryRun
            ? new DryRunDataStore(Path.Combine(logsDir, "dotnet-sync.log"))
            : new SqlServerDataStore(configProvider.GetDatabaseOptions());

        var syncService = new SyncService(apiClient, dataStore, configProvider);
        var scheduler = new SchedulerService(syncService);

        syncService.ProgressChanged += static (message, progress) =>
        {
            Console.WriteLine($"[{DateTimeOffset.Now:HH:mm:ss}] {progress,3}% {message}");
        };

        scheduler.SyncCompleted += static result =>
        {
            Console.WriteLine(
                $"[scheduler] run={result.RunId} status={result.Status} inserted={result.TotalInsertedCount} msg={result.Message}");
        };

        var command = args[0].ToLowerInvariant();
        return command switch
        {
            "sync" => await RunSyncAsync(args, syncService).ConfigureAwait(false),
            "check" => await RunCheckAsync(syncService).ConfigureAwait(false),
            "schedule" => await RunScheduleAsync(args, scheduler).ConfigureAwait(false),
            "parity" => await RunParityAsync(args, apiClient, configProvider).ConfigureAwait(false),
            _ => UnknownCommand(command),
        };
    }

    private static async Task<int> RunSyncAsync(string[] args, SyncService syncService)
    {
        var syncType = ParseSyncType(GetOption(args, "--mode") ?? "incremental");
        var forms = ParseForms(GetOption(args, "--tables"));

        var request = new SyncRequest
        {
            Forms = forms,
            Type = syncType,
            UseDefaultFormsWhenEmpty = forms.Count == 0,
        };

        Console.WriteLine("Starting sync...");
        var result = await syncService.ExecuteAsync(request).ConfigureAwait(false);
        Console.WriteLine(
            $"Finished. run={result.RunId} status={result.Status} source={result.TotalSourceCount} inserted={result.TotalInsertedCount}");
        Console.WriteLine(result.Message);
        return result.Status == SyncStatus.Failed ? 1 : 0;
    }

    private static async Task<int> RunCheckAsync(SyncService syncService)
    {
        var ok = await syncService.TestConnectionsAsync().ConfigureAwait(false);
        Console.WriteLine(ok ? "Connection check passed." : "Connection check failed.");
        return ok ? 0 : 1;
    }

    private static async Task<int> RunScheduleAsync(string[] args, SchedulerService scheduler)
    {
        var intervalRaw = GetOption(args, "--interval") ?? "60";
        if (!int.TryParse(intervalRaw, out var interval) || interval <= 0)
        {
            Console.Error.WriteLine("Invalid --interval value.");
            return 2;
        }

        var syncType = ParseSyncType(GetOption(args, "--mode") ?? "incremental");
        var forms = ParseForms(GetOption(args, "--tables"));
        var request = new SyncRequest
        {
            Forms = forms,
            Type = syncType,
            UseDefaultFormsWhenEmpty = forms.Count == 0,
        };

        scheduler.Configure(TimeSpan.FromMinutes(interval), request);

        using var cts = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            cts.Cancel();
        };

        Console.WriteLine("Scheduler started. Press Ctrl+C to stop.");
        await scheduler.StartAsync(cts.Token).ConfigureAwait(false);

        try
        {
            await Task.Delay(Timeout.Infinite, cts.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // Expected on Ctrl+C.
        }
        finally
        {
            await scheduler.StopAsync(CancellationToken.None).ConfigureAwait(false);
            Console.WriteLine("Scheduler stopped.");
        }

        return 0;
    }

    private static async Task<int> RunParityAsync(
        string[] args,
        IApiClient apiClient,
        IConfigProvider configProvider)
    {
        var syncType = ParseSyncType(GetOption(args, "--mode") ?? "full");
        var startRow = ParseNonNegativeInt(GetOption(args, "--start-row"), 0);
        var defaultLimit = configProvider.GetKingdeeOptions().PageSize > 0
            ? configProvider.GetKingdeeOptions().PageSize
            : 20000;
        var limit = ParseNonNegativeInt(GetOption(args, "--limit"), defaultLimit);

        var forms = ParseForms(GetOption(args, "--tables"));
        if (forms.Count == 0)
        {
            var defaults = configProvider.GetSyncOptions().DefaultForms;
            forms = defaults.Count > 0
                ? defaults
                    .Where(static x => !string.IsNullOrWhiteSpace(x))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToArray()
                : configProvider.GetTableMappings().Keys
                    .Where(static x => !string.IsNullOrWhiteSpace(x))
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToArray();
        }

        if (forms.Count == 0)
        {
            Console.Error.WriteLine("No forms available for parity check.");
            return 2;
        }

        var authenticated = await apiClient.EnsureAuthenticatedAsync().ConfigureAwait(false);
        if (!authenticated)
        {
            Console.Error.WriteLine("Failed to authenticate with Kingdee API.");
            return 1;
        }

        var templates = configProvider.GetFormQueries();
        var formResults = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
        foreach (var form in forms)
        {
            var rows = await apiClient.QueryFormAsync(
                    form,
                    syncType,
                    filterString: null,
                    startRow: startRow,
                    limit: limit,
                    cancellationToken: CancellationToken.None)
                .ConfigureAwait(false);

            var formId = templates.TryGetValue(form, out var template) && !string.IsNullOrWhiteSpace(template.FormId)
                ? template.FormId
                : form;

            formResults[form] = new Dictionary<string, object?>
            {
                ["formName"] = form,
                ["formId"] = formId,
                ["rowCount"] = rows.Count,
                ["rowHash"] = ComputeRowsHash(rows),
                ["sampleRowHashes"] = ComputeSampleRowHashes(rows, 3),
            };

            Console.WriteLine($"[parity] {form} rows={rows.Count}");
        }

        var report = new Dictionary<string, object?>
        {
            ["generatedAt"] = DateTimeOffset.Now.ToString("O"),
            ["mode"] = syncType.ToString().ToLowerInvariant(),
            ["startRow"] = startRow,
            ["limit"] = limit,
            ["forms"] = forms,
            ["results"] = formResults,
        };

        var json = JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true });
        var outputPath = GetOption(args, "--output");
        if (!string.IsNullOrWhiteSpace(outputPath))
        {
            var fullPath = Path.IsPathRooted(outputPath)
                ? outputPath
                : Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), outputPath));
            var dir = Path.GetDirectoryName(fullPath);
            if (!string.IsNullOrWhiteSpace(dir))
            {
                Directory.CreateDirectory(dir);
            }

            await File.WriteAllTextAsync(fullPath, json, Encoding.UTF8).ConfigureAwait(false);
            Console.WriteLine($"Parity report saved: {fullPath}");
        }
        else
        {
            Console.WriteLine(json);
        }

        return 0;
    }

    private static string ResolveDefaultConfigPath()
    {
        var fromCwd = Path.Combine(Directory.GetCurrentDirectory(), "config.ini");
        if (File.Exists(fromCwd))
        {
            return Path.GetFullPath(fromCwd);
        }

        return Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "config.ini"));
    }

    private static bool HasFlag(IEnumerable<string> args, string name)
    {
        return args.Any(arg => string.Equals(arg, name, StringComparison.OrdinalIgnoreCase));
    }

    private static string? GetOption(IReadOnlyList<string> args, string name)
    {
        for (var i = 0; i < args.Count; i++)
        {
            var item = args[i];
            if (string.Equals(item, name, StringComparison.OrdinalIgnoreCase))
            {
                if (i + 1 < args.Count)
                {
                    return args[i + 1];
                }
                return null;
            }

            if (item.StartsWith(name + "=", StringComparison.OrdinalIgnoreCase))
            {
                return item[(name.Length + 1)..];
            }
        }

        return null;
    }

    private static IReadOnlyList<string> ParseForms(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
        {
            return Array.Empty<string>();
        }

        return raw
            .Split([',', ';', '|'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(static x => !string.IsNullOrWhiteSpace(x))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static SyncType ParseSyncType(string raw)
    {
        return raw.Trim().ToLowerInvariant() switch
        {
            "full" => SyncType.Full,
            "complete" or "reset" => SyncType.Complete,
            _ => SyncType.Incremental,
        };
    }

    private static int ParseNonNegativeInt(string? raw, int defaultValue)
    {
        if (string.IsNullOrWhiteSpace(raw))
        {
            return defaultValue;
        }

        return int.TryParse(raw, out var value) && value >= 0 ? value : defaultValue;
    }

    private static string ComputeRowsHash(IReadOnlyList<IDictionary<string, object?>> rows)
    {
        var canonicalRows = rows
            .Select(CanonicalizeRow)
            .OrderBy(static x => x, StringComparer.Ordinal)
            .ToArray();
        var payload = string.Join('\n', canonicalRows);
        return ComputeSha256(payload);
    }

    private static IReadOnlyList<string> ComputeSampleRowHashes(
        IReadOnlyList<IDictionary<string, object?>> rows,
        int take)
    {
        return rows
            .Select(CanonicalizeRow)
            .OrderBy(static x => x, StringComparer.Ordinal)
            .Take(Math.Max(0, take))
            .Select(ComputeSha256)
            .ToArray();
    }

    private static string CanonicalizeRow(IDictionary<string, object?> row)
    {
        var pairs = row
            .OrderBy(static x => x.Key, StringComparer.OrdinalIgnoreCase)
            .Select(x => $"{x.Key}={NormalizeValue(x.Value)}");
        return string.Join('|', pairs);
    }

    private static string NormalizeValue(object? value)
    {
        if (value is null)
        {
            return "null";
        }

        if (value is bool boolValue)
        {
            return boolValue ? "true" : "false";
        }

        if (value is DateTime dateTime)
        {
            return dateTime.ToString("O", CultureInfo.InvariantCulture);
        }

        if (value is DateTimeOffset dateTimeOffset)
        {
            return dateTimeOffset.ToString("O", CultureInfo.InvariantCulture);
        }

        if (value is IDictionary<string, object?> map)
        {
            var items = map
                .OrderBy(static x => x.Key, StringComparer.OrdinalIgnoreCase)
                .Select(x => $"{x.Key}:{NormalizeValue(x.Value)}");
            return "{" + string.Join(",", items) + "}";
        }

        if (value is IEnumerable enumerable && value is not string)
        {
            var values = new List<string>();
            foreach (var item in enumerable)
            {
                values.Add(NormalizeValue(item));
            }
            return "[" + string.Join(",", values) + "]";
        }

        if (value is IFormattable formattable)
        {
            return formattable.ToString(null, CultureInfo.InvariantCulture) ?? string.Empty;
        }

        return value.ToString() ?? string.Empty;
    }

    private static string ComputeSha256(string raw)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static int UnknownCommand(string command)
    {
        Console.Error.WriteLine($"Unknown command: {command}");
        PrintUsage();
        return 2;
    }

    private static void PrintUsage()
    {
        Console.WriteLine("Kingdee.SyncTool (.NET migration bootstrap)");
        Console.WriteLine();
        Console.WriteLine("Usage:");
        Console.WriteLine("  Kingdee.SyncTool.Cli sync --mode incremental --tables saleorder,sal_outstock [--config path]");
        Console.WriteLine("  Kingdee.SyncTool.Cli check [--config path]");
        Console.WriteLine("  Kingdee.SyncTool.Cli schedule --interval 60 --mode incremental [--tables ...] [--config path]");
        Console.WriteLine("  Kingdee.SyncTool.Cli parity --mode full --tables saleorder,sal_outstock [--start-row 0] [--limit 20000] [--output path] [--config path]");
        Console.WriteLine("  add --dry-run false to use SqlServerDataStore");
        Console.WriteLine();
        Console.WriteLine("Notes:");
        Console.WriteLine("  1) Default datastore is DryRunDataStore; use --dry-run false to use SqlServerDataStore.");
        Console.WriteLine("  2) parity command exports row-count/hash baseline for Python/.NET migration acceptance.");
        Console.WriteLine("  3) form-queries are loaded from shared JSON config.");
    }

    private static bool ParseBool(string? raw, bool defaultValue)
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
}
