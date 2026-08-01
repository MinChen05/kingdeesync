import { request } from '@umijs/max';
import type {
  ApiResponse,
  HealthResponse,
  HistoryDetailsData,
  ReadyResponse,
  SyncLogsData,
  SyncStartData,
  SyncStartRequest,
  SyncStatusData,
  SyncStopData,
} from './generated-api';

import type { ConfigData } from '@/pages/system/types';
import type { FormItem, DataSource, FormStat } from '@/pages/data/types';
import type {
  HistoryRun,
  HistoryListParams,
  HistoryListData,
  StatsSummary,
  LogEntry,
  LogsParams,
  LogsData,
  LogsStatsData,
} from '@/pages/monitor/types';
import type { ScheduleJob } from '@/pages/schedule/types';
import type {
  TodayStats,
  TrendDay,
  TopForm,
  HealthStatus,
  RecentRun,
  TaskItem,
} from '@/pages/Overview/types';

export type { SyncStatus, SyncType, SyncErrorCode } from './generated-api';
export type { SyncStartRequest as SyncStartParams } from './generated-api';

// Re-export types so existing imports still work
export type { ConfigData, FormItem, DataSource, FormStat };
export type { HistoryRun, HistoryListParams, HistoryListData, StatsSummary };
export type { LogEntry, LogsParams, LogsData, LogsStatsData };
export type { ScheduleJob };
export type { TodayStats, TrendDay, TopForm, HealthStatus, RecentRun, TaskItem };

// ─── Sync ───

export async function startSync(params: SyncStartRequest) {
  return request<ApiResponse<SyncStartData>>('/api/sync/start', { method: 'POST', data: params });
}

export async function getSyncStatus(runId?: string) {
  return request<ApiResponse<SyncStatusData>>('/api/v1/sync/status', {
    method: 'GET',
    params: runId ? { run_id: runId } : undefined,
  });
}

export async function getSyncLogs(runId?: string) {
  return request<ApiResponse<SyncLogsData>>('/api/sync/logs', {
    method: 'GET',
    params: runId ? { run_id: runId } : undefined,
  });
}

export async function stopSync(runId: string) {
  return request<ApiResponse<SyncStopData>>('/api/v1/sync/stop', {
    method: 'POST',
    params: { run_id: runId },
  });
}

// ─── Health / Readiness ───

export async function getHealth() {
  return request<HealthResponse>('/health', { method: 'GET' });
}

export async function getReady() {
  return request<ReadyResponse>('/ready', { method: 'GET' });
}

// ─── Config ───

export async function getConfig() {
  return request<ApiResponse<ConfigData>>('/api/config', { method: 'GET' });
}

export async function updateConfig(data: Partial<ConfigData>) {
  return request<ApiResponse<ConfigData>>('/api/config', { method: 'PUT', data });
}

// ─── Forms ───

export async function getForms() {
  return request<ApiResponse<FormItem[]>>('/api/v1/forms', { method: 'GET' });
}

export async function updateForm(formName: string, enabled: boolean) {
  return request<ApiResponse<FormItem>>(`/api/v1/forms/${formName}`, { method: 'PUT', data: { enabled } });
}

// ─── History ───

export async function getHistory(params?: HistoryListParams) {
  return request<ApiResponse<HistoryListData>>('/api/history', { method: 'GET', params });
}

export async function getHistoryDetail(runId: string) {
  return request<ApiResponse<HistoryDetailsData>>(`/api/history/runs/${runId}/details`, { method: 'GET' });
}

// ─── Dashboard ───

export async function getDashboardToday() {
  return request<ApiResponse<TodayStats>>('/api/dashboard/today', { method: 'GET' });
}

export async function getDashboardTrend7d() {
  return request<ApiResponse<TrendDay[]>>('/api/dashboard/trend/7d', { method: 'GET' });
}

export async function getDashboardTopForms7d() {
  return request<ApiResponse<TopForm[]>>('/api/dashboard/top-forms/7d', { method: 'GET' });
}

export async function getDashboardHealth() {
  return request<ApiResponse<HealthStatus>>('/api/dashboard/health', { method: 'GET' });
}

export async function getDashboardRecent(limit?: number) {
  return request<ApiResponse<RecentRun[]>>('/api/dashboard/recent', { method: 'GET', params: limit ? { limit } : undefined });
}

// ─── Schedule ───

