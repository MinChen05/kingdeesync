import { App } from 'antd';
import React, { useState } from 'react';
import PageHeader from '@/components/PageHeader';
import { ApiProblemError } from '@/services/v1';
import { errorMessage } from '@/utils/errorMessage';
import LastSyncSummary from './components/LastSyncSummary';
import SyncConfigPanel from './components/SyncConfigPanel';
import SyncLogViewer from './components/SyncLogViewer';
import SyncProgressPanel from './components/SyncProgressPanel';
import { useSyncPage } from './hooks';
import type { SyncMode } from './types';
import './sync.less';

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
    starting,
    stopSync,
  } = useSyncPage();
  const [clearLogs, setClearLogs] = useState(false);
  const [stopping, setStopping] = useState(false);

  const displayLogs = clearLogs ? [] : logs;

  const handleStart = async (mode: SyncMode, selectedForms: string[]) => {
    try {
      await startSync({
        sync_type: mode,
        forms: selectedForms.length > 0 ? selectedForms : undefined,
      });
      message.success('同步任务已启动');
    } catch (err) {
      if (
        err instanceof ApiProblemError &&
        (err.status === 409 || err.code === 'ALREADY_RUNNING')
      ) {
        message.warning('已有同步任务正在运行，请稍后再试');
      } else {
        message.error(errorMessage(err) || '启动同步失败');
      }
    }
  };

  const handleStop = async () => {
    setStopping(true);
    try {
      if (!status.run_id) {
        throw new Error('当前没有可停止的运行任务');
      }
      await stopSync(status.run_id);
      message.info('已请求停止同步');
    } catch (err) {
      message.error(errorMessage(err) || '停止同步失败');
    } finally {
      setStopping(false);
    }
  };

  const handleClearLogs = () => {
    setClearLogs(true);
    setTimeout(() => setClearLogs(false), 1000);
  };

  return (
    <div className="page-stack sync-page">
      <PageHeader
        title="同步管理"
        description="配置同步范围，跟踪执行进度与运行日志"
      />
      <LastSyncSummary run={lastRun} loading={lastRunLoading} />
      <div className="sync-workspace">
        <SyncConfigPanel
          forms={forms}
          formsLoading={formsLoading}
          status={status.status}
          starting={starting}
          stopping={stopping}
          onStart={handleStart}
          onStop={handleStop}
        />
        <div className="sync-runtime">
          <SyncProgressPanel status={status} />
          <SyncLogViewer logs={displayLogs} onClear={handleClearLogs} />
        </div>
      </div>
    </div>
  );
};

export default SyncPage;
