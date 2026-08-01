/** 调度任务 */
export interface ScheduleJob {
  id: number;
  name: string;
  cron_expr: string;
  sync_type: 'incremental' | 'full';
  forms: string; // JSON array string
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
  last_run_at?: string;
  next_run_at?: string;
  last_status?: string;
  last_run_id?: string;
}

/** 调度器状态 */
export interface SchedulerStatus {
  enabled: boolean;
  jobs: ScheduleJob[];
}

/** 调度任务提交数据（创建/编辑抽屉输出） */
export interface ScheduleJobSubmit {
  name: string;
  cron_expr: string;
  sync_type: 'incremental' | 'full';
  forms: string[];
  enabled: boolean;
}

/** 解析后的表单列表 */
export const parseForms = (formsStr: string): string[] => {
  try {
    const parsed = JSON.parse(formsStr || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};
