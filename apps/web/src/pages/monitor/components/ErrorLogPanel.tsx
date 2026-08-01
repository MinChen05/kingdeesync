import { FileSearchOutlined } from '@ant-design/icons';
import { useSearchParams } from '@umijs/max';
import { useQuery } from '@tanstack/react-query';
import { Empty, Table } from 'antd';
import React, { useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import { listLogs } from '@/services/v1';
import type { V1RunEvent } from '@/services/v1';
import { LogFilterBar, useLogColumns } from './LogColumns';

/**
 * 错误日志面板：排障主战场。
 */
const ErrorLogPanel: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const focusForm = searchParams.get('form') || '';
  const [level, setLevel] = useState('ERROR');
  const [days, setDays] = useState(7);

  const params = useMemo(() => {
    const p: { level?: string; form_name?: string; days?: number; limit: number } = {
      limit: 50,
      days,
    };
    if (level) p.level = level;
    if (focusForm) p.form_name = focusForm;
    return p;
  }, [level, days, focusForm]);

  const logsReq = useQuery({
    queryKey: ['v1', 'logs', params],
    queryFn: () => listLogs(params),
  });
  const loading = logsReq.isPending;
  const logs: V1RunEvent[] = logsReq.data?.logs || [];

  const clearFocusForm = () => {
    searchParams.delete('form');
    setSearchParams(searchParams, { replace: true });
  };

  const columns = useLogColumns();

  return (
    <Panel
      title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <FileSearchOutlined style={{ color: 'var(--tk-error)' }} />
          错误日志
        </span>
      }
      loading={loading && logs.length === 0}
      extra={
        <a onClick={() => logsReq.refetch()} style={{ fontSize: 12, color: 'var(--tk-primary)' }}>
          刷新
        </a>
      }
    >
      <LogFilterBar
        focusForm={focusForm}
        level={level}
        days={days}
        logCount={logs.length}
        onLevelChange={setLevel}
        onDaysChange={setDays}
        onClearFocusForm={clearFocusForm}
      />
      <Table<V1RunEvent>
        columns={columns}
        dataSource={logs}
        rowKey={(record, index) => `${record.created_at}-${index}`}
        size="small"
        loading={loading && logs.length > 0}
        pagination={false}
        scroll={{ x: 800 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="该时间范围内无错误日志"
            />
          ),
        }}
        expandable={{
          rowExpandable: () => false, // v1 RunEvent 无 detail 字段
        }}
      />
    </Panel>
  );
};

export default ErrorLogPanel;
