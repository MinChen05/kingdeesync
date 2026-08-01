import type { SyncFormStatus, SyncStatus, SyncType } from '@/services/generated-api';

/** 同步模式 */
export type SyncMode = SyncType;

/** 表单信息 */
export interface FormItem {
  form_name: string;
  enabled: boolean;
}

/** 同步状态（含 idle 兼容值） */
export interface SyncStatusInfo {
  run_id: string;
  status: SyncStatus | 'idle';
  message: string;
  progress: number;
  current_form: string;
  elapsed_seconds: number;
  form_stats: SyncFormStatus[];
}

/** 表单级统计 */
export type FormStat = SyncFormStatus;
