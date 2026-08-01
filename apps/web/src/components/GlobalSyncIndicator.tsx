import { StopOutlined } from '@ant-design/icons';
import { useNavigate } from '@umijs/max';
import { useMutation, useQuery } from '@tanstack/react-query';
import { App, FloatButton, Space, Tooltip } from 'antd';
import React, { useEffect, useState } from 'react';
import { getOverview } from '@/services/v1';
import type { V1Run } from '@/services/v1';
import {
  SyncStatusContent,
  syncButtonBg,
  syncButtonBorder,
  syncIconForStatus,
} from './SyncStatusContent';
import type { SyncStatus } from './SyncStatusContent';

const TERMINAL_STATUSES: SyncStatus[] = [
  'success',
  'failed',
  'partial',
  'stopped',
  'failed_abnormal_exit',
];

interface SyncInfo {
  run_id: string;
  status: SyncStatus;
  progress: number;
  current_form: string;
  message: string;
  elapsed_seconds: number;
}

/**
 * 全局同步状态指示器 — v1 版。
 *
 * 使用 v1 overview 端点获取 active_run 作为当前同步状态。
 * 停止操作暂用旧接口（v1 尚无 stop 端点）。
 */
const GlobalSyncIndicator: React.FC = () => {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const [boundRunId, setBoundRunId] = useState('');

  const overviewReq = useQuery({
    queryKey: ['overview'],
    queryFn: getOverview,
    refetchInterval: 3000,
  });
  const activeRun: V1Run | undefined = overviewReq.data?.active_run;

  const info: SyncInfo = {
    run_id: activeRun?.run_id || '',
    status: (activeRun?.status || 'idle') as SyncStatus,
    progress: 0,
    current_form: '',
    message: activeRun?.error_message || '',
    elapsed_seconds: activeRun?.duration_seconds ?? 0,
  };
  const { status } = info;

  useEffect(() => {
    if (activeRun?.run_id && !boundRunId) {
      setBoundRunId(activeRun.run_id);
    } else if (
      boundRunId &&
      status !== 'running' &&
      status !== 'stopping'
    ) {
      setBoundRunId('');
    }
  }, [activeRun?.run_id, boundRunId, status]);

  useEffect(() => {
    if (status === 'running' || status === 'stopping') {
      setVisible(true);
      return () => {};
    }
    if (status === 'idle') {
      setVisible(false);
      return () => {};
    }
    if (TERMINAL_STATUSES.includes(status)) {
      setVisible(true);
      const timeout = setTimeout(
        () => setVisible(false),
        status === 'success' ? 3000 : 5000,
      );
      return () => clearTimeout(timeout);
    }
    return () => {};
  }, [status]);

  const stopMutation = useMutation({
    mutationFn: async (runId: string) => {
      await import('@/services/api').then(m => m.stopSync(runId));
    },
    onSuccess: () => message.success('同步已停止'),
    onError: () => message.error('停止同步失败'),
  });

  if (!visible) return null;

  const icon = syncIconForStatus(status);
  const tooltipContent = <SyncStatusContent {...info} />;

  return (
    <Space
      orientation="vertical"
      size={8}
      style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1000 }}
    >
      <Tooltip title={tooltipContent} placement="topLeft" mouseEnterDelay={0}>
        <FloatButton
          icon={icon}
          style={{
            backgroundColor: syncButtonBg(status),
            borderColor: syncButtonBorder(status),
          }}
          onClick={() => navigate('/sync')}
        />
      </Tooltip>

      {status === 'running' && info.run_id && (
        <Tooltip title="停止同步" placement="left">
          <FloatButton
            icon={<StopOutlined style={{ fontSize: 14 }} />}
            style={{
              backgroundColor: '#7f1d1d',
              borderColor: 'var(--tk-error)',
              width: 36,
              height: 36,
            }}
            onClick={(e) => {
              e.stopPropagation();
              stopMutation.mutate(info.run_id);
            }}
          />
        </Tooltip>
      )}
    </Space>
  );
};

export default GlobalSyncIndicator;
