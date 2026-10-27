import { ArrowRightOutlined } from '@ant-design/icons';
import { Link } from '@umijs/max';
import { Empty, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import { formatDuration } from '@/utils/format';
import type { RecentRun } from '../hooks';

const { Text } = Typography;

interface RecentRunsProps {
  recent: RecentRun[];
  loading?: boolean;
}

const STATUS_COLOR: Record<string, string> = {
  success: 'var(--tk-success)',
  failed: 'var(--tk-error)',
  failed_abnormal_exit: 'var(--tk-error)',
  partial: 'var(--tk-warning)',
  running: 'var(--tk-primary)',
};

const getStatusColor = (status: string) =>
  STATUS_COLOR[status] || 'var(--tk-dim)';

const RecentRuns: React.FC<RecentRunsProps> = ({ recent, loading }) => {
  return (
    <Panel
      title="最近同步运行"
      loading={loading}
      extra={
        <Link
          to="/monitor"
          style={{ fontSize: 13, color: 'var(--tk-primary)' }}
        >
          查看全部 <ArrowRightOutlined />
        </Link>
      }
    >
      {recent.length > 0 ? (
        <div className="space-y-2">
          {recent.map((run) => (
            <Link
              key={run.id || run.run_id || run.start_time}
              to="/monitor"
              className="recent-run-row"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '11px 12px',
                border: '1px solid transparent',
                borderRadius: 10,
                textDecoration: 'none',
              }}
            >
              <span
                className="recent-run-dot"
                style={{ backgroundColor: getStatusColor(run.status) }}
              />
              <Text
                strong
                style={{
                  color: 'var(--tk-text)',
                  fontSize: 13,
                  flex: 1,
                  minWidth: 120,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {run.task_name || run.form_name || '-'}
              </Text>
              <div className="recent-run-meta">
                <span>{(run.record_count || 0).toLocaleString()} 条</span>
                <span>·</span>
                <span>
                  {run.duration_seconds
                    ? formatDuration(run.duration_seconds)
                    : '-'}
                </span>
                <span>·</span>
                <span>{run.start_time || '-'}</span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无同步记录"
        />
      )}
    </Panel>
  );
};

export default RecentRuns;
