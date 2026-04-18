using Kingdee.SyncTool.Domain.Contracts;
using Kingdee.SyncTool.Domain.Enums;
using Kingdee.SyncTool.Domain.Models;

namespace Kingdee.SyncTool.Application.Services;

public sealed class SyncService : ISyncService
{
    private readonly IApiClient _apiClient;
    private readonly IDataStore _dataStore;
    private readonly IConfigProvider _configProvider;

    public SyncService(IApiClient apiClient, IDataStore dataStore, IConfigProvider configProvider)
    {
        _apiClient = apiClient;
        _dataStore = dataStore;
        _configProvider = configProvider;
    }

    public event Action<string, int>? ProgressChanged;

    public async Task<bool> TestConnectionsAsync(CancellationToken cancellationToken = default)
    {
        var apiOk = await _apiClient.TestConnectionAsync(cancellationToken).ConfigureAwait(false);
        var dbOk = await _dataStore.TestConnectionAsync(cancellationToken).ConfigureAwait(false);
        return apiOk && dbOk;
    }

    public async Task<SyncResult> ExecuteAsync(SyncRequest request, CancellationToken cancellationToken = default)
    {
        var start = DateTimeOffset.Now;
        var runId = Guid.NewGuid().ToString("N");
        var details = new Dictionary<string, FormSyncDetail>(StringComparer.OrdinalIgnoreCase);

        var result = new SyncResult
        {
            RunId = runId,
            StartTime = start,
            EndTime = start,
            Status = SyncStatus.Running,
            Message = "Sync task started.",
        };

        var forms = ResolveForms(request);
        if (forms.Count == 0)
        {
            return Complete(result, details, SyncStatus.Failed, "No forms selected for synchronization.");
        }

        var canRun = await TestConnectionsAsync(cancellationToken).ConfigureAwait(false);
        if (!canRun)
        {
            return Complete(result, details, SyncStatus.Failed, "Connection test failed.");
        }

        Notify("Connection check passed.", 5);

        var authenticated = await _apiClient.EnsureAuthenticatedAsync(cancellationToken).ConfigureAwait(false);
        if (!authenticated)
        {
            return Complete(result, details, SyncStatus.Failed, "Failed to authenticate with Kingdee API.");
        }

        Notify("Kingdee API authentication succeeded.", 10);

        var tableMappings = _configProvider.GetTableMappings();
        var kingdeeOptions = _configProvider.GetKingdeeOptions();
        var failed = 0;
        var completed = 0;

        foreach (var form in forms)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var formStart = DateTimeOffset.Now;
            Notify($"Syncing form: {form}", CalculateProgress(completed, forms.Count, 15, 90));

            if (!tableMappings.TryGetValue(form, out var tableName) || string.IsNullOrWhiteSpace(tableName))
            {
                var missingMapping = new FormSyncDetail
                {
                    FormName = form,
                    TableName = string.Empty,
                    Status = SyncStatus.Failed,
                    Message = "No table mapping found.",
                    Duration = DateTimeOffset.Now - formStart,
                };
                details[form] = missingMapping;
                failed++;
                completed++;
                continue;
            }

            try
            {
                string? filter = null;
                if (request.Type == SyncType.Incremental)
                {
                    var lastSync = await _dataStore.GetLastSyncTimeAsync(tableName, cancellationToken).ConfigureAwait(false);
                    var incrementalField = _configProvider.GetIncrementalField(tableName);
                    if (string.IsNullOrWhiteSpace(incrementalField))
                    {
                        incrementalField = _configProvider.GetIncrementalField(form);
                    }

                    if (string.IsNullOrWhiteSpace(incrementalField))
                    {
                        incrementalField = "FModifyDate";
                    }

                    filter = BuildIncrementalFilter(lastSync, incrementalField);
                }

                var rows = await _apiClient
                    .QueryFormAsync(
                        form,
                        request.Type,
                        filter,
                        startRow: 0,
                        limit: kingdeeOptions.PageSize > 0 ? kingdeeOptions.PageSize : 20000,
                        cancellationToken: cancellationToken)
                    .ConfigureAwait(false);

                var sourceCount = rows.Count;
                var inserted = 0;
                if (sourceCount > 0)
                {
                    inserted = await _dataStore
                        .UpsertBatchAsync(tableName, rows, cancellationToken)
                        .ConfigureAwait(false);
                }

                var status = inserted == sourceCount ? SyncStatus.Success : SyncStatus.Partial;
                if (status != SyncStatus.Success)
                {
                    failed++;
                }

                var formDetail = new FormSyncDetail
                {
                    FormName = form,
                    TableName = tableName,
                    Status = status,
                    SourceCount = sourceCount,
                    InsertedCount = inserted,
                    UpdatedCount = 0,
                    Message = status == SyncStatus.Success
                        ? $"Synchronized {inserted} record(s)."
                        : $"Source {sourceCount}, synchronized {inserted}.",
                    Duration = DateTimeOffset.Now - formStart,
                };
                details[form] = formDetail;

                result.TotalSourceCount += sourceCount;
                result.TotalInsertedCount += inserted;

                await _dataStore.LogSyncOperationAsync(
                    tableName: tableName,
                    syncType: request.Type.ToString().ToLowerInvariant(),
                    status: formDetail.Status.ToString().ToLowerInvariant(),
                    recordCount: inserted,
                    message: formDetail.Message,
                    startTime: formStart,
                    endTime: DateTimeOffset.Now,
                    cancellationToken: cancellationToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                failed++;
                details[form] = new FormSyncDetail
                {
                    FormName = form,
                    TableName = tableName,
                    Status = SyncStatus.Failed,
                    Message = ex.Message,
                    Duration = DateTimeOffset.Now - formStart,
                };

                await _dataStore.LogSyncOperationAsync(
                    tableName: tableName,
                    syncType: request.Type.ToString().ToLowerInvariant(),
                    status: "failed",
                    recordCount: 0,
                    message: ex.Message,
                    startTime: formStart,
                    endTime: DateTimeOffset.Now,
                    cancellationToken: cancellationToken).ConfigureAwait(false);
            }

            completed++;
            Notify($"Completed form: {form} ({completed}/{forms.Count})", CalculateProgress(completed, forms.Count, 15, 95));
        }

        if (!kingdeeOptions.KeepSessionAlive)
        {
            // In non-auto mode, follow current Python behavior and close session.
            await _apiClient.LogoutAsync(cancellationToken).ConfigureAwait(false);
        }

        if (failed == 0)
        {
            return Complete(result, details, SyncStatus.Success, "Synchronization completed successfully.");
        }

        if (failed == forms.Count)
        {
            return Complete(result, details, SyncStatus.Failed, "All forms failed.");
        }

        return Complete(result, details, SyncStatus.Partial, "Synchronization completed with partial failures.");
    }

