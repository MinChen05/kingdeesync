/**
 * v1 API 客户端 — 对应 /api/v1/* 端点。
 *
 * 与旧版 api.ts 的区别：
 * - 响应格式为 {"data": T, "meta": PageMeta} 或 {"error": {code, message}}
 * - 错误统一转为 ApiProblemError 抛出
 * - 类型从后端 v1 DTO 直接映射，不经过 ApiResponse 包装
 */

import { request } from '@umijs/max';

// ─── v1 响应信封 ───

interface Envelope<T> {
  data: T;
  meta?: PageMeta;
}

interface ProblemResponse {
  error: { code: string; message: string; details?: unknown };
}

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
}

// ─── 错误类型 ───

/**
 * v1 结构化错误，对应后端 Problem DTO。
 */
export class ApiProblemError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = 'ApiProblemError';
  }
}

// ─── v1 DTO ───

export interface V1RunForm {
  form_name: string;
  status: string;
  total_records: number;
  inserted: number;
  updated: number;
  deleted: number;
  failed: number;
  skipped: number;
  duration_seconds: number;
  error_message?: string;
}

export interface V1RunError {
  form_name: string;
  level: string;
  message: string;
  detail?: string;
  created_at: string;
}

export interface V1Run {
  run_id: string;
  status: string;
  sync_type: string;
  started_at?: string;
  finished_at?: string;
  duration_seconds: number;
  total_records: number;
  success_records: number;
  failed_records: number;
  form_count: number;
  success_forms: number;
  failed_forms: number;
  error_message?: string;
  forms?: V1RunForm[];
  errors?: V1RunError[];
}

export interface V1RunEvent {
  created_at: string;
  form_name: string;
  level: string;
  message: string;
}

export interface V1TodayStats {
  sync_count: number;
  success_rate: number;
  fail_count: number;
  avg_duration: number;
  last_sync_time?: string;
  yesterday_sync_count: number;
  yesterday_success_rate: number;
}

export interface V1HealthItem {
  status: string;
  response_ms?: number;
  today_calls?: number;
  conn_count?: number;
  uptime?: string;
  next_exec?: string;
  write_speed?: string;
  log_size?: string;
}

export interface V1HealthStatus {
  kingdee_api: V1HealthItem;
  database: V1HealthItem;
  scheduler: V1HealthItem;
  log_service: V1HealthItem;
}

export interface V1TrendDay {
  date: string;
  sync_count: number;
  records: number;
  success_rate: number;
}

export interface V1RiskItem {
  form_name: string;
  failure_count: number;
  last_error?: string;
}

export interface V1Overview {
  today: V1TodayStats;
  health: V1HealthStatus;
  active_run?: V1Run;
  trend: V1TrendDay[];
  risks: V1RiskItem[];
  recent_runs: V1Run[];
}

export interface V1Schedule {
  id: number;
  name: string;
  cron_expr: string;
  sync_type: string;
  forms: string;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
  last_run_at?: string;
  next_run_at?: string;
  last_status?: string;
}

export interface V1SchedulerStatus {
  enabled: boolean;
}

export interface V1Form {
  form_name: string;
  enabled: boolean;
  last_sync_time?: string;
  last_status?: string;
  record_count: number;
  error_count: number;
  form_id?: string;
  field_keys?: string;
  filter_string?: string;
  field_map?: Record<string, string>;
  default_values?: Record<string, unknown>;
}

export interface V1DataSource {
  id: string;
  name: string;
  type: string;
  status: string;
}

export interface V1DiagService {
  status: string;
  response_ms?: number;
}

export interface V1Diagnostics {
  kingdee_api: V1DiagService;
  database: V1DiagService;
  scheduler: V1DiagService;
  log_service: V1DiagService;
}

export type V1SystemConfig = Record<string, unknown>;

// ─── 请求辅助 ───

/**
 * 发起 v1 请求并解包 data。若后端返回 error，抛出 ApiProblemError。
 */
async function v1Request<T>(url: string, options?: Record<string, unknown>): Promise<T> {
  const resp: Envelope<T> | ProblemResponse = await request(url, {
    ...(options || {}) as any,
  }) as any;

  // 判断是错误响应
  if ('error' in resp) {
    const err = (resp as ProblemResponse).error;
    throw new ApiProblemError(0, err.code, err.message, err.details);
  }

  return (resp as Envelope<T>).data;
}

