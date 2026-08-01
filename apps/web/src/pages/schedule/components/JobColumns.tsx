import {
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { Button, Popconfirm, Space, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React from 'react';
import type { ScheduleJob } from '../types';
import { parseForms } from '../types';
import { formatCron } from '../cron';

interface JobColumnsDeps {
  onEdit: (job: ScheduleJob) => void;
  onDelete: (id: number) => void;
  deleting: boolean;
}

/** 定时任务表格列定义 */
const useJobColumns = ({
  onEdit,
  onDelete,
  deleting,
}: JobColumnsDeps): ColumnsType<ScheduleJob> => {
  const isDefaultJob = (name: string) => name === 'default_incremental';

  return [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (v: string) => (
        <Space>
          <span style={{ fontWeight: 600 }}>{v}</span>
          {isDefaultJob(v) && <Tag color="orange">默认</Tag>}
        </Space>
      ),
    },
    {
      title: '关联表单',
      key: 'forms',
      width: 200,
      render: (_: unknown, record: ScheduleJob) => {
        const forms = parseForms(record.forms);
        if (forms.length === 0)
          return <span style={{ color: 'var(--tk-dim)' }}>全部</span>;
        return (
          <span style={{ fontSize: 12, color: 'var(--tk-muted)' }}>
            {forms.join(', ')}
          </span>
        );
      },
    },
    {
      title: '执行频率',
      dataIndex: 'cron_expr',
      key: 'cron_expr',
      width: 160,
      render: (v: string) => (
        <span style={{ fontSize: 12 }}>{formatCron(v)}</span>
      ),
    },
    {
      title: '同步类型',
      dataIndex: 'sync_type',
      key: 'sync_type',
      width: 100,
      render: (v: string) => (
        <Tag color={v === 'incremental' ? 'blue' : 'green'}>
          {v === 'incremental' ? '增量' : '全量'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 90,
      render: (enabled: boolean) =>
        enabled ? (
          <Tag icon={<CheckCircleOutlined />} color="success">
            已启用
          </Tag>
        ) : (
          <Tag color="default">已禁用</Tag>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: ScheduleJob) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
          />
          {!isDefaultJob(record.name) && (
            <Popconfirm
              title="确定删除此任务？"
              onConfirm={() => onDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                loading={deleting}
              />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];
};

export { useJobColumns };
export type { JobColumnsDeps };