    private IReadOnlyList<string> ResolveForms(SyncRequest request)
    {
        if (request.Forms.Count > 0)
        {
            return request.Forms
                .Where(static x => !string.IsNullOrWhiteSpace(x))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
        }

        if (!request.UseDefaultFormsWhenEmpty)
        {
            return Array.Empty<string>();
        }

        var syncOptions = _configProvider.GetSyncOptions();
        if (syncOptions.DefaultForms.Count > 0)
        {
            return syncOptions.DefaultForms
                .Where(static x => !string.IsNullOrWhiteSpace(x))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
        }

        return _configProvider.GetTableMappings().Keys
            .Where(static x => !string.IsNullOrWhiteSpace(x))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static string? BuildIncrementalFilter(DateTimeOffset? lastSyncTime, string incrementalField)
    {
        if (!lastSyncTime.HasValue)
        {
            return null;
        }

        var ts = lastSyncTime.Value.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss");
        return $"{incrementalField} > '{ts}'";
    }

    private void Notify(string message, int progress)
    {
        ProgressChanged?.Invoke(message, Math.Clamp(progress, 0, 100));
    }

    private static int CalculateProgress(int completed, int total, int startPercent, int endPercent)
    {
        if (total <= 0)
        {
            return endPercent;
        }

        var span = endPercent - startPercent;
        return startPercent + (int)Math.Round((double)completed / total * span);
    }

    private SyncResult Complete(
        SyncResult result,
        IReadOnlyDictionary<string, FormSyncDetail> details,
        SyncStatus status,
        string message)
    {
        result.Status = status;
        result.Message = message;
        result.EndTime = DateTimeOffset.Now;
        result.Details = details;
        Notify(message, 100);
        return result;
    }
}
