import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { Link } from '@umijs/max';
import { Empty } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import type { V1Run } from '@/services/v1';
import { formatDuration } from '@/utils/format';

interface LastSyncSummaryProps {
  run?: V1Run;
  loading?: boolean;
}

/**
 * 上次同步结果摘要。
 */
const LastSyncSummary: React.FC<LastSyncSummaryProps> = ({ run, loading }) => {
  if (loading || !run) {
    return (
      <Panel title="上次同步" loading={loading}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无同步记录"
        />
      </Panel>
    );
  }

  const statusIcon = (status: string) => {
    if (status === 'success')
      return <CheckCircleOutlined style={{ color: 'var(--tk-success)' }} />;
    if (status === 'failed')
      return <CloseCircleOutlined style={{ color: 'var(--tk-error)' }} />;
    return <ExclamationCircleOutlined style={{ color: 'var(--tk-warning)' }} />;
  };

  return (
    <Panel
      title="上次同步"
      extra={
        <Link
          to="/monitor"
          style={{ fontSize: 12, color: 'var(--tk-primary)' }}
        >
          查看全部 →
        </Link>
      }
    >
      <div className="flex items-center justify-between">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {statusIcon(run.status)}
          <SyncStatusTag status={run.status} />
          <SyncTypeTag type={run.sync_type} />
          <span style={{ fontSize: 11, color: 'var(--tk-dim)', fontFamily: 'monospace' }}>
            {run.run_id}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
          <span style={{ fontSize: 13 }}>
            {run.total_records?.toLocaleString() || 0} 条
          </span>
          <span style={{ fontSize: 13 }}>
            {run.success_forms || 0}/{run.form_count || 0} 表单
          </span>
          <span style={{ fontSize: 13 }}>
            {formatDuration(run.duration_seconds)}
          </span>
          <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>
            {run.started_at || '-'}
          </span>
        </div>
      </div>
    </Panel>
  );
};

export default LastSyncSummary;
