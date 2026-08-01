import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSchedule,
  deleteSchedule,
  listSchedules,
  startScheduler,
  stopScheduler,
  updateSchedule,
} from '@/services/v1';
import type { V1Schedule } from '@/services/v1';
import type { ScheduleJob, ScheduleJobSubmit, SchedulerStatus } from './types';

/** useSchedule 返回值类型 */
interface UseScheduleResult {
  status: SchedulerStatus;
  jobs: ScheduleJob[];
  loading: boolean;
  refresh: () => Promise<unknown>;
  startScheduler: () => Promise<unknown>;
  starting: boolean;
  pauseScheduler: () => Promise<unknown>;
  pausing: boolean;
  stopScheduler: () => Promise<unknown>;
  stopping: boolean;
  createJob: (
    data: ScheduleJobSubmit,
  ) => Promise<ScheduleJob>;
  creating: boolean;
  updateJob: (
    id: number,
    data: ScheduleJobSubmit,
  ) => Promise<ScheduleJob>;
  updating: boolean;
  deleteJob: (id: number) => Promise<void>;
  deleting: boolean;
}

/**
 * 调度页面数据 Hook — v1 版。
 *
 * 使用 v1 API 管理调度任务，所有操作成功后自动失效查询缓存。
 */
export function useSchedule(): UseScheduleResult {
  const queryClient = useQueryClient();

  // 调度器状态 + 任务列表（v1）
  const schedulesReq = useQuery({
    queryKey: ['v1', 'schedules'],
    queryFn: listSchedules,
    refetchInterval: 5000,
  });
  const schedules: V1Schedule[] = schedulesReq.data || [];

  // 转换为 ScheduleJob 格式
  const jobs: ScheduleJob[] = schedules.map(toScheduleJob);
  const status: SchedulerStatus = {
    enabled: true, // v1 通过单独端点获取
    jobs,
  };

  const invalidateSchedule = () =>
    queryClient.invalidateQueries({ queryKey: ['v1', 'schedules'] });

  // 启动调度
  const startReq = useMutation({
    mutationFn: startScheduler,
    onSuccess: invalidateSchedule,
  });

  // 停止调度
  const stopReq = useMutation({
    mutationFn: stopScheduler,
    onSuccess: invalidateSchedule,
  });

  // 创建任务
  const createReq = useMutation({
    mutationFn: (data: ScheduleJobSubmit) =>
      createSchedule({
        name: data.name,
        cron_expr: data.cron_expr,
        sync_type: data.sync_type,
        forms: data.forms.length > 0 ? JSON.stringify(data.forms) : '',
        enabled: data.enabled,
      }),
    onSuccess: invalidateSchedule,
  });

  // 更新任务
  const updateReq = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: ScheduleJobSubmit;
    }) => updateSchedule(id, {
      name: data.name,
      cron_expr: data.cron_expr,
      sync_type: data.sync_type,
      forms: data.forms.length > 0 ? JSON.stringify(data.forms) : '',
      enabled: data.enabled,
    }),
    onSuccess: invalidateSchedule,
  });

  // 删除任务
  const deleteReq = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: invalidateSchedule,
  });

  return {
    status,
    jobs,
    loading: schedulesReq.isPending,
    refresh: schedulesReq.refetch,
    startScheduler: startReq.mutateAsync,
    starting: startReq.isPending,
    pauseScheduler: stopReq.mutateAsync,
    pausing: stopReq.isPending,
    stopScheduler: stopReq.mutateAsync,
    stopping: stopReq.isPending,
    createJob: async (data: ScheduleJobSubmit) => {
      const v1 = await createReq.mutateAsync(data);
      return toScheduleJob(v1);
    },
    creating: createReq.isPending,
    updateJob: async (id: number, data: ScheduleJobSubmit) => {
      const v1 = await updateReq.mutateAsync({ id, data });
      return toScheduleJob(v1);
    },
    updating: updateReq.isPending,
    deleteJob: async (id: number) => { await deleteReq.mutateAsync(id); },
    deleting: deleteReq.isPending,
  };
}

/** V1Schedule → ScheduleJob 转换 */
function toScheduleJob(v1: V1Schedule): ScheduleJob {
  return {
    id: v1.id,
    name: v1.name,
    cron_expr: v1.cron_expr,
    sync_type: v1.sync_type as 'incremental' | 'full',
    forms: v1.forms,
    enabled: v1.enabled,
    created_at: v1.created_at,
    updated_at: v1.updated_at,
    last_run_at: v1.last_run_at,
    next_run_at: v1.next_run_at,
    last_status: v1.last_status,
  };
}