/**
 * 发起 v1 分页请求，同时返回 data 和 meta。
 */
async function v1Paginated<T>(
  url: string,
  options?: Record<string, unknown>,
): Promise<{ data: T; meta: PageMeta }> {
  const resp: Envelope<T> | ProblemResponse = await request(url, {
    ...(options || {}) as any,
  }) as any;

  if ('error' in resp) {
    const err = (resp as ProblemResponse).error;
    throw new ApiProblemError(0, err.code, err.message, err.details);
  }

  const envelope = resp as Envelope<T> & { meta: PageMeta };
  return { data: envelope.data, meta: envelope.meta! };
}

// ─── Runs ───

export interface ListRunsParams {
  status?: string;
  sync_type?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  page_size?: number;
}

export async function listRuns(params?: ListRunsParams) {
  return v1Paginated<V1Run[]>('/api/v1/runs', { method: 'GET', params });
}

export async function getRun(runId: string) {
  return v1Request<V1Run>(`/api/v1/runs/${runId}`, { method: 'GET' });
}

export async function listRunEvents(runId: string) {
  return v1Request<V1RunEvent[]>(`/api/v1/runs/${runId}/events`, { method: 'GET' });
}

/**
 * 创建运行 — v1 暂返回 501，委托旧路由。
 * 保留接口签名，后续迁移后直接可用。
 */
export async function createRun(params: { forms?: string[]; sync_type: string }) {
  return v1Request<V1Run>('/api/v1/runs', { method: 'POST', data: params });
}

// ─── Overview ───

export async function getOverview() {
  return v1Request<V1Overview>('/api/v1/overview', { method: 'GET' });
}

// ─── Schedules ───

export async function listSchedules() {
  return v1Request<V1Schedule[]>('/api/v1/schedules', { method: 'GET' });
}

export async function getSchedulerStatus() {
  return v1Request<V1SchedulerStatus>('/api/v1/schedules/status', { method: 'GET' });
}

export async function createSchedule(data: {
  name: string;
  cron_expr: string;
  sync_type: string;
  forms?: string;
  enabled?: boolean;
}) {
  return v1Request<V1Schedule>('/api/v1/schedules', { method: 'POST', data });
}

export async function updateSchedule(id: number, data: Partial<V1Schedule>) {
  return v1Request<V1Schedule>(`/api/v1/schedules/${id}`, { method: 'PUT', data });
}

export async function deleteSchedule(id: number) {
  return v1Request<unknown>(`/api/v1/schedules/${id}`, { method: 'DELETE' });
}

export async function startScheduler() {
  return v1Request<unknown>('/api/v1/scheduler/start', { method: 'POST' });
}

export async function stopScheduler() {
  return v1Request<unknown>('/api/v1/scheduler/stop', { method: 'POST' });
}

// ─── Resources ───

export async function listForms() {
  return v1Request<V1Form[]>('/api/v1/forms', { method: 'GET' });
}

export async function listDataSources() {
  return v1Request<V1DataSource[]>('/api/v1/datasources', { method: 'GET' });
}

// ─── System ───

export async function getDiagnostics() {
  return v1Request<V1Diagnostics>('/api/v1/system/diagnostics', { method: 'GET' });
}

export async function getSystemConfig() {
  return v1Request<V1SystemConfig>('/api/v1/system/config', { method: 'GET' });
}

export async function testConnections() {
  return v1Request<unknown>('/api/v1/system/test-connections', { method: 'POST' });
}

export async function getVersion() {
  return v1Request<{ version: string; build_time: string }>('/api/v1/system/version', { method: 'GET' });
}

export async function archiveSystem(daysToKeep: number) {
  return v1Request<unknown>('/api/v1/system/archive', { method: 'POST', data: { days_to_keep: daysToKeep } });
}

export interface ListLogsParams {
  level?: string;
  form_name?: string;
  days?: number;
  limit?: number;
}

export async function listLogs(params?: ListLogsParams) {
  return v1Request<{ logs: V1RunEvent[]; total: number }>('/api/v1/logs', { method: 'GET', params });
}
