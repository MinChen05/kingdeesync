/**
 * Overview 页面集中类型定义。
 * 接口字段变更时只需修改这里，各面板组件统一从这里引用类型。（原因：收敛类型、便于维护与扩展）
 */

/** 今日统计 */
export interface TodayStats {
  sync_count?: number;
  success_rate?: number;
  fail_count?: number;
  avg_duration?: number;
  last_sync_time?: string;
  yesterday_sync_count?: number;
  yesterday_success_rate?: number;
}

/** 同步运行状态（3s 轮询） */
export interface SyncStatusInfo {
  status?: string;
  message?: string;
  progress?: number;
  current_form?: string;
  elapsed_seconds?: number;
}

/** 7 天趋势单日 */
export interface TrendDay {
  date: string;
  sync_count: number;
  records: number;
  success_rate: number;
}

/** 近 7 天异常表单 */
export interface TopForm {
  form_name: string;
  failure_count: number;
  last_error: string;
}

/** 数据源（与后端 /api/datasources 返回结构对齐） */
export interface DataSource {
  id: string | number;
  name: string;
  type?: string;
  /** configured / connected / error 等 */
  status: string;
  latency?: string;
  last_test_time?: string;
  account_info?: string;
  config?: Record<string, unknown>;
}

/** 系统健康单项（各服务字段不同，统一宽松定义） */
export interface HealthItem {
  status?: string;
  response_ms?: number;
  today_calls?: number;
  conn_count?: number;
  uptime?: string;
  next_exec?: string;
  write_speed?: string;
  log_size?: string;
}

/** 系统健康 */
export interface HealthStatus {
  kingdee_api?: HealthItem;
  database?: HealthItem;
  scheduler?: HealthItem;
  log_service?: HealthItem;
}

/** 最近同步记录 */
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

/** 健康状态枚举（用于指示灯颜色） */
export type HealthLevel = 'ok' | 'error' | 'unknown';

/** 任务项 */
export interface TaskItem {
  id: number;
  name: string;
  enabled: boolean;
  last_run_at?: string;
  last_status?: string;
}
