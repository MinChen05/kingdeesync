import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  ExclamationCircleFilled,
  PauseCircleFilled,
  SyncOutlined,
} from '@ant-design/icons';
import { Progress } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import { formatDuration } from '@/utils/format';
import type { FormStat, SyncStatusInfo } from '../types';

interface SyncProgressPanelProps {
  status: SyncStatusInfo;
}

const SyncProgressPanel: React.FC<SyncProgressPanelProps> = ({ status }) => {
  const isRunning = ['running', 'stopping'].includes(status.status);
  const isIdle = status.status === 'idle';
  const isFailed = ['failed', 'failed_abnormal_exit'].includes(status.status);
  const isWarning = ['partial', 'stopped'].includes(status.status);
  const percent = Math.min(100, Math.max(0, Math.round(status.progress || 0)));
  const successfulForms = status.form_stats.filter(
    (item) => item.status === 'success',
  ).length;
  const failedForms = status.form_stats.filter(
    (item) => item.status === 'failed',
  ).length;

  const statusIcon = isRunning ? (
    <SyncOutlined spin={status.status === 'running'} />
  ) : status.status === 'success' ? (
    <CheckCircleFilled />
  ) : isFailed ? (
    <CloseCircleFilled />
  ) : isWarning ? (
    <ExclamationCircleFilled />
  ) : (
    <PauseCircleFilled />
  );

  const tone = isFailed
    ? 'error'
    : isWarning
      ? 'warning'
      : status.status === 'success'
        ? 'success'
        : 'primary';

  return (
    <Panel
      title="执行进度"
      extra={
        status.run_id ? (
          <span className="sync-run-id" title={status.run_id}>
            {status.run_id}
          </span>
        ) : (
          <span className="sync-progress-extra">实时更新</span>
        )
      }
    >
      <div className={`sync-progress-content is-${isIdle ? 'idle' : tone}`}>
        <div className="sync-progress-overview">
          <div className="sync-progress-icon" aria-hidden="true">
            {isIdle ? <ClockCircleOutlined /> : statusIcon}
          </div>
          <div className="sync-progress-copy">
            <div className="sync-progress-status">
              <SyncStatusTag status={status.status} />
              <span aria-live="polite">
                {isIdle
                  ? '配置任务后即可开始'
                  : status.current_form || status.message || '等待执行明细'}
              </span>
            </div>
            <div className="sync-progress-meta">
              <span>
                已用时 <strong>{formatDuration(status.elapsed_seconds)}</strong>
              </span>
              {status.form_stats.length > 0 && (
                <>
                  <span>{successfulForms} 个成功</span>
                  {failedForms > 0 && (
                    <span className="is-error">{failedForms} 个失败</span>
                  )}
                </>
              )}
            </div>
          </div>
          <div className="sync-progress-number">
            <strong>{isIdle ? '—' : percent}</strong>
            {!isIdle && <span>%</span>}
          </div>
        </div>

        <Progress
          percent={percent}
          status={
            isFailed
              ? 'exception'
              : status.status === 'success'
                ? 'success'
                : isRunning
                  ? 'active'
                  : 'normal'
          }
          showInfo={false}
          size={['100%', 8]}
          className="sync-progress-bar"
        />

        {!isIdle && (
          <div className="sync-form-progress">
            <div className="sync-form-progress-heading">
              <span>表单执行明细</span>
              <span>{status.form_stats.length} 项</span>
            </div>
            {status.form_stats.length > 0 ? (
              <div className="sync-form-progress-list">
                {status.form_stats.map((formStat: FormStat) => {
                  const formTone =
                    formStat.status === 'success'
                      ? 'success'
                      : formStat.status === 'failed'
                        ? 'error'
                        : 'pending';
                  return (
                    <div
                      key={formStat.form_name}
                      className={`sync-form-stat is-${formTone}`}
                    >
                      <div className="sync-form-stat-name">
                        <span className="sync-form-stat-dot" />
                        <strong>{formStat.form_name}</strong>
                        <span>{formatDuration(formStat.duration_sec)}</span>
                      </div>
                      <div className="sync-form-stat-metrics">
                        <span>
                          拉取 <strong>{formStat.fetched}</strong>
                        </span>
                        <span>
                          写入 <strong>{formStat.inserted}</strong>
                        </span>
                        <span className={formStat.errors > 0 ? 'is-error' : ''}>
                          错误 <strong>{formStat.errors}</strong>
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="sync-form-progress-empty" aria-live="polite">
                执行明细将在任务处理表单后显示
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
};

export default SyncProgressPanel;
