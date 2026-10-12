import { App } from 'antd';
import React from 'react';
import PageHeader from '@/components/PageHeader';
import { errorMessage } from '@/utils/errorMessage';
import JobTable from './components/JobTable';
import SchedulerControl from './components/SchedulerControl';
import { useSchedule } from './hooks';
import type { ScheduleJobSubmit } from './types';

/**
 * 任务调度页。
 *
 * 信息架构：
 * - 顶部：调度器状态卡片 + 任务统计卡片
 * - 主体：任务列表（搜索、编辑、删除）
 * - 右侧抽屉：任务创建/编辑
 */
const SchedulePage: React.FC = () => {
  const { message } = App.useApp();
  const {
    status,
    jobs,
    loading,
    startScheduler,
    starting,
    stopScheduler,
    stopping,
    createJob,
    creating,
    updateJob,
    updating,
    deleteJob,
    deleting,
    batchAction,
    batchActioning,
  } = useSchedule();

  const enabledCount = jobs.filter((j) => j.enabled).length;

  const handleStart = async () => {
    try {
      await startScheduler();
      message.success('调度器已启动');
    } catch (err) {
      message.error(errorMessage(err) || '启动失败');
    }
  };

  const handleStop = async () => {
    try {
      await stopScheduler();
      message.info('调度器已停止');
    } catch (err) {
      message.error(errorMessage(err) || '停止失败');
    }
  };

  // 以下 handler 失败时必须 rethrow：
  // （原因：调用方组件 await 后无条件弹"成功"，吞掉异常会让失败也报成功）
  const handleCreateJob = async (data: ScheduleJobSubmit) => {
    try {
      await createJob(data);
    } catch (err) {
      message.error(errorMessage(err) || '创建失败');
      throw err;
    }
  };

  const handleUpdateJob = async (id: number, data: ScheduleJobSubmit) => {
    try {
      await updateJob(id, data);
    } catch (err) {
      message.error(errorMessage(err) || '更新失败');
      throw err;
    }
  };

  const handleDeleteJob = async (id: number) => {
    try {
      await deleteJob(id);
    } catch (err) {
      message.error(errorMessage(err) || '删除失败');
      throw err;
    }
  };

  const handleBatchAction = async (action: string, ids: number[]) => {
    try {
      await batchAction(action, ids);
    } catch (err) {
      message.error(errorMessage(err) || '批量操作失败');
      throw err;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="任务调度" />

      {/* 顶部：调度器状态 + 统计卡片 */}
      <SchedulerControl
        enabled={status.enabled}
        jobCount={jobs.length}
        enabledCount={enabledCount}
        onStart={handleStart}
        onStop={handleStop}
        starting={starting}
        stopping={stopping}
      />

      {/* 任务列表 */}
      <JobTable
        jobs={jobs}
        loading={loading}
        onCreate={handleCreateJob}
        onUpdate={handleUpdateJob}
        onDelete={handleDeleteJob}
        creating={creating}
        updating={updating}
        deleting={deleting}
        onBatchAction={handleBatchAction}
        batchActioning={batchActioning}
      />
    </div>
  );
};

export default SchedulePage;
