import { Progress, Table, Typography } from 'antd';
import React from 'react';
import SyncStatusTag from '@/components/SyncStatusTag';
import { formatDuration } from '@/utils/format';
import type { RunFormDetail } from '../types';

const { Text, Paragraph } = Typography;

interface FormDetailTableProps {
  forms: RunFormDetail[];
}

/** 表单状态 → 进度条颜色 */
const STATUS_BAR_COLOR: Record<string, string> = {
  success: 'var(--tk-success)',
  partial: 'var(--tk-warning)',
  failed: 'var(--tk-error)',
  running: 'var(--tk-primary)',
};

/** 表单明细表格（含成功占比进度条 + 错误展开行） */
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
      width: 100,
      render: (v: string) => <SyncStatusTag status={v} />,
    },
    {
      title: '总记录',
      dataIndex: 'total_records',
      key: 'total_records',
      width: 90,
      render: (v: number) => (
        <Text style={{ fontVariantNumeric: 'tabular-nums' }}>{(v || 0).toLocaleString()}</Text>
      ),
    },
    {
      title: '写入',
      key: 'written',
      width: 130,
      render: (_: unknown, r: RunFormDetail) => {
        const written = (r.inserted || 0) + (r.updated || 0);
        const total = r.total_records || 0;
        const pct = total > 0 ? Math.round((written / total) * 100) : 100;
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Progress
              percent={pct}
              size="small"
              showInfo={false}
              strokeColor={STATUS_BAR_COLOR[r.status] || 'var(--tk-primary)'}
              trailColor="rgba(148, 163, 184, 0.15)"
              style={{ flex: 1, minWidth: 40, margin: 0 }}
            />
            <Text style={{ fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>
              {written.toLocaleString()}
            </Text>
          </div>
        );
      },
    },
    {
      title: '失败',
      dataIndex: 'failed',
      key: 'failed',
      width: 80,
      render: (v: number) => (
        <Text
          style={{
            color: v > 0 ? 'var(--tk-error)' : 'var(--tk-muted)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {(v || 0).toLocaleString()}
        </Text>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 90,
      render: (v: number) => (
        <Text style={{ fontVariantNumeric: 'tabular-nums' }}>{formatDuration(v)}</Text>
      ),
    },
  ];

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <Text strong style={{ color: 'var(--tk-text)' }}>
          表单明细
        </Text>
        <span
          style={{
            fontSize: 11,
            color: 'var(--tk-muted)',
            background: 'rgba(148, 163, 184, 0.1)',
            border: '1px solid rgba(148, 163, 184, 0.15)',
            borderRadius: 999,
            padding: '1px 10px',
          }}
        >
          {forms.length} 个
        </span>
      </div>
      <Table<RunFormDetail>
        columns={columns}
        dataSource={forms}
        rowKey="form_name"
        size="small"
        pagination={false}
        scroll={{ y: 300 }}
        expandable={{
          rowExpandable: (r) => !!r.error_message,
          expandedRowRender: (r) => (
            <Paragraph
              className="!mb-0"
              style={{
                fontSize: 12,
                color: 'var(--tk-error)',
                whiteSpace: 'pre-wrap',
                background: 'rgba(248, 113, 113, 0.06)',
                borderRadius: 8,
                padding: '8px 12px',
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
