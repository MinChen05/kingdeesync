/** Types generated from docs/openapi.yaml's synchronization contract. */

// ─── Sync Status ───

export type SyncStatus =
  | 'running'
  | 'stopping'
  | 'success'
  | 'partial'
  | 'failed'
  | 'stopped'
  | 'failed_abnormal_exit';

export type SyncType = 'incremental' | 'full' | 'reset';

// ─── Error Codes ───

export type SyncErrorCode =
  | 'SYNC_ALREADY_RUNNING'
  | 'SYNC_RUN_ID_REQUIRED'
  | 'SYNC_NOT_FOUND'
  | 'SYNC_NOT_ACTIVE'
  | 'SYNC_INVALID_REQUEST'
  | 'SYNC_DATABASE_UNAVAILABLE'
  | 'SYNC_START_FAILED'
  | 'SYNC_LOGS_FAILED';

// ─── API Response ───

export interface ApiResponse<T> {
  ok: boolean;
  data: T;
  error: string;
  code: string;
}

// ─── Health / Readiness ───

export interface HealthResponse {
  status: 'ok';
}

export interface ReadyResponse {
  status: 'ready' | 'not_ready';
  reasons?: string[];
}

// ─── Sync Start / Stop ───

export interface SyncStartRequest {
  forms?: string[];
  sync_type?: SyncType;
  dry_run?: boolean;
}

export interface SyncStartData {
  run_id: string;
  dry_run: boolean;
}

export interface SyncStopData {
  run_id: string;
  status: 'stopping';
}

// ─── Sync Status ───

export interface SyncFormStatus {
  form_name: string;
  fetched: number;
  inserted: number;
  errors: number;
  duration_sec: number;
  status: SyncStatus;
  error_summary?: string;
}

export interface SyncStatusData {
  run_id: string;
  status: SyncStatus;
  progress: number;
  current_form: string;
  message: string;
  error_summary: string;
  elapsed_seconds: number;
  started_at: string;
  form_stats: SyncFormStatus[];
}

// ─── Sync Logs ───

export interface SyncLogEntry {
  created_at: string;
  form_name: string;
  level: string;
  message: string;
  detail: string;
}

export interface SyncLogsData {
  run_id: string;
  logs: SyncLogEntry[];
}

// ─── History Details ───

export interface HistoryFormDetails {
  id?: number;
  run_id: string;
  form_name: string;
  status: SyncStatus;
  total_records: number;
  inserted: number;
  updated: number;
  deleted: number;
  failed: number;
  skipped: number;
  start_time?: string;
  end_time?: string;
  duration_seconds: number;
  error_message?: string;
}

export interface HistoryErrorDetails {
  id?: number;
  run_id: string;
  form_name: string;
  level: string;
  message: string;
  detail: string;
  created_at: string;
}

export interface HistoryDetailsData {
  id: number;
  run_id: string;
  task_name: string;
  sync_type: string;
  status: SyncStatus;
  start_time: string;
  end_time?: string;
  duration_seconds: number;
  total_records: number;
  success_records: number;
  failed_records: number;
  form_count: number;
  success_forms: number;
  failed_forms: number;
  error_message?: string;
  forms: HistoryFormDetails[];
  errors: HistoryErrorDetails[];
}
