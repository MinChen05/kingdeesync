import { CloseOutlined, RedoOutlined } from '@ant-design/icons';
import { Link } from '@umijs/max';
import { Select, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React from 'react';
import { DotIndicator } from '@/components/DotIndicator';
import type { V1RunEvent } from '@/services/v1';

const { Text } = Typography;

const LEVEL_META: Record<
  string,
  { color: string; text: string; dot: 'ok' | 'error' | 'unknown' }
> = {
  ERROR: { color: 'var(--tk-error)', text: '错误', dot: 'error' },
  WARNING: { color: 'var(--tk-warning)', text: '警告', dot: 'unknown' },
  INFO: { color: 'var(--tk-primary)', text: '信息', dot: 'ok' },
};

/** 日志列定义（含级别指示灯渲染） */
const useLogColumns = (): ColumnsType<V1RunEvent> => [
  {
    title: '级别',
    dataIndex: 'level',
    key: 'level',
    width: 90,
    render: (v: string) => {
      const meta =
        LEVEL_META[v] || { color: 'var(--tk-dim)', text: v, dot: 'unknown' };
      return (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: meta.color,
          }}
        >
          <DotIndicator level={meta.dot} />
          {meta.text}
        </span>
      );
    },
  },
  {
    title: '表单',
    dataIndex: 'form_name',
    key: 'form_name',
    width: 180,
    render: (v: string) => (
      <Text strong style={{ color: 'var(--tk-text)', fontSize: 13 }}>
        {v || '-'}
      </Text>
    ),
  },
  {
    title: '错误信息',
    dataIndex: 'message',
    key: 'message',
    ellipsis: true,
    render: (v: string) => <span style={{ fontSize: 13 }}>{v || '-'}</span>,
  },
  {
    title: '时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 165,
    render: (v: string) => (
      <Text type="secondary" style={{ fontSize: 12 }}>
        {v || '-'}
      </Text>
    ),
  },
  {
    title: '操作',
    key: 'action',
    width: 100,
    render: (_: unknown, record: V1RunEvent) =>
      record.form_name ? (
        <Link
          to={`/sync?forms=${encodeURIComponent(record.form_name)}`}
          style={{ fontSize: 12, color: 'var(--tk-primary)' }}
        >
          <RedoOutlined /> 重跑此表
        </Link>
      ) : null,
  },
];

/** 日志筛选栏 */
interface LogFilterBarProps {
  focusForm: string;
  level: string;
  days: number;
  logCount: number;
  onLevelChange: (v: string) => void;
  onDaysChange: (v: number) => void;
  onClearFocusForm: () => void;
}

const LogFilterBar: React.FC<LogFilterBarProps> = ({
  focusForm,
  level,
  days,
  logCount,
  onLevelChange,
  onDaysChange,
  onClearFocusForm,
}) => {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-3">
      {focusForm && (
        <Tag
          closable
          closeIcon={<CloseOutlined />}
          onClose={onClearFocusForm}
          color="blue"
          style={{ marginInlineEnd: 0 }}
        >
          表单：{focusForm}
        </Tag>
      )}
      <Select
        value={level}
        onChange={onLevelChange}
        size="small"
        style={{ width: 110 }}
        options={[
          { value: '', label: '全部级别' },
          { value: 'ERROR', label: '仅错误' },
          { value: 'WARNING', label: '仅警告' },
        ]}
      />
      <Select
        value={days}
        onChange={onDaysChange}
        size="small"
        style={{ width: 110 }}
        options={[
          { value: 1, label: '近 1 天' },
          { value: 3, label: '近 3 天' },
          { value: 7, label: '近 7 天' },
          { value: 30, label: '近 30 天' },
        ]}
      />
      <Text type="secondary" style={{ fontSize: 12, marginLeft: 'auto' }}>
        共 {logCount} 条
      </Text>
    </div>
  );
};

export { useLogColumns, LogFilterBar };
export type { LogFilterBarProps };
