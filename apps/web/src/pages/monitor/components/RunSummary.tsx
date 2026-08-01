import { Typography } from 'antd';
import React from 'react';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import { formatDuration } from '@/utils/format';
import type { RunDetail } from '../types';

const { Text } = Typography;

/** 状态 → 主色（Hero 发光点与数字强调色） */
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

/** KPI 指标卡：大数字 + 小标签 */
const KpiCard: React.FC<{
  label: string;
  value: string;
  color?: string;
}> = ({ label, value, color }) => (
  <div className="glass-card" style={{ padding: '12px 14px', minWidth: 0 }}>
    <div
      style={{
        fontSize: 22,
        fontWeight: 700,
        lineHeight: 1.2,
        color: color || 'var(--tk-text)',
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      {value}
    </div>
    <div style={{ fontSize: 12, color: 'var(--tk-muted)', marginTop: 2 }}>{label}</div>
  </div>
);

/**
 * 运行摘要：Hero 状态区 + KPI 指标卡。
 */
const RunSummary: React.FC<RunSummaryProps> = ({ detail }) => {
  const accent = STATUS_COLOR[detail.status] || 'var(--tk-text)';
  const successRate =
    (detail.total_records || 0) > 0
      ? Math.round(((detail.success_records || 0) / detail.total_records) * 100)
      : 0;

  return (
    <div className="space-y-4">
      {/* Hero 状态区 */}
      <div className="glass-card" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* 发光状态圆点 */}
          <span
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: accent,
              boxShadow: `0 0 0 4px ${accent}22, 0 0 14px ${accent}66`,
              flexShrink: 0,
            }}
          />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <Text
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: 'var(--tk-text)',
                  lineHeight: 1.3,
                }}
              >
                运行详情
              </Text>
              <SyncStatusTag status={detail.status} />
              <SyncTypeTag type={detail.sync_type} />
            </div>
            <div
              style={{
                marginTop: 6,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
                fontSize: 12,
                color: 'var(--tk-muted)',
              }}
            >
              <Text code style={{ fontSize: 12 }}>
                {detail.run_id}
              </Text>
              <span>开始 {detail.start_time || '-'}</span>
              <span>结束 {detail.end_time || '-'}</span>
              <span>耗时 {formatDuration(detail.duration_seconds)}</span>
            </div>
          </div>
        </div>
        {detail.error_message && (
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--tk-error)',
              background: 'rgba(248, 113, 113, 0.08)',
              border: '1px solid rgba(248, 113, 113, 0.2)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {detail.error_message}
          </div>
        )}
      </div>

      {/* KPI 指标卡 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: 10,
        }}
      >
        <KpiCard label="总记录" value={(detail.total_records || 0).toLocaleString()} color="var(--tk-text)" />
        <KpiCard label="成功记录" value={(detail.success_records || 0).toLocaleString()} color="var(--tk-success)" />
        <KpiCard
          label="失败记录"
          value={(detail.failed_records || 0).toLocaleString()}
          color={(detail.failed_records || 0) > 0 ? 'var(--tk-error)' : 'var(--tk-text)'}
        />
        <KpiCard label="表单" value={`${detail.success_forms || 0}/${detail.form_count || 0}`} color="var(--tk-primary)" />
        <KpiCard
          label="成功率"
          value={`${successRate}%`}
          color={successRate === 100 ? 'var(--tk-success)' : successRate >= 60 ? 'var(--tk-warning)' : 'var(--tk-error)'}
        />
      </div>
    </div>
  );
};

export { RunSummary };
