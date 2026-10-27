import {
  ArrowRightOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  ExclamationCircleFilled,
  HistoryOutlined,
} from '@ant-design/icons';
import { Link } from '@umijs/max';
import React from 'react';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import type { V1Run } from '@/services/v1';
import { formatDuration } from '@/utils/format';

interface LastSyncSummaryProps {
  run?: V1Run;
  loading?: boolean;
}

const LastSyncSummary: React.FC<LastSyncSummaryProps> = ({ run, loading }) => {
  if (loading || !run) {
    return (
      <Panel title="最近执行" loading={loading}>
        <div className="sync-last-empty">
          <HistoryOutlined />
          <span>暂无同步记录，首次执行结果将显示在这里</span>
        </div>
      </Panel>
    );
  }

  const isSuccess = run.status === 'success';
  const isFailed = ['failed', 'failed_abnormal_exit'].includes(run.status);
  const tone = isSuccess ? 'success' : isFailed ? 'error' : 'warning';
  const statusIcon = isSuccess ? (
    <CheckCircleFilled />
  ) : isFailed ? (
    <CloseCircleFilled />
  ) : (
    <ExclamationCircleFilled />
  );

  return (
    <Panel
      title="最近执行"
      extra={
        <Link to="/monitor" className="sync-history-link">
          执行历史 <ArrowRightOutlined />
        </Link>
      }
    >
      <div className="sync-last-run">
        <div className="sync-last-run-main">
          <span className={`sync-last-run-icon is-${tone}`}>{statusIcon}</span>
          <div className="sync-last-run-copy">
            <div className="sync-last-run-tags">
              <SyncStatusTag status={run.status} />
              <SyncTypeTag type={run.sync_type} />
            </div>
            <span className="sync-last-run-id" title={run.run_id}>
              {run.run_id}
            </span>
          </div>
          <time className="sync-last-run-time">{run.started_at || '-'}</time>
        </div>
        <div className="sync-last-run-metrics">
          <div>
            <span>处理记录</span>
            <strong>{(run.total_records || 0).toLocaleString()}</strong>
            <small>条</small>
          </div>
          <div>
            <span>成功表单</span>
            <strong>{run.success_forms || 0}</strong>
            <small>/ {run.form_count || 0}</small>
          </div>
          <div>
            <span>执行耗时</span>
            <strong>{formatDuration(run.duration_seconds)}</strong>
          </div>
        </div>
      </div>
    </Panel>
  );
};

export default LastSyncSummary;
