import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getDiagnostics, listForms } from '@/services/v1';
import type { V1DiagService, V1Form } from '@/services/v1';
import type { DiagInfo, FormItem, FormStat } from './types';
import { request } from '@umijs/max';

/**
 * data 页面数据 Hook — v1 版。
 *
 * 使用 v1 API 获取表单列表和诊断信息。
 * 表单统计从 V1Form 自带字段获取（record_count / error_count）。
 */
export function useDataPage() {
  const queryClient = useQueryClient();

  // 表单列表（v1）
  const formsReq = useQuery({
    queryKey: ['v1', 'forms'],
    queryFn: listForms,
  });
  const allForms: FormItem[] = (formsReq.data ?? []).map(toFormItem);

  // 诊断信息（v1）
  const diagReq = useQuery({
    queryKey: ['v1', 'diagnostics'],
    queryFn: getDiagnostics,
  });
  const diagInfo: DiagInfo = {
    kingdee_api: diagReq.data?.kingdee_api,
    database: diagReq.data?.database,
  };

  // 表单统计 — 从 V1Form 自带字段构建
  const statsMap = new Map<string, FormStat>(
    allForms.map(f => [f.form_name, {
      form_name: f.form_name,
      failed_records: f.error_count ?? 0,
      total_runs: 0,
    }]),
  );

  // 更新表单启用状态
  const updateReq = useMutation({
    mutationFn: ({ formName, enabled }: { formName: string; enabled: boolean }) =>
      request(`/api/v1/forms/${formName}`, {
        method: 'PUT',
        data: { enabled },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v1', 'forms'] });
    },
  });

  // 更新表单配置（FormID, FieldKeys, FilterString, FieldMap）
  const updateConfigReq = useMutation({
    mutationFn: ({ formName, data }: { formName: string; data: Partial<FormItem> }) =>
      request(`/api/v1/forms/${formName}`, {
        method: 'PUT',
        data,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['v1', 'forms'] });
    },
  });

  return {
    allForms,
    formsLoading: formsReq.isPending,
    diagInfo,
    diagLoading: diagReq.isPending,
    statsMap,
    updateForm: (formName: string, enabled: boolean) =>
      updateReq.mutateAsync({ formName, enabled }),
    updating: updateReq.isPending,
    updateFormConfig: (formName: string, data: Partial<FormItem>) =>
      updateConfigReq.mutateAsync({ formName, data }),
    updatingConfig: updateConfigReq.isPending,
    refreshForms: formsReq.refetch,
  };
}

/** V1Form → FormItem 转换 */
function toFormItem(v1: V1Form): FormItem {
  return {
    form_name: v1.form_name,
    enabled: v1.enabled,
    last_sync_time: v1.last_sync_time,
    last_status: v1.last_status,
    record_count: v1.record_count,
    error_count: v1.error_count,
    form_id: v1.form_id,
    field_keys: v1.field_keys,
    filter_string: v1.filter_string,
    field_map: v1.field_map,
  };
}
