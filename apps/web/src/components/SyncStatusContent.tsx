import {
  CheckCircleOutlined,
  CloseCircleOutlined,
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

/** 同步状态 Tooltip 内容（不含 FloatButton 外壳） */
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
          <Text strong>同步进行中</Text>
          <div className="sync-indicator-progress">
            <Progress
              percent={Math.round(progress)}
              size="small"
              strokeColor={'var(--tk-primary)'}
              format={() => `${Math.round(progress)}%`}
            />
          </div>
          {current_form && (
            <div style={{ fontSize: 12, color: 'var(--tk-muted)', marginTop: 4 }}>
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
        <div>
          <Text strong style={{ color: 'var(--tk-success)' }}>
            同步完成
          </Text>
        </div>
      );

    case 'failed':
    case 'failed_abnormal_exit':
      return (
        <div style={{ minWidth: 200 }}>
          <Text strong style={{ color: 'var(--tk-error)' }}>
            同步失败
          </Text>
          {message && (
            <div style={{ fontSize: 12, color: 'var(--tk-muted)', marginTop: 4 }}>
              {message}
            </div>
          )}
        </div>
      );

    default:
      return null;
  }
};

/** 根据状态返回 FloatButton 图标 */
const syncIconForStatus = (status: SyncStatus): React.ReactNode => {
  const style = { fontSize: 20 } as React.CSSProperties;

  switch (status) {
    case 'running':
    case 'stopping':
      return <SyncOutlined spin style={style} />;
    case 'success':
      return (
        <CheckCircleOutlined
          style={{ ...style, color: 'var(--tk-success)' }}
        />
      );
    case 'failed':
    case 'failed_abnormal_exit':
      return (
        <CloseCircleOutlined
          style={{ ...style, color: 'var(--tk-error)' }}
        />
      );
    default:
      return null;
  }
};

/** 根据状态返回 FloatButton 背景色 */
const syncButtonBg = (status: SyncStatus): string => {
  if (status === 'running' || status === 'stopping') return 'var(--tk-surface)';
  if (status === 'success') return '#064e3b';
  return '#7f1d1d';
};

/** 根据状态返回 FloatButton 边框色 */
const syncButtonBorder = (status: SyncStatus): string => {
  if (status === 'running' || status === 'stopping') return 'var(--tk-primary)';
  if (status === 'success') return 'var(--tk-success)';
  return 'var(--tk-error)';
};

export {
  SyncStatusContent,
  syncIconForStatus,
  syncButtonBg,
  syncButtonBorder,
};
export type { SyncStatus };
