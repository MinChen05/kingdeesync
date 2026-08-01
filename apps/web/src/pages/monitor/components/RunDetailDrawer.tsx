import { useQuery } from '@tanstack/react-query';
import { Drawer, Empty, Typography } from 'antd';
import React from 'react';
import { getRun } from '@/services/v1';
import type { V1Run } from '@/services/v1';
import type { RunDetail } from '../types';

/** V1Run → RunDetail 兼容转换 */
function toRunDetail(v1: V1Run): RunDetail {
  return {
    id: 0,
    run_id: v1.run_id,
    task_name: v1.sync_type,
    sync_type: v1.sync_type,
    status: v1.status as import('@/services/generated-api').SyncStatus,
    start_time: v1.started_at || '',
    end_time: v1.finished_at || '',
    duration_seconds: v1.duration_seconds,
    total_records: v1.total_records,
    success_records: v1.success_records,
    failed_records: v1.failed_records,
    form_count: v1.form_count,
    success_forms: v1.success_forms,
    failed_forms: v1.failed_forms,
    error_message: v1.error_message,
    forms: (v1.forms ?? []).map(f => ({
      run_id: v1.run_id,
      form_name: f.form_name,
      status: f.status as import('@/services/generated-api').SyncStatus,
      total_records: f.total_records,
      inserted: f.inserted,
      updated: f.updated,
      deleted: f.deleted,
      failed: f.failed,
      skipped: f.skipped,
      duration_seconds: f.duration_seconds,
      error_message: f.error_message,
    })),
    errors: (v1.errors ?? []).map(e => ({
      run_id: v1.run_id,
      form_name: e.form_name,
      level: e.level,
      message: e.message,
      detail: e.detail || '',
      created_at: e.created_at,
    })),
  };
}
import { FormDetailTable } from './FormDetailTable';
import { RunErrorList } from './RunErrorList';
import { RunSummary } from './RunSummary';

const { Text } = Typography;

/** 状态 → 标题发光点颜色 */
const STATUS_DOT_COLOR: Record<string, string> = {
  success: 'var(--tk-success)',
  partial: 'var(--tk-warning)',
  failed: 'var(--tk-error)',
  failed_abnormal_exit: 'var(--tk-error)',
  running: 'var(--tk-primary)',
};

interface RunDetailDrawerProps {
  runId: string | null;
  onClose: () => void;
}

/**
 * 运行详情抽屉：单次同步运行的完整钻取视图。
 */
const RunDetailDrawer: React.FC<RunDetailDrawerProps> = ({
  runId,
  onClose,
}) => {
  const detailReq = useQuery({
    queryKey: ['v1', 'run', runId],
    queryFn: () => getRun(runId as string),
    enabled: !!runId,
  });
  const loading = detailReq.isPending;
  const detail: RunDetail | undefined = detailReq.data ? toRunDetail(detailReq.data) : undefined;
  const dotColor = detail ? STATUS_DOT_COLOR[detail.status] || 'var(--tk-text)' : 'var(--tk-primary)';

  return (
    <Drawer
      title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* 状态发光点 */}
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: dotColor,
              boxShadow: `0 0 0 3px ${dotColor}22, 0 0 10px ${dotColor}55`,
              flexShrink: 0,
            }}
          />
          <span style={{ fontSize: 15, fontWeight: 600 }}>运行详情</span>
          {detail && (
            <Text code style={{ fontSize: 12 }}>
              {detail.run_id}
            </Text>
          )}
        </span>
      }
      width={760}
      open={!!runId}
      onClose={onClose}
      loading={loading}
      styles={{ body: { paddingTop: 16 } }}
    >
      {detail ? (
        <div className="space-y-4">
          <RunSummary detail={detail} />
          <FormDetailTable forms={detail.forms || []} />
          <RunErrorList errors={detail.errors || []} />
        </div>
      ) : (
        !loading && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="未找到运行详情"
          />
        )
      )}
    </Drawer>
  );
};

export default RunDetailDrawer;
