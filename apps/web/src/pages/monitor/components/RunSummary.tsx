import { Typography } from 'antd';
import React from 'react';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import { formatDuration } from '@/utils/format';
import type { RunDetail } from '../types';

const { Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  success: 'var(--tk-success)',
  partial: 'var(--tk-warning)',
  failed: 'var(--tk-error)',
  failed_abnormal_exit: 'var(--tk-error)',
  running: 'var(--tk-primary)',
};

interface RunSummaryProps {
  detail: RunDetail;
}

const KpiCard: React.FC<{
  label: string;
  value: string;
  tone?: string;
}> = ({ label, value, tone = 'neutral' }) => (
  <div className={`monitor-summary-kpi monitor-summary-kpi--${tone}`}>
    <div className="monitor-summary-kpi__value">{value}</div>
    <div className="monitor-summary-kpi__label">{label}</div>
  </div>
);

const RunSummary: React.FC<RunSummaryProps> = ({ detail }) => {
  const accent = STATUS_COLOR[detail.status] || 'var(--tk-text)';
  const successRate =
    (detail.total_records || 0) > 0
      ? Math.round(((detail.success_records || 0) / detail.total_records) * 100)
      : 0;

  return (
    <div className="monitor-summary">
      <section className="monitor-summary-hero" aria-label="运行摘要">
        <div className="monitor-summary-hero__main">
          <span
            className="monitor-status-dot monitor-status-dot--large"
            style={{ backgroundColor: accent }}
            aria-hidden="true"
          />
          <div className="monitor-summary-hero__content">
            <div className="monitor-summary-hero__heading">
              <Text strong>本次运行</Text>
              <SyncStatusTag status={detail.status} />
              <SyncTypeTag type={detail.sync_type} />
            </div>
            <div className="monitor-summary-hero__meta">
              <Text code>{detail.run_id}</Text>
              <span>开始 {detail.start_time || '-'}</span>
              <span>结束 {detail.end_time || '-'}</span>
              <span>耗时 {formatDuration(detail.duration_seconds)}</span>
            </div>
          </div>
        </div>
        {detail.error_message && (
          <div className="monitor-summary-hero__error" role="alert">
            {detail.error_message}
          </div>
        )}
      </section>

      <div className="monitor-summary-kpis">
        <KpiCard
          label="总记录"
          value={(detail.total_records || 0).toLocaleString()}
        />
        <KpiCard
          label="成功记录"
          value={(detail.success_records || 0).toLocaleString()}
          tone="success"
        />
        <KpiCard
          label="失败记录"
          value={(detail.failed_records || 0).toLocaleString()}
          tone={(detail.failed_records || 0) > 0 ? 'error' : 'neutral'}
        />
        <KpiCard
          label="成功表单 / 总表单"
          value={`${detail.success_forms || 0}/${detail.form_count || 0}`}
          tone="primary"
        />
        <KpiCard
          label="记录成功率"
          value={`${successRate}%`}
          tone={
            successRate === 100
              ? 'success'
              : successRate >= 60
                ? 'warning'
                : 'error'
          }
        />
      </div>
    </div>
  );
};

export { RunSummary };
