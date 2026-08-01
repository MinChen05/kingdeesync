import React from 'react';
import type { V1HealthItem } from '@/services/v1';
import type { DataSource, HealthStatus } from '../hooks';
import { DotIndicator } from '@/components/DotIndicator';
import Panel from '@/components/Panel';

interface HealthGridProps {
  health: HealthStatus;
  sources: DataSource[];
  loading?: boolean;
}

interface MetricLine {
  label: string;
  value: string;
}

interface ServiceMeta {
  key: string;
  name: string;
  item?: V1HealthItem;
  metrics: MetricLine[];
}

const isOk = (status?: string) => status === 'ok' || status === 'healthy';

const fmtMs = (ms?: number) => (ms != null ? `${ms}ms` : '-');

/**
 * 系统健康：以发光指示灯 + 关键指标呈现各服务状态。
 * 服务清单用配置数组描述，新增服务只需追加一项。（原因：配置化，便于扩展）
 * 同时融合数据源的连接池/认证等补充信息，让健康状态更有判断价值。
 */
const HealthGrid: React.FC<HealthGridProps> = ({
  health,
  sources,
  loading,
}) => {
  const sourceMap = new Map(sources.map((s) => [String(s.id), s]));

  const services: ServiceMeta[] = [
    {
      key: 'kingdee_api',
      name: '金蝶 API',
      item: health.kingdee_api,
      metrics: [
        { label: '响应', value: fmtMs(health.kingdee_api?.response_ms) },
        {
          label: '今日调用',
          value:
            health.kingdee_api?.today_calls != null
              ? `${health.kingdee_api.today_calls} 次`
              : '-',
        },
        {
          label: '认证',
          value: String(sourceMap.get('kingdee')?.config?.auth_status || '-'),
        },
      ],
    },
    {
      key: 'database',
      name: '数据库',
      item: health.database,
      metrics: [
        { label: '响应', value: fmtMs(health.database?.response_ms) },
        {
          label: '连接',
          value:
            health.database?.conn_count != null
              ? `${health.database.conn_count}`
              : '-',
        },
        {
          label: '连接池',
          value: String(sourceMap.get('database')?.config?.pool_status || '-'),
        },
      ],
    },
    {
      key: 'scheduler',
      name: '调度器',
      item: health.scheduler,
      metrics: [
        { label: '状态', value: health.scheduler?.uptime || '-' },
        { label: '下次执行', value: health.scheduler?.next_exec || '-' },
      ],
    },
    {
      key: 'log_service',
      name: '日志服务',
      item: health.log_service,
      metrics: [
        { label: '写入', value: health.log_service?.write_speed || '-' },
        { label: '日志量', value: health.log_service?.log_size || '-' },
      ],
    },
  ];

  return (
    <Panel title="系统健康" loading={loading}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {services.map((s) => {
          const unknown = !s.item?.status;
          const ok = isOk(s.item?.status);
          return (
            <div
              key={s.key}
              className="list-row"
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <DotIndicator
                  level={unknown ? 'unknown' : ok ? 'ok' : 'error'}
                />
                <span
                  style={{ fontWeight: 600, color: 'var(--tk-text)', fontSize: 13 }}
                >
                  {s.name}
                </span>
                <span
                  style={{
                    marginLeft: 'auto',
                    fontSize: 12,
                    color: unknown ? 'var(--tk-dim)' : ok ? 'var(--tk-success)' : 'var(--tk-error)',
                  }}
                >
                  {unknown ? '未知' : ok ? '正常' : '异常'}
                </span>
              </div>
              <div
                style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}
              >
                {s.metrics.map((m) => (
                  <span
                    key={m.label}
                    style={{ fontSize: 12, color: 'var(--tk-dim)' }}
                  >
                    {m.label}{' '}
                    <span style={{ color: '#cbd5e1' }}>{m.value}</span>
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
};

export default HealthGrid;