export interface ScheduleStatusData {
  enabled: boolean;
  jobs: ScheduleJob[];
}

export async function getScheduleJobs() {
  return request<ApiResponse<ScheduleStatusData>>('/api/schedule', { method: 'GET' });
}

export async function createScheduleJob(data: Partial<ScheduleJob>) {
  return request<ApiResponse<ScheduleJob>>('/api/schedule/job', { method: 'POST', data });
}

export async function updateScheduleJob(id: number, data: Partial<ScheduleJob>) {
  return request<ApiResponse<ScheduleJob>>(`/api/schedule/job/${id}`, { method: 'PUT', data });
}

export async function deleteScheduleJob(id: number) {
  return request<ApiResponse<null>>(`/api/schedule/job/${id}`, { method: 'DELETE' });
}

export async function startSchedule() {
  return request<ApiResponse<null>>('/api/schedule/start', { method: 'POST' });
}

export async function pauseSchedule() {
  return request<ApiResponse<null>>('/api/schedule/pause', { method: 'POST' });
}

export async function stopSchedule() {
  return request<ApiResponse<null>>('/api/schedule/stop', { method: 'POST' });
}

// ─── Stats ───

export async function getStats() {
  return request<ApiResponse<StatsSummary>>('/api/stats/summary', { method: 'GET' });
}

// ─── Diagnostics ───

export interface DiagService {
  status: string;
  response_ms?: number;
}

export interface DiagnosticsData {
  kingdee_api: DiagService;
  database: DiagService;
  environment: { go_version: string; os: string; arch: string; num_cpu: number };
  recent_errors: Record<string, unknown>[];
  messages: string[];
}

export async function getDiagnostics() {
  return request<ApiResponse<DiagnosticsData>>('/api/diagnostics', { method: 'GET' });
}

// ─── Logs ───

export async function getLogs(params?: LogsParams) {
  return request<ApiResponse<LogsData>>('/api/logs/recent', { method: 'GET', params });
}

export async function getLogsStats(days?: number) {
  return request<ApiResponse<LogsStatsData>>('/api/logs/stats', { method: 'GET', params: days ? { days } : undefined });
}

// ─── Tasks ───

export async function getTasks() {
  return request<ApiResponse<TaskItem[]>>('/api/tasks', { method: 'GET' });
}

export async function getTaskStats() {
  return request<ApiResponse<StatsSummary>>('/api/tasks/stats', { method: 'GET' });
}

export async function runTask(id: number, syncType: string) {
  return request<ApiResponse<null>>(`/api/tasks/${id}/run`, { method: 'POST', data: { sync_type: syncType } });
}

export async function enableTask(id: number) {
  return request<ApiResponse<null>>(`/api/tasks/${id}/enable`, { method: 'POST' });
}

export async function pauseTask(id: number) {
  return request<ApiResponse<null>>(`/api/tasks/${id}/pause`, { method: 'POST' });
}

export async function batchEnableTasks(taskIds: number[]) {
  return request<ApiResponse<null>>('/api/tasks/batch-enable', { method: 'POST', data: { task_ids: taskIds } });
}

export async function batchPauseTasks(taskIds: number[]) {
  return request<ApiResponse<null>>('/api/tasks/batch-pause', { method: 'POST', data: { task_ids: taskIds } });
}

export async function batchRunTasks(taskIds: number[], syncType: string) {
  return request<ApiResponse<null>>('/api/tasks/batch-run', { method: 'POST', data: { task_ids: taskIds, sync_type: syncType } });
}

// ─── Data Sources ───

export async function getDataSources() {
  return request<ApiResponse<DataSource[]>>('/api/datasources', { method: 'GET' });
}

export async function testAllDatasources() {
  return request<ApiResponse<DataSource[]>>('/api/datasources/test', { method: 'POST' });
}

export async function getFormsStats() {
  return request<ApiResponse<FormStat[]>>('/api/forms/stats', { method: 'GET' });
}

// ─── Version ───

export interface VersionData {
  version: string;
  build_time: string;
}

export async function getVersion() {
  return request<ApiResponse<VersionData>>('/api/version', { method: 'GET' });
}

// ─── Maintenance ───

export async function archiveMaintenanceData(daysToKeep: number) {
  return request<ApiResponse<null>>('/api/maintenance/archive', {
    method: 'POST',
    data: { days_to_keep: daysToKeep },
  });
}