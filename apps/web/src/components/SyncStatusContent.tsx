import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { Progress, Typography } from 'antd';
import React from 'react';
import { formatDuration } from '@/utils/format';

const { Text } = Typography;

type SyncStatus =
  | 'idle'
  | 'running'
  | 'stopping'
  | 'success'
  | 'failed'
  | 'partial'
  | 'stopped'
  | 'failed_abnormal_exit';

interface SyncInfo {
  status: SyncStatus;
  progress: number;
  current_form: string;
  message: string;
  elapsed_seconds: number;
}

const SyncStatusContent: React.FC<SyncInfo> = ({
  status,
  progress,
  current_form,
  message,
  elapsed_seconds,
}) => {
  switch (status) {
    case 'running':
    case 'stopping':
      return (
        <div style={{ minWidth: 220 }}>
          <Text strong>
            {status === 'stopping' ? '正在停止同步' : '同步进行中'}
          </Text>
          <div className="sync-indicator-progress">
            <Progress
              percent={Math.round(progress)}
              size="small"
              strokeColor="var(--tk-primary)"
              format={() => `${Math.round(progress)}%`}
            />
          </div>
          {current_form && (
            <div
              style={{ fontSize: 12, color: 'var(--tk-muted)', marginTop: 4 }}
            >
              当前：{current_form}
            </div>
          )}
          <div style={{ fontSize: 12, color: 'var(--tk-dim)', marginTop: 2 }}>
            已运行：{formatDuration(elapsed_seconds)}
          </div>
        </div>
      );
    case 'success':
      return (
        <Text strong style={{ color: 'var(--tk-success)' }}>
          同步完成
        </Text>
      );
    case 'partial':
      return (
        <Text strong style={{ color: 'var(--tk-warning)' }}>
          部分表单同步完成
        </Text>
      );
    case 'stopped':
      return <Text strong>同步已停止</Text>;
    case 'failed':
    case 'failed_abnormal_exit':
      return (
        <div style={{ minWidth: 200 }}>
          <Text strong style={{ color: 'var(--tk-error)' }}>
            同步失败
          </Text>
          {message && (
            <div
              style={{ fontSize: 12, color: 'var(--tk-muted)', marginTop: 4 }}
            >
              {message}
            </div>
          )}
        </div>
      );
    default:
      return null;
  }
};

const syncIconForStatus = (status: SyncStatus): React.ReactNode => {
  const style = { fontSize: 20 } as React.CSSProperties;
  switch (status) {
    case 'running':
    case 'stopping':
      return (
        <SyncOutlined spin style={{ ...style, color: 'var(--tk-primary)' }} />
      );
    case 'success':
      return (
        <CheckCircleOutlined style={{ ...style, color: 'var(--tk-success)' }} />
      );
    case 'partial':
      return (
        <ExclamationCircleOutlined
          style={{ ...style, color: 'var(--tk-warning)' }}
        />
      );
    case 'stopped':
      return <StopOutlined style={{ ...style, color: 'var(--tk-muted)' }} />;
    case 'failed':
    case 'failed_abnormal_exit':
      return (
        <CloseCircleOutlined style={{ ...style, color: 'var(--tk-error)' }} />
      );
    default:
      return null;
  }
};

const syncButtonBg = (status: SyncStatus): string => {
  if (status === 'success') return 'var(--tk-success-soft)';
  if (status === 'partial') return 'var(--tk-warning-soft)';
  if (status === 'failed' || status === 'failed_abnormal_exit')
    return 'var(--tk-error-soft)';
  return 'var(--tk-surface)';
};

const syncButtonBorder = (status: SyncStatus): string => {
  if (status === 'running' || status === 'stopping') return 'var(--tk-primary)';
  if (status === 'success') return 'var(--tk-success)';
  if (status === 'partial') return 'var(--tk-warning)';
  if (status === 'stopped') return 'var(--tk-border-strong)';
  return 'var(--tk-error)';
};

export type { SyncStatus };
export { SyncStatusContent, syncButtonBg, syncButtonBorder, syncIconForStatus };
