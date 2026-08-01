import { ExclamationCircleOutlined } from '@ant-design/icons';
import { Link } from '@umijs/max';
import { Empty, Table, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import { formatDuration } from '@/utils/format';
import type { HistoryRun } from '../types';

const { Text } = Typography;

interface RecentErrorsProps {
  runs: HistoryRun[];
  loading?: boolean;
}

/**
 * 最近异常：最近 5 条失败/部分运行记录。
 *
 * （原因：运维人员需要快速了解最近是否有失败任务）
 */
const RecentErrors: React.FC<RecentErrorsProps> = ({ runs, loading }) => {
  if (loading || runs.length === 0) {
    return (
      <Panel
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <ExclamationCircleOutlined style={{ color: 'var(--tk-warning)' }} />
            最近异常
          </span>
        }
        loading={loading}
      >
        {!loading && runs.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Text type="secondary">暂无异常记录，系统运行正常</Text>
            }
          />
        )}
      </Panel>
    );
  }

  const columns = [
    {
      title: '运行ID',
      dataIndex: 'run_id',
      key: 'run_id',
      width: 140,
      render: (v: string) => (
        <Text code style={{ fontSize: 12 }}>
          {v}
        </Text>
      ),
    },
    {
      title: '类型',
      dataIndex: 'sync_type',
      key: 'sync_type',
      width: 80,
      render: (v: string) => <SyncTypeTag type={v} />,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => <SyncStatusTag status={v} />,
    },
    {
      title: '失败表单',
      dataIndex: 'failed_forms',
      key: 'failed_forms',
      width: 90,
      render: (v: number) => (
        <Text style={{ color: v > 0 ? 'var(--tk-error)' : 'var(--tk-muted)' }}>{v || '-'}</Text>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 100,
      render: formatDuration,
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      width: 160,
      render: (v: string) => v || '-',
    },
  ];

  return (
    <Panel
      title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <ExclamationCircleOutlined style={{ color: 'var(--tk-warning)' }} />
          最近异常
          <Text
            type="secondary"
            style={{ fontSize: 12, fontWeight: 400 }}
          >
            ({runs.length}条)
          </Text>
        </span>
      }
      extra={
        <Link to="/monitor" style={{ fontSize: 12, color: 'var(--tk-primary)' }}>
          查看全部 →
        </Link>
      }
    >
      <Table
        columns={columns}
        dataSource={runs}
        rowKey="run_id"
        pagination={false}
        size="small"
        scroll={{ x: 700 }}
      />
    </Panel>
  );
};

export default RecentErrors;
