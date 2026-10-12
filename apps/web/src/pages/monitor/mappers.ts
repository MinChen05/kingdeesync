import type { V1Run } from '@/services/v1';
import type { HistoryRun } from './types';

/**
 * V1Run → HistoryRun 兼容转换。
 * （原因：hooks 与 HistoryTable 曾有逐字相同的私有实现，收敛为单一来源）
 */
export function toHistoryRun(v1: V1Run): HistoryRun {
  return {
    id: 0,
    run_id: v1.run_id,
    task_name: v1.sync_type,
    sync_type: v1.sync_type,
    status: v1.status,
    start_time: v1.started_at || '',
    end_time: v1.finished_at,
    duration_seconds: v1.duration_seconds,
    total_records: v1.total_records,
    success_records: v1.success_records,
    failed_records: v1.failed_records,
    form_count: v1.form_count,
    success_forms: v1.success_forms,
    failed_forms: v1.failed_forms,
  };
}
