import { ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Button,
  DatePicker,
  Select,
  Table,
  Typography,
} from 'antd';
import type dayjs from 'dayjs';
import React, { useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import { listRuns } from '@/services/v1';
import type { V1Run } from '@/services/v1';
import { formatDuration } from '@/utils/format';
import type { HistoryRun } from '../types';

/** V1Run → HistoryRun 兼容转换 */
function toHistoryRun(v1: V1Run): HistoryRun {
  return {
    id: 0,
    run_id: v1.run_id,
    task_name: v1.sync_type,
    sync_type: v1.sync_type,
    status: v1.status,
    start_time: v1.started_at || '',
    end_time: v1.finished_at,
    duration_seconds: v1.duration_seconds,
    total_records: v1.total_records,
    success_records: v1.success_records,
    failed_records: v1.failed_records,
    form_count: v1.form_count,
    success_forms: v1.success_forms,
    failed_forms: v1.failed_forms,
  };
}
import RunDetailDrawer from './RunDetailDrawer';

const { RangePicker } = DatePicker;
const { Text } = Typography;

interface HistoryTableProps {
  loading?: boolean;
}

/**
 * 同步历史列表：强筛选 + 关键指标列。
 *
 * （原因：运维人员需要详细追溯历史运行记录）
 */
const HistoryTable: React.FC<HistoryTableProps> = ({ loading }) => {
  const [filters, setFilters] = useState({
    status: '',
    syncType: '',
    dateRange: [null, null] as [dayjs.Dayjs | null, dayjs.Dayjs | null],
  });
  const [page, setPage] = useState({ current: 1, pageSize: 10 });

  // 构建请求参数
  const params = useMemo(() => {
    const p: { page?: number; page_size?: number; status?: string; sync_type?: string; from_date?: string; to_date?: string } = {
      page: page.current,
      page_size: page.pageSize,
    };
    // search 参数保留在 queryKey 中但不传给 v1 API（v1 无 search 支持）
    if (filters.status) p.status = filters.status;
    if (filters.syncType) p.sync_type = filters.syncType;
    // search 参数保留在 queryKey 中但不传给 v1 API（v1 无 search 支持）
    if (filters.dateRange[0] && filters.dateRange[1]) {
      p.from_date = filters.dateRange[0].format('YYYY-MM-DD');
      p.to_date = filters.dateRange[1].format('YYYY-MM-DD');
    }
    return p;
  }, [filters, page]);

  // params 作为 queryKey 一部分，筛选/分页变化自动重取；
  // 数据直接从查询结果派生（移除原 onSuccess + useState 复制模式）
  const req = useQuery({
    queryKey: ['v1', 'runs', 'history', params],
    queryFn: () => listRuns(params),
  });

  const data: HistoryRun[] = (req.data?.data ?? []).map(toHistoryRun);
  const total = req.data?.meta?.total ?? 0;
  // 当前钻取的 run_id（行点击打开详情抽屉）
  const [detailRunId, setDetailRunId] = useState<string | null>(null);

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
      title: '表单成功率',
      key: 'form_rate',
      width: 110,
      render: (_: unknown, record: HistoryRun) => {
        if (!record.form_count) return '-';
        const rate = Math.round(
          (record.success_forms / record.form_count) * 100,
        );
        const color =
          rate === 100 ? 'var(--tk-success)' : rate >= 50 ? 'var(--tk-warning)' : 'var(--tk-error)';
        return (
          <Text style={{ color }}>
            {record.success_forms}/{record.form_count} ({rate}%)
          </Text>
        );
      },
    },
    {
      title: '记录数',
      dataIndex: 'total_records',
      key: 'total_records',
      width: 120,
      render: (v: number) => v?.toLocaleString() || '-',
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

  const handleReset = () => {
    setFilters({ status: '', syncType: '', dateRange: [null, null] });
    setPage({ current: 1, pageSize: 10 });
  };

  return (
    <Panel
      title="同步历史"
      extra={
        <Button
          size="small"
          onClick={() => req.refetch()}
          icon={<ReloadOutlined />}
        >
          刷新
        </Button>
      }
      loading={loading || req.isPending}
    >
      {/* 筛选栏 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 100 }}
          value={filters.status}
          onChange={(v) => {
            setFilters((f) => ({ ...f, status: v || '' }));
            setPage((p) => ({ ...p, current: 1 }));
          }}
          options={[
            { label: '成功', value: 'success' },
            { label: '失败', value: 'failed' },
            { label: '部分完成', value: 'partial' },
            { label: '运行中', value: 'running' },
          ]}
        />
        <Select
          placeholder="类型"
          allowClear
          style={{ width: 100 }}
          value={filters.syncType}
          onChange={(v) => {
            setFilters((f) => ({ ...f, syncType: v || '' }));
            setPage((p) => ({ ...p, current: 1 }));
          }}
          options={[
            { label: '增量', value: 'incremental' },
            { label: '全量', value: 'full' },
            { label: '重置', value: 'reset' },
          ]}
        />
        <RangePicker
          value={filters.dateRange.length ? filters.dateRange : undefined}
          onChange={(vals) => {
            const range = vals as [dayjs.Dayjs | null, dayjs.Dayjs | null];
            setFilters((f) => ({
              ...f,
              dateRange: range[0] && range[1] ? range : [null, null],
            }));
            setPage((p) => ({ ...p, current: 1 }));
          }}
          style={{ width: 240 }}
        />
        <Button size="small" onClick={handleReset}>
          重置
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="run_id"
        pagination={{
          current: page.current,
          pageSize: page.pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (current, pageSize) => setPage({ current, pageSize }),
        }}
        scroll={{ x: 900 }}
        size="small"
        onRow={(record) => ({
          onClick: () => setDetailRunId(record.run_id),
          style: { cursor: 'pointer' },
        })}
      />
      <RunDetailDrawer
        runId={detailRunId}
        onClose={() => setDetailRunId(null)}
      />
    </Panel>
  );
};

export default HistoryTable;
