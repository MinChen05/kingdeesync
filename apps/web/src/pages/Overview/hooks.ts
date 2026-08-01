import { useQuery } from '@tanstack/react-query';
import { getOverview, listDataSources } from '@/services/v1';
import type {
  V1HealthItem,
  V1Overview,
  V1RiskItem,
  V1Run,
  V1TrendDay,
  V1TodayStats,
} from '@/services/v1';

/**
 * 概览页统一数据获取 Hook — v1 版。
 *
 * 后端聚合端点 GET /api/v1/overview 一次返回 today + health + trend + risks + recent_runs，
 * 将原来 7 个独立请求合并为 2 个（overview + datasources）。
 */
export function useOverviewData() {
  const overviewReq = useQuery({
    queryKey: ['overview'],
    queryFn: getOverview,
  });
  const sourcesReq = useQuery({
    queryKey: ['datasources'],
    queryFn: listDataSources,
  });

  const overview: V1Overview = overviewReq.data || EMPTY_OVERVIEW;

  return {
    today: {
      data: overview.today,
      loading: overviewReq.isPending,
      refresh: overviewReq.refetch,
    },
    status: {
      data: overview.active_run
        ? {
            run_id: overview.active_run.run_id,
            status: overview.active_run.status,
            message: overview.active_run.error_message || '',
            progress: 0,
            current_form: '',
            elapsed_seconds: overview.active_run.duration_seconds,
          }
        : IDLE_STATUS,
      loading: overviewReq.isPending,
      refresh: overviewReq.refetch,
    },
    sources: {
      data: sourcesReq.data?.map(ds => ({
        id: ds.id,
        name: ds.name,
        type: ds.type,
        status: ds.status,
      })) || [],
      loading: sourcesReq.isPending,
    },
    trend: {
      data: overview.trend,
      loading: overviewReq.isPending,
    },
    topForms: {
      data: overview.risks,
      loading: overviewReq.isPending,
    },
    health: {
      data: overview.health,
      loading: overviewReq.isPending,
    },
    recent: {
      data: overview.recent_runs.map(toRecentRun),
      loading: overviewReq.isPending,
    },
  };
}

/** 将 v1 V1Run 转换为组件兼容的 RecentRun */
function toRecentRun(run: V1Run): RecentRun {
  return {
    run_id: run.run_id,
    start_time: run.started_at || '',
    task_name: run.sync_type || '',
    form_name: `${run.form_count} 表单`,
    status: run.status,
    record_count: run.total_records,
    duration_seconds: run.duration_seconds,
  };
}

// ─── Defaults ───

const IDLE_STATUS = {
  run_id: '',
  status: 'idle',
  message: '',
  progress: 0,
  current_form: '',
  elapsed_seconds: 0,
};

const EMPTY_OVERVIEW: V1Overview = {
  today: {
    sync_count: 0,
    success_rate: 0,
    fail_count: 0,
    avg_duration: 0,
    yesterday_sync_count: 0,
    yesterday_success_rate: 0,
  },
  health: {
    kingdee_api: { status: 'unknown' },
    database: { status: 'unknown' },
    scheduler: { status: 'unknown' },
    log_service: { status: 'unknown' },
  },
  trend: [],
  risks: [],
  recent_runs: [],
};

// ─── Type aliases for components ───

export interface SyncStatusInfo {
  run_id: string;
  status: string;
  message: string;
  progress: number;
  current_form: string;
  elapsed_seconds: number;
}

export type TodayStats = V1TodayStats;

/** 健康状态 — 旧组件使用可选字段，v1 返回的是必选字段，这里用兼容类型 */
export interface HealthStatus {
  kingdee_api?: V1HealthItem;
  database?: V1HealthItem;
  scheduler?: V1HealthItem;
  log_service?: V1HealthItem;
}

export type TrendDay = V1TrendDay;
export type TopForm = V1RiskItem;

/** 最近运行 — 兼容旧组件接口（使用 start_time / task_name / form_name） */
export interface RecentRun {
  id?: number;
  run_id?: string;
  start_time: string;
  task_name: string;
  form_name: string;
  status: string;
  record_count: number;
  duration_seconds: number;
}

export interface DataSource {
  id: string | number;
  name: string;
  type?: string;
  status: string;
  config?: Record<string, unknown>;
}
