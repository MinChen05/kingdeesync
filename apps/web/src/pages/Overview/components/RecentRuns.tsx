import { ArrowRightOutlined } from '@ant-design/icons';
import { Link } from '@umijs/max';
import { Empty, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import type { RecentRun } from '../hooks';

const { Text } = Typography;

interface RecentRunsProps {
  recent: RecentRun[];
  loading?: boolean;
}

const STATUS_META: Record<string, { color: string; label: string }> = {
  success: { color: 'var(--tk-success)', label: '成功' },
  failed: { color: 'var(--tk-error)', label: '失败' },
  failed_abnormal_exit: { color: 'var(--tk-error)', label: '失败' },
  partial: { color: 'var(--tk-warning)', label: '部分' },
  running: { color: 'var(--tk-primary)', label: '运行中' },
};

const getStatusMeta = (status: string) =>
  STATUS_META[status] || { color: 'var(--tk-dim)', label: status || '未知' };

/**
 * 最近同步记录：状态指示灯 + 表单名 + 记录数/耗时/时间。
 */
const RecentRuns: React.FC<RecentRunsProps> = ({ recent, loading }) => {
  return (
    <Panel
      title="最近同步"
      loading={loading}
      extra={
        <Link to="/monitor" style={{ fontSize: 13, color: 'var(--tk-primary)' }}>
          查看全部 <ArrowRightOutlined />
        </Link>
      }
    >
      {recent.length > 0 ? (
        <div className="space-y-2">
          {recent.map((run) => {
            const meta = getStatusMeta(run.status);
            return (
              <Link
                key={run.id || run.run_id || run.start_time}
                to="/monitor"
                className="recent-run-row"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '9px 12px',
                  borderRadius: 8,
                  textDecoration: 'none',
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: meta.color,
                    boxShadow: `0 0 8px ${meta.color}`,
                    flexShrink: 0,
                  }}
                />
                <Text
                  strong
                  style={{
                    color: 'var(--tk-text)',
                    fontSize: 13,
                    flex: 1,
                    minWidth: 0,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {run.task_name || run.form_name || '-'}
                </Text>
                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--tk-dim)',
                    fontVariantNumeric: 'tabular-nums',
                    flexShrink: 0,
                  }}
                >
                  {(run.record_count || 0).toLocaleString()} 条 ·{' '}
                  {run.duration_seconds
                    ? `${Math.round(run.duration_seconds)}秒`
                    : '-'}{' '}
                  · {run.start_time || '-'}
                </span>
              </Link>
            );
          })}
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
