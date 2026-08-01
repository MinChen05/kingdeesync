import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { Empty, Progress } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import { DotIndicator } from '@/components/DotIndicator';
import { formatDuration } from '@/utils/format';
import type { FormStat, SyncStatusInfo } from '../types';

interface SyncProgressPanelProps {
  status: SyncStatusInfo;
}

/**
 * 同步进度面板。
 */
const SyncProgressPanel: React.FC<SyncProgressPanelProps> = ({ status }) => {
  const isRunning = ['running', 'stopping'].includes(status.status);
  const isTerminal = ['success', 'failed', 'partial', 'stopped', 'failed_abnormal_exit'].includes(status.status);
  const showPanel = isRunning || isTerminal;

  if (!showPanel) {
    return (
      <Panel title="同步状态">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span style={{ color: 'var(--tk-dim)' }}>
              当前无同步任务
            </span>
          }
        />
      </Panel>
    );
  }

  const isFailed = ['failed', 'failed_abnormal_exit'].includes(status.status);

  return (
    <Panel title="同步进度">
      <div className="space-y-4">
        {/* 状态行 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {isRunning && <SyncOutlined spin style={{ color: 'var(--tk-primary)' }} />}
          {status.status === 'success' && <CheckCircleOutlined style={{ color: 'var(--tk-success)' }} />}
          {isFailed && <ExclamationCircleOutlined style={{ color: 'var(--tk-error)' }} />}
          {!isRunning && status.status !== 'success' && !isFailed && <StopOutlined style={{ color: 'var(--tk-dim)' }} />}
          <SyncStatusTag status={status.status} />
          {status.current_form && (
            <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>
              {status.current_form}
            </span>
          )}
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--tk-dim)' }}>
            {formatDuration(status.elapsed_seconds)}
          </span>
        </div>

        {/* 进度条 */}
        <Progress
          percent={Math.round(status.progress || 0)}
          status={isFailed ? 'exception' : status.status === 'success' ? 'success' : 'active'}
          size="small"
        />

        {/* 表单级统计 */}
        {status.form_stats && status.form_stats.length > 0 && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {status.form_stats.map((fs: FormStat) => {
              const level =
                fs.status === 'success' ? 'ok' : fs.status === 'failed' ? 'error' : 'unknown';
              return (
                <div key={fs.form_name} className="list-row" style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '8px 10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <DotIndicator level={level} />
                    <span style={{ fontWeight: 600, color: 'var(--tk-text)', fontSize: 12 }}>
                      {fs.form_name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 12px' }}>
                    <span style={{ fontSize: 11, color: 'var(--tk-dim)' }}>
                      拉取 <span style={{ color: '#cbd5e1' }}>{fs.fetched}</span>
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--tk-dim)' }}>
                      写入 <span style={{ color: '#cbd5e1' }}>{fs.inserted}</span>
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--tk-dim)' }}>
                      错误 <span style={{ color: fs.errors > 0 ? 'var(--tk-error)' : '#cbd5e1' }}>{fs.errors}</span>
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--tk-dim)' }}>
                      <span style={{ color: '#cbd5e1' }}>{formatDuration(fs.duration_sec)}</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Panel>
  );
};

export default SyncProgressPanel;
