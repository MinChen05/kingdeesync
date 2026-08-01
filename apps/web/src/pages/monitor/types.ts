import type { HistoryDetailsData, HistoryFormDetails } from '@/services/generated-api';

/** 历史运行记录 */
export interface HistoryRun {
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
}

/** 统计摘要 */
export interface StatsSummary {
  total_runs: number;
  success_runs: number;
  failed_runs: number;
  partial_runs: number;
  total_records: number;
  success_records: number;
  failed_records: number;
  avg_duration_sec: number;
  success_rate: number;
  period_days: number;
}

/** 诊断信息 */
export interface DiagInfo {
  kingdee_api?: { status: string; response_ms?: number };
  database?: { status: string; response_ms?: number };
  scheduler?: { status: string };
  log_service?: { status: string };
}

/** 错误日志条目 */
export interface LogEntry {
  id?: number;
  run_id: string;
  form_name: string;
  level: string;
  message: string;
  detail?: string;
  created_at: string;
}

/** 日志查询参数 */
export interface LogsParams {
  level?: string;
  limit?: number;
  form_name?: string;
  days?: number;
}

/** 日志数据 */
export interface LogsData {
  logs: LogEntry[];
  total: number;
}

/** 日志统计 */
export interface LogsStatsData {
  total: number;
  errors: number;
  warnings: number;
  infos: number;
}

/** 历史列表查询参数 */
export interface HistoryListParams {
  page?: number;
  pageSize?: number;
  status?: string;
  sync_type?: string;
  from_date?: string;
  to_date?: string;
}

/** 历史列表数据 */
export interface HistoryListData {
  runs: HistoryRun[];
  total: number;
  page: number;
  page_size: number;
}

/** 运行详情中的表单明细 */
export type RunFormDetail = HistoryFormDetails;

/** 运行详情 — 与 HistoryDetailsData 兼容 */
export type RunDetail = HistoryDetailsData;

/** @deprecated 迁移至 {@link '@/types/form'}，此处保留以兼容现有导入 */
export type { FormStat } from '@/types/form';
