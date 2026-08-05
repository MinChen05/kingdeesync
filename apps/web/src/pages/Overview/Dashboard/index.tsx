import { useQuery } from '@tanstack/react-query';
import { Button, Typography } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { DotIndicator } from '@/components/DotIndicator';
import type { V1Overview } from '@/services/v1';
import { getOverview } from '@/services/v1';
import { formatDuration, formatNumber } from '@/utils/format';

const { Text } = Typography;

/**
 * 管理看板大屏：全屏深色布局，30 秒自动刷新。
 * 复用 Overview 的 v1/overview 聚合数据。
 */
const DashboardPage: React.FC = () => {
  const [now, setNow] = useState(new Date());
  const { data: overview, isPending } = useQuery({
    queryKey: ['v1', 'overview'],
    queryFn: getOverview,
    refetchInterval: 30_000,
  });

  // Clock ticker
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  useEffect(() => {
    timerRef.current = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timerRef.current!);
  }, []);

  const health = overview?.health || {};
  const today = overview?.today || {};
  const recentRuns = overview?.recent_runs || [];

  if (isPending) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: '80px 0',
          color: 'var(--tk-dim)',
        }}
      >
        加载中...
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'var(--tk-bg)',
        minHeight: '100vh',
        padding: '24px 32px',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1
            style={{
              fontSize: 24,
              fontWeight: 700,
              color: '#e2e8f0',
              margin: 0,
            }}
          >
            金蝶数据同步看板
          </h1>
          <DotIndicator
            type={
              health.overall === 'ok'
                ? 'ok'
                : health.overall === 'degraded'
                  ? 'unknown'
                  : 'error'
            }
            size={12}
          />
        </div>
        <Text
          style={{
            fontSize: 14,
            color: 'var(--tk-muted)',
            fontFamily: 'monospace',
          }}
        >
          {now.toLocaleString('zh-CN')}
        </Text>
      </div>

      {/* KPI Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <KpiCard
          title="今日同步"
          value={formatNumber(today.total_runs || 0)}
          subtitle="次"
          color="#38bdf8"
        />
        <KpiCard
          title="成功表单"
          value={formatNumber(today.success_forms || 0)}
          subtitle="个"
          color="#34d399"
        />
        <KpiCard
          title="失败表单"
          value={formatNumber(today.failed_forms || 0)}
          subtitle="个"
          color="#f87171"
        />
        <KpiCard
          title="总数据量"
          value={formatNumber(today.total_records || 0)}
          subtitle="行"
          color="#a78bfa"
        />
      </div>

      {/* Service Health */}
      <div style={{ marginBottom: 24 }}>
        <h3
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: '#e2e8f0',
            marginBottom: 12,
          }}
        >
          服务健康
        </h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12,
          }}
        >
          <ServiceStatus
            name="金蝶 API"
            status={health.kingdee_api?.status || 'unknown'}
          />
          <ServiceStatus
            name="数据库"
            status={health.database?.status || 'unknown'}
          />
          <ServiceStatus
            name="调度器"
            status={health.scheduler?.status || 'unknown'}
          />
          <ServiceStatus
            name="日志服务"
            status={health.log_service?.status || 'unknown'}
          />
        </div>
      </div>

      {/* Recent Runs */}
      <div>
        <h3
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: '#e2e8f0',
            marginBottom: 12,
          }}
        >
          最近运行
        </h3>
        <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
          {recentRuns.length === 0 ? (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                color: 'var(--tk-dim)',
              }}
            >
              暂无运行记录
            </div>
          ) : (
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 13,
              }}
            >
              <thead>
                <tr
                  style={{ borderBottom: '1px solid rgba(148,163,184,0.08)' }}
                >
                  {['状态', '类型', '表单', '数据量', '耗时', '时间'].map(
                    (h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: 'left',
                          padding: '10px 16px',
                          color: 'var(--tk-dim)',
                          fontWeight: 500,
                        }}
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {recentRuns.slice(0, 8).map((run) => (
                  <tr
                    key={run.run_id}
                    style={{ borderBottom: '1px solid rgba(148,163,184,0.04)' }}
                  >
                    <td style={{ padding: '8px 16px' }}>
                      <DotIndicator
                        type={
                          run.status === 'success'
                            ? 'ok'
                            : run.status === 'partial'
                              ? 'unknown'
                              : 'error'
                        }
                        size={8}
                      />
                    </td>
                    <td
                      style={{ padding: '8px 16px', color: 'var(--tk-text)' }}
                    >
                      {run.sync_type === 'incremental' ? '增量' : '全量'}
                    </td>
                    <td
                      style={{ padding: '8px 16px', color: 'var(--tk-text)' }}
                    >
                      {run.form_count}
                    </td>
                    <td
                      style={{ padding: '8px 16px', color: 'var(--tk-muted)' }}
                    >
                      {formatNumber(run.total_records)}
                    </td>
                    <td
                      style={{ padding: '8px 16px', color: 'var(--tk-muted)' }}
                    >
                      {formatDuration(run.duration_seconds)}
                    </td>
                    <td style={{ padding: '8px 16px', color: 'var(--tk-dim)' }}>
                      {run.started_at
                        ? new Date(run.started_at).toLocaleTimeString('zh-CN')
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Sub-components ──

const KpiCard: React.FC<{
  title: string;
  value: string;
  subtitle: string;
  color: string;
}> = ({ title, value, subtitle, color }) => (
  <div
    className="glass-card"
    style={{
      padding: '20px 24px',
      background: `linear-gradient(135deg, ${color}08, transparent)`,
      borderLeft: `3px solid ${color}`,
    }}
  >
    <Text style={{ fontSize: 12, color: 'var(--tk-dim)' }}>{title}</Text>
    <div
      style={{ fontSize: 32, fontWeight: 700, color: '#e2e8f0', marginTop: 4 }}
    >
      {value}
      <Text
        style={{
          fontSize: 14,
          fontWeight: 400,
          color: 'var(--tk-muted)',
          marginLeft: 4,
        }}
      >
        {subtitle}
      </Text>
    </div>
  </div>
);

const ServiceStatus: React.FC<{ name: string; status: string }> = ({
  name,
  status,
}) => {
  const isOk = status === 'ok';
  return (
    <div
      className="glass-card"
      style={{
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
      }}
    >
      <DotIndicator type={isOk ? 'ok' : 'error'} size={10} />
      <Text style={{ fontSize: 13, color: 'var(--tk-text)' }}>{name}</Text>
      <Text
        style={{
          marginLeft: 'auto',
          fontSize: 12,
          color: isOk ? 'var(--tk-success)' : 'var(--tk-error)',
        }}
      >
        {isOk ? '正常' : '异常'}
      </Text>
    </div>
  );
};

export default DashboardPage;
