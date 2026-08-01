/**
 * 表单统计 — monitor 与 data 页面共用。
 * 两处原有定义已合并到此，避免重复。
 */
export interface FormStat {
  form_name: string;
  failed_records?: number;
  total_runs?: number;
  record_count?: number;
  error_count?: number;
  total_records?: number;
  last_sync_time?: string;
  last_status?: string;
}
