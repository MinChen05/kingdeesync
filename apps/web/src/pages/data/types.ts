/** 表单信息（含统计字段） */
export interface FormItem {
  form_name: string;
  enabled: boolean;
  last_sync_time?: string;
  last_status?: string;
  record_count?: number;
  error_count?: number;
  form_id?: string;
  field_keys?: string;
  filter_string?: string;
  field_map?: Record<string, string>;
}

/** @deprecated 迁移至 {@link '@/types/form'}，此处保留以兼容现有导入 */
export type { FormStat } from '@/types/form';

/** 诊断信息 */
export interface DiagInfo {
  kingdee_api?: { status: string; response_ms?: number };
  database?: { status: string; response_ms?: number };
}

/** 数据源 */
export interface DataSource {
  name: string;
  type: string;
  status: string;
  response_ms?: number;
}
