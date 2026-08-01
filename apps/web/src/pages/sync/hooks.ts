import { useMutation, useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useState } from 'react';
import {
  createRun,
  listForms,
  listRunEvents,
  listRuns,
} from '@/services/v1';
import type { V1Form, V1Run, V1RunEvent } from '@/services/v1';
import type { SyncStatusInfo } from './types';

/**
 * Sync 页面数据 Hook — v1 版。
 *
 * 使用 v1 API 获取表单列表和运行历史，启动同步通过 v1 createRun。
 * 状态轮询和日志暂保留旧接口（v1 尚无实时状态端点）。
 *
 * 启动同步后保存 run_id，后续轮询状态和日志都绑定该 run_id。
 */
export function useSyncPage() {
  const [activeRunId, setActiveRunId] = useState<string>('');

  // 表单列表（v1）
  const formsReq = useQuery({
    queryKey: ['v1', 'forms'],
    queryFn: listForms,
  });
  const forms: V1Form[] = formsReq.data ?? [];

  // 同步状态（轮询 3s，绑定 run_id）— 暂用旧接口
  const statusReq = useQuery({
    queryKey: ['sync', 'status', activeRunId],
    queryFn: () => import('@/services/api').then(m => m.getSyncStatus(activeRunId || undefined)),
    enabled: Boolean(activeRunId),
    refetchInterval: 3000,
  });
  const rawStatus = statusReq.data?.data;

  // 首次进入页面时若已有正在运行的任务，自动接管其 run_id
  useEffect(() => {
    if (!activeRunId && rawStatus?.run_id) {
      setActiveRunId(rawStatus.run_id);
    }
  }, [activeRunId, rawStatus?.run_id]);

  const status: SyncStatusInfo = {
    run_id: rawStatus?.run_id || '',
    status: (rawStatus?.status || 'idle') as SyncStatusInfo['status'],
    message: rawStatus?.message || '',
    progress: rawStatus?.progress ?? 0,
    current_form: rawStatus?.current_form || '',
    elapsed_seconds: rawStatus?.elapsed_seconds ?? 0,
    form_stats: rawStatus?.form_stats || [],
  };

  // 日志（同步中轮询 2s，否则 10s）— v1 运行事件
  const logsReq = useQuery({
    queryKey: ['v1', 'run', 'events', activeRunId],
    queryFn: () => listRunEvents(activeRunId),
    enabled: Boolean(activeRunId),
    refetchInterval: status.status === 'running' ? 2000 : 10000,
  });
  const logs: V1RunEvent[] = logsReq.data || [];

  // 上次同步结果（v1）
  const lastRunReq = useQuery({
    queryKey: ['v1', 'runs', 'last'],
    queryFn: () => listRuns({ page_size: 1 }),
  });
  const lastRun: V1Run | undefined = lastRunReq.data?.data[0];

  // 启动同步 — v1 createRun，成功后保存 run_id
  const startMutation = useMutation({ mutationFn: createRun });
  const doStartSync = useCallback(
    async (params: { forms?: string[]; sync_type: string }) => {
      const run = await startMutation.mutateAsync(params);
      if (run.run_id) {
        setActiveRunId(run.run_id);
      }
      return run;
    },
    [startMutation],
  );

  // 停止同步 — 暂用旧接口
  const doStopSync = useCallback(
    async (runId: string) => {
      await import('@/services/api').then(m => m.stopSync(runId));
      setActiveRunId('');
    },
    [],
  );

  return {
    forms,
    formsLoading: formsReq.isPending,
    status,
    logs,
    logsLoading: logsReq.isPending,
    lastRun,
    lastRunLoading: lastRunReq.isPending,
    startSync: doStartSync,
    stopSync: doStopSync,
    starting: startMutation.isPending,
    refreshLogs: logsReq.refetch,
  };
}
