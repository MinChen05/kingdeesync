import { App } from 'antd';
import React, { useState } from 'react';
import PageHeader from '@/components/PageHeader';
import { errorMessage } from '@/utils/errorMessage';
import { ApiProblemError } from '@/services/v1';
import LastSyncSummary from './components/LastSyncSummary';
import SyncConfigPanel from './components/SyncConfigPanel';
import SyncLogViewer from './components/SyncLogViewer';
import SyncProgressPanel from './components/SyncProgressPanel';
import { useSyncPage } from './hooks';
import type { SyncMode } from './types';

/**
 * 同步执行中心。
 *
 * 信息架构：
 * - 顶部：上次同步结果摘要
 * - 左侧：同步配置（模式 + 表单选择 + 启动/停止 + 快速同步）
 * - 右侧上：同步进度（同步中/刚结束时显示）
 * - 右侧下：实时日志
 *
 * （原因：把"上次结果 + 配置启动 + 执行反馈"集中到一页，减少页面跳转）
 */
const SyncPage: React.FC = () => {
  const { message } = App.useApp();
  const {
    forms,
    formsLoading,
    status,
    logs,
    lastRun,
    lastRunLoading,
    startSync,
    stopSync,
  } = useSyncPage();
  const [clearLogs, setClearLogs] = useState(false);

  const displayLogs = clearLogs ? [] : logs;

  const handleStart = async (mode: SyncMode, selectedForms: string[]) => {
    try {
      await startSync({
        sync_type: mode,
        forms: selectedForms.length > 0 ? selectedForms : undefined,
      });
      message.success('同步任务已启动');
    } catch (err) {
      // 409 冲突改读结构化 status/code（原因：字符串匹配会把含 "409" 的任意错误误判为冲突）
      if (err instanceof ApiProblemError && (err.status === 409 || err.code === 'ALREADY_RUNNING')) {
        message.warning('已有同步任务正在运行，请稍后再试');
      } else {
        message.error(errorMessage(err) || '启动同步失败');
      }
    }
  };

  const handleStop = async () => {
    try {
      if (!status.run_id) {
        throw new Error('当前没有可停止的运行任务');
      }
      await stopSync(status.run_id);
      message.info('已请求停止同步');
    } catch (err) {
      message.error(errorMessage(err) || '停止同步失败');
    }
  };

  const handleClearLogs = () => {
    setClearLogs(true);
    setTimeout(() => setClearLogs(false), 1000);
  };

  return (
    <div className="space-y-6">
      <PageHeader title="同步管理" description="配置同步模式与表单，启动数据同步任务" />

      {/* 上次同步结果摘要 */}
      <LastSyncSummary run={lastRun} loading={lastRunLoading} />

      {/* 主布局：左配置 + 右进度/日志 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* 左侧：配置面板 */}
        <div className="lg:col-span-2">
          <SyncConfigPanel
            forms={forms}
            formsLoading={formsLoading}
            status={status.status}
            onStart={handleStart}
            onStop={handleStop}
          />
        </div>

        {/* 右侧：进度 + 日志 */}
        <div className="space-y-6 lg:col-span-3">
          <SyncProgressPanel status={status} />
          <SyncLogViewer logs={displayLogs} onClear={handleClearLogs} />
        </div>
      </div>
    </div>
  );
};

export default SyncPage;
