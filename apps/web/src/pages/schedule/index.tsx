import { App } from 'antd';
import React from 'react';
import PageHeader from '@/components/PageHeader';
import JobTable from './components/JobTable';
import SchedulerControl from './components/SchedulerControl';
import { useSchedule } from './hooks';
import type { ScheduleJobSubmit } from './types';

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

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
    pauseScheduler,
    pausing,
    stopScheduler,
    stopping,
    createJob,
    creating,
    updateJob,
    updating,
    deleteJob,
    deleting,
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

  const handlePause = async () => {
    try {
      await pauseScheduler();
      message.info('调度器已暂停');
    } catch (err) {
      message.error(errorMessage(err) || '暂停失败');
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

  const handleCreateJob = async (data: ScheduleJobSubmit) => {
    try {
      await createJob(data);
    } catch (err) {
      message.error(errorMessage(err) || '创建失败');
    }
  };

  const handleUpdateJob = async (id: number, data: ScheduleJobSubmit) => {
    try {
      await updateJob(id, data);
    } catch (err) {
      message.error(errorMessage(err) || '更新失败');
    }
  };

  const handleDeleteJob = async (id: number) => {
    try {
      await deleteJob(id);
    } catch (err) {
      message.error(errorMessage(err) || '删除失败');
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
        onPause={handlePause}
        onStop={handleStop}
        starting={starting}
        pausing={pausing}
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
      />
    </div>
  );
};

export default SchedulePage;
