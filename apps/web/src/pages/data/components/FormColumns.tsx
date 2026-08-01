import { SettingOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { Button, Switch } from 'antd';
import dayjs from 'dayjs';
import SyncStatusTag from '@/components/SyncStatusTag';
import type { FormItem, FormStat } from '../../data/types';

interface FormColumnsDeps {
  statsMap: Map<string, FormStat>;
  updating?: boolean;
  onToggle: (formName: string, enabled: boolean) => void;
  onEdit: (form: FormItem) => void;
}

/** 表单管理表格列定义（抽离 FormsManager 的 columns 数组） */
const useFormColumns = ({
  statsMap,
  updating,
  onToggle,
  onEdit,
}: FormColumnsDeps): ColumnsType<FormItem> => [
  {
    title: '表单名称',
    dataIndex: 'form_name',
    key: 'form_name',
    width: 200,
    render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span>,
  },
  {
    title: '启用',
    dataIndex: 'enabled',
    key: 'enabled',
    width: 80,
    render: (enabled: boolean, record: FormItem) => (
      <Switch
        checked={enabled}
        size="small"
        loading={updating}
        onChange={(v) => onToggle(record.form_name, v)}
      />
    ),
  },
  {
    title: '上次状态',
    dataIndex: 'last_status',
    key: 'last_status',
    width: 100,
    render: (v: string) => <SyncStatusTag status={v} />,
  },
  {
    title: '上次同步',
    dataIndex: 'last_sync_time',
    key: 'last_sync_time',
    width: 160,
    render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm:ss') : '-',
  },
  {
    title: '记录数',
    key: 'record_count',
    width: 120,
    render: (_: unknown, record: FormItem) => {
      const stat = statsMap.get(record.form_name);
      return (stat?.total_records || record.record_count || 0).toLocaleString();
    },
  },
  {
    title: '错误数',
    key: 'error_count',
    width: 100,
    render: (_: unknown, record: FormItem) => {
      const stat = statsMap.get(record.form_name);
      const count = stat?.failed_records || record.error_count || 0;
      return (
        <span style={{ color: count > 0 ? 'var(--tk-error)' : 'var(--tk-muted)' }}>
          {count}
        </span>
      );
    },
  },
  {
    title: '操作',
    key: 'action',
    width: 80,
    render: (_: unknown, record: FormItem) => (
      <Button
        type="text"
        size="small"
        icon={<SettingOutlined />}
        onClick={() => onEdit(record)}
      />
    ),
  },
];

export { useFormColumns };
export type { FormColumnsDeps };
