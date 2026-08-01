import { Table, Typography } from 'antd';
import React from 'react';
import SyncStatusTag from '@/components/SyncStatusTag';
import { formatDuration } from '@/utils/format';
import type { RunFormDetail } from '../types';

const { Text, Paragraph } = Typography;

interface FormDetailTableProps {
  forms: RunFormDetail[];
}

/** 表单明细表格（含错误展开行） */
const FormDetailTable: React.FC<FormDetailTableProps> = ({ forms }) => {
  const columns = [
    {
      title: '表单',
      dataIndex: 'form_name',
      key: 'form_name',
      render: (v: string) => (
        <Text strong style={{ color: 'var(--tk-text)', fontSize: 13 }}>
          {v}
        </Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => <SyncStatusTag status={v} />,
    },
    {
      title: '总记录',
      dataIndex: 'total_records',
      key: 'total_records',
      width: 90,
      render: (v: number) => (v || 0).toLocaleString(),
    },
    {
      title: '写入',
      key: 'written',
      width: 90,
      render: (_: unknown, r: RunFormDetail) =>
        ((r.inserted || 0) + (r.updated || 0)).toLocaleString(),
    },
    {
      title: '失败',
      dataIndex: 'failed',
      key: 'failed',
      width: 70,
      render: (v: number) => (
        <Text style={{ color: v > 0 ? 'var(--tk-error)' : 'var(--tk-muted)' }}>{v || 0}</Text>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 90,
      render: (v: number) => formatDuration(v),
    },
  ];

  return (
    <div>
      <Text strong className="mb-2 block">
        表单明细（{forms.length}）
      </Text>
      <Table<RunFormDetail>
        columns={columns}
        dataSource={forms}
        rowKey="form_name"
        size="small"
        pagination={false}
        scroll={{ y: 320 }}
        expandable={{
          rowExpandable: (r) => !!r.error_message,
          expandedRowRender: (r) => (
            <Paragraph
              className="!mb-0"
              style={{
                fontSize: 12,
                color: 'var(--tk-error)',
                whiteSpace: 'pre-wrap',
              }}
            >
              {r.error_message}
            </Paragraph>
          ),
        }}
      />
    </div>
  );
};

export { FormDetailTable };
