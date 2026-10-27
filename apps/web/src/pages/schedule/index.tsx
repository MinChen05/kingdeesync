import { App } from 'antd';
import React from 'react';
import PageHeader from '@/components/PageHeader';
import { errorMessage } from '@/utils/errorMessage';
import JobTable from './components/JobTable';
import SchedulerControl from './components/SchedulerControl';
import { useSchedule } from './hooks';
import type { ScheduleJobSubmit } from './types';
import './schedule.less';

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

  const enabledCount = jobs.filter((job) => job.enabled).length;

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
    <div className="page-stack schedule-page">
      <PageHeader
        title="任务调度"
        description="管理自动同步计划，掌握启停状态与下一次执行时间"
      />
      <SchedulerControl
        enabled={status.enabled}
        jobCount={jobs.length}
        enabledCount={enabledCount}
        onStart={handleStart}
        onStop={handleStop}
        starting={starting}
        stopping={stopping}
      />
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
