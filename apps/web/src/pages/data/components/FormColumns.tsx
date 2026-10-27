import { SettingOutlined } from '@ant-design/icons';
import { Button, Switch, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import SyncStatusTag from '@/components/SyncStatusTag';
import type { FormItem, FormStat } from '../types';

interface FormColumnsDeps {
  statsMap: Map<string, FormStat>;
  updating?: boolean;
  onToggle: (formName: string, enabled: boolean) => void;
  onEdit: (form: FormItem) => void;
}

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
    width: 240,
    fixed: 'left',
    render: (value: string) => (
      <Typography.Text
        className="data-form-name"
        strong
        ellipsis={{ tooltip: value }}
      >
        {value}
      </Typography.Text>
    ),
  },
  {
    title: '同步开关',
    dataIndex: 'enabled',
    key: 'enabled',
    width: 96,
    render: (enabled: boolean, record: FormItem) => (
      <div
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <Switch
          aria-label={`${enabled ? '禁用' : '启用'} ${record.form_name}`}
          checked={enabled}
          size="small"
          loading={updating}
          onChange={(value) => onToggle(record.form_name, value)}
        />
      </div>
    ),
  },
  {
    title: '上次状态',
    dataIndex: 'last_status',
    key: 'last_status',
    width: 112,
    render: (value: string) => <SyncStatusTag status={value} />,
  },
  {
    title: '上次同步',
    dataIndex: 'last_sync_time',
    key: 'last_sync_time',
    width: 168,
    render: (value: string) => (
      <span className={value ? 'data-sync-time' : 'data-empty-value'}>
        {value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '尚未同步'}
      </span>
    ),
  },
  {
    title: '记录数',
    key: 'record_count',
    width: 120,
    align: 'right',
    className: 'data-number-cell',
    render: (_: unknown, record: FormItem) => {
      const stat = statsMap.get(record.form_name);
      return (stat?.total_records || record.record_count || 0).toLocaleString();
    },
  },
  {
    title: '错误数',
    key: 'error_count',
    width: 96,
    align: 'right',
    className: 'data-number-cell',
    render: (_: unknown, record: FormItem) => {
      const stat = statsMap.get(record.form_name);
      const count = stat?.failed_records || record.error_count || 0;
      return (
        <span className={count > 0 ? 'data-error-count' : 'data-empty-value'}>
          {count}
        </span>
      );
    },
  },
  {
    title: '配置',
    key: 'action',
    width: 72,
    fixed: 'right',
    align: 'center',
    render: (_: unknown, record: FormItem) => (
      <Tooltip title="编辑字段配置">
        <Button
          type="text"
          size="small"
          aria-label={`配置 ${record.form_name}`}
          icon={<SettingOutlined />}
          onClick={(event) => {
            event.stopPropagation();
            onEdit(record);
          }}
        />
      </Tooltip>
    ),
  },
];

export type { FormColumnsDeps };
export { useFormColumns };
