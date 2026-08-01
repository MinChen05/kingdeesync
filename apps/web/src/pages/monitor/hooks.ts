import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { getDiagnostics, getOverview, listRuns } from '@/services/v1';
import type { V1Diagnostics, V1Run } from '@/services/v1';
import type { FormStat } from '@/types/form';
import type { DiagInfo, StatsSummary } from './types';

const DEFAULT_STATS: StatsSummary = {
  total_runs: 0,
  success_runs: 0,
  failed_runs: 0,
  partial_runs: 0,
  total_records: 0,
  success_records: 0,
  failed_records: 0,
  avg_duration_sec: 0,
  success_rate: 0,
  period_days: 30,
};

/**
 * monitor 页面数据 Hook — v1 版。
 *
 * 使用 v1 API 获取运行列表和诊断信息。
 * 统计摘要从运行列表聚合计算。
 */
export function useMonitorPage() {
  // 运行列表（用于统计和最近异常）
  const runsReq = useQuery({
    queryKey: ['v1', 'runs'],
    queryFn: () => listRuns({ page_size: 100 }),
  });

  // 从运行列表聚合统计摘要
  const stats = useMemo(() => {
    const runs = runsReq.data?.data ?? [];
    if (runs.length === 0) return DEFAULT_STATS;
    const total_runs = runs.length;
    const success_runs = runs.filter(r => r.status === 'success').length;
    const failed_runs = runs.filter(r => r.status === 'failed' || r.status === 'failed_abnormal_exit').length;
    const partial_runs = runs.filter(r => r.status === 'partial').length;
    const total_records = runs.reduce((s, r) => s + r.total_records, 0);
    const success_records = runs.reduce((s, r) => s + r.success_records, 0);
    const failed_records = runs.reduce((s, r) => s + r.failed_records, 0);
    const avg_duration_sec = runs.reduce((s, r) => s + r.duration_seconds, 0) / total_runs;
    return {
      total_runs,
      success_runs,
      failed_runs,
      partial_runs,
      total_records,
      success_records,
      failed_records,
      avg_duration_sec,
      success_rate: total_runs > 0 ? (success_runs / total_runs) * 100 : 0,
      period_days: 30,
    };
  }, [runsReq.data]);

  // 最近异常（最近 5 条失败/部分运行）
  const recentErrors = useMemo(
    () =>
      (runsReq.data?.data ?? [])
        .filter(r => r.status === 'failed' || r.status === 'failed_abnormal_exit' || r.status === 'partial')
        .slice(0, 5)
        .map(toHistoryRun),
    [runsReq.data],
  );

  // 异常表单 — 从 overview.risks 获取（后端已按 go_sync_errors 聚合）
  const overviewReq = useQuery({
    queryKey: ['v1', 'overview'],
    queryFn: getOverview,
  });
  const topErrors = useMemo(() => {
    const risks = overviewReq.data?.risks ?? [];
    return risks.map(r => ({
      form_name: r.form_name,
      failed_records: r.failure_count,
      total_runs: 0,
    })) as FormStat[];
  }, [overviewReq.data]);

  // 诊断信息（v1）
  const diagReq = useQuery({
    queryKey: ['v1', 'diagnostics'],
    queryFn: getDiagnostics,
  });
  const diagInfo: DiagInfo = {
    kingdee_api: diagReq.data?.kingdee_api,
    database: diagReq.data?.database,
    scheduler: diagReq.data?.scheduler,
    log_service: diagReq.data?.log_service,
  };

  return {
    stats,
    statsLoading: runsReq.isPending,
    recentErrors,
    recentErrorsLoading: runsReq.isPending,
    topErrors,
    topErrorsLoading: overviewReq.isPending,
    diagInfo,
    diagLoading: diagReq.isPending,
    refreshDiag: diagReq.refetch,
    refreshStats: runsReq.refetch,
  };
}

/** V1Run → HistoryRun 转换 */
function toHistoryRun(run: V1Run): {
  id: number;
  run_id: string;
  task_name: string;
  sync_type: string;
  status: string;
  start_time: string;
  end_time?: string;
  duration_seconds: number;
  total_records: number;
  success_records: number;
  failed_records: number;
  form_count: number;
  success_forms: number;
  failed_forms: number;
} {
  return {
    id: 0,
    run_id: run.run_id,
    task_name: run.sync_type,
    sync_type: run.sync_type,
    status: run.status,
    start_time: run.started_at || '',
    end_time: run.finished_at,
    duration_seconds: run.duration_seconds,
    total_records: run.total_records,
    success_records: run.success_records,
    failed_records: run.failed_records,
    form_count: run.form_count,
    success_forms: run.success_forms,
    failed_forms: run.failed_forms,
  };
}
