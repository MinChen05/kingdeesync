using Kingdee.SyncTool.Domain.Contracts;
using Kingdee.SyncTool.Domain.Enums;
using Kingdee.SyncTool.Domain.Models;

namespace Kingdee.SyncTool.Application.Services;

public sealed class SchedulerService : ISchedulerService, IDisposable
{
    private readonly ISyncService _syncService;
    private readonly SemaphoreSlim _gate = new(1, 1);

    private CancellationTokenSource? _schedulerCts;
    private Task? _schedulerTask;

    private TimeSpan _interval = TimeSpan.FromMinutes(60);
    private SyncRequest _request = new();
    private SchedulerState _state = SchedulerState.Stopped;
    private DateTimeOffset? _lastExecution;
    private DateTimeOffset? _nextExecution;

    public SchedulerService(ISyncService syncService)
    {
        _syncService = syncService;
    }

    public event Action<SyncResult>? SyncCompleted;

    public SchedulerStatusInfo Status => new()
    {
        Status = _state,
        Interval = _interval,
        LastExecutionTime = _lastExecution,
        NextExecutionTime = _nextExecution,
        Message = _state switch
        {
            SchedulerState.Running => "Scheduler is running.",
            SchedulerState.Paused => "Scheduler is paused.",
            _ => "Scheduler is stopped.",
        }
    };

    public void Configure(TimeSpan interval, SyncRequest request)
    {
        if (interval <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(interval), "Interval must be greater than zero.");
        }

        _interval = interval;
        _request = request;
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_state == SchedulerState.Running)
            {
                return;
            }

            _schedulerCts?.Cancel();
            _schedulerCts?.Dispose();
            _schedulerCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

            _state = SchedulerState.Running;
            _schedulerTask = Task.Run(() => SchedulerLoopAsync(_schedulerCts.Token), _schedulerCts.Token);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task StopAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_state == SchedulerState.Stopped)
            {
                return;
            }

            _state = SchedulerState.Stopped;
            _nextExecution = null;

            if (_schedulerCts is not null)
            {
                await _schedulerCts.CancelAsync().ConfigureAwait(false);
            }
        }
        finally
        {
            _gate.Release();
        }

        if (_schedulerTask is not null)
        {
            try
            {
                await _schedulerTask.ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                // Ignore cancellation.
            }
        }
    }

    private async Task SchedulerLoopAsync(CancellationToken cancellationToken)
    {
        using var timer = new PeriodicTimer(_interval);

        // Keep behavior aligned with Python scheduler: trigger once immediately.
        await ExecuteScheduledSyncAsync(cancellationToken).ConfigureAwait(false);
        _nextExecution = DateTimeOffset.Now.Add(_interval);

        while (_state == SchedulerState.Running && !cancellationToken.IsCancellationRequested)
        {
            var moved = await timer.WaitForNextTickAsync(cancellationToken).ConfigureAwait(false);
            if (!moved || _state != SchedulerState.Running)
            {
                break;
            }

            await ExecuteScheduledSyncAsync(cancellationToken).ConfigureAwait(false);
            _nextExecution = DateTimeOffset.Now.Add(_interval);
        }
    }

    private async Task ExecuteScheduledSyncAsync(CancellationToken cancellationToken)
    {
        _lastExecution = DateTimeOffset.Now;
        var result = await _syncService.ExecuteAsync(_request, cancellationToken).ConfigureAwait(false);
        SyncCompleted?.Invoke(result);
    }

    public void Dispose()
    {
        _schedulerCts?.Cancel();
        _schedulerCts?.Dispose();
        _gate.Dispose();
    }
}
