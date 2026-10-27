import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Empty } from 'antd';
import dayjs from 'dayjs';
import React, { useEffect, useRef, useState } from 'react';
import PageHeader from '@/components/PageHeader';
import Panel from '@/components/Panel';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import type { HealthLevel } from '@/pages/Overview/types';
import type { V1HealthStatus } from '@/services/v1';
import { getOverview } from '@/services/v1';
import { formatDuration, formatNumber } from '@/utils/format';
import './index.less';

const DashboardPage: React.FC = () => {
  const [now, setNow] = useState(new Date());
  const { data: overview, isPending } = useQuery({
    queryKey: ['v1', 'overview'],
    queryFn: () => getOverview(),
    refetchInterval: 30_000,
  });

  const timerRef = useRef<ReturnType<typeof setInterval>>();
  useEffect(() => {
    timerRef.current = setInterval(() => setNow(new Date()), 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const health = overview?.health;
  const today = overview?.today;
  const recentRuns = overview?.recent_runs ?? [];
  const overall = healthOverall(health);

  return (
    <div className="page-stack dashboard-page">
      <PageHeader
        title="金蝶数据同步看板"
        description="实时掌握今日同步表现、服务状态与最近运行情况"
        extra={
          <div className="dashboard-header-meta">
            <span className={`dashboard-overall dashboard-overall--${overall}`}>
              <span className="dashboard-status-dot" aria-hidden="true" />
              {healthLabel(overall)}
            </span>
            <time className="dashboard-clock" dateTime={now.toISOString()}>
              {dayjs(now).format('YYYY-MM-DD HH:mm:ss')}
            </time>
          </div>
        }
      />

      <Panel title="今日概览" loading={isPending}>
        <div className="dashboard-kpis">
          <KpiCard
            title="今日同步"
            value={formatNumber(today?.sync_count ?? 0)}
            unit="次"
            note="今日发起的同步运行"
            icon={<SyncOutlined />}
            tone="primary"
          />
          <KpiCard
            title="成功次数"
            value={formatNumber(
              Math.max((today?.sync_count ?? 0) - (today?.fail_count ?? 0), 0),
            )}
            unit="次"
            note="已完成且无失败"
            icon={<CheckCircleOutlined />}
            tone="success"
          />
          <KpiCard
            title="失败次数"
            value={formatNumber(today?.fail_count ?? 0)}
            unit="次"
            note={
              (today?.fail_count ?? 0) > 0 ? '建议查看异常明细' : '今日暂无失败'
            }
            icon={<CloseCircleOutlined />}
            tone={(today?.fail_count ?? 0) > 0 ? 'error' : 'neutral'}
          />
          <KpiCard
            title="平均耗时"
            value={formatDuration(today?.avg_duration ?? 0)}
            note="单次同步平均用时"
            icon={<ClockCircleOutlined />}
            tone="neutral"
          />
        </div>
      </Panel>

      <Panel title="服务健康" loading={isPending}>
        <div className="dashboard-services">
          <ServiceStatus
            name="金蝶 API"
            status={health?.kingdee_api?.status || 'unknown'}
          />
          <ServiceStatus
            name="数据库"
            status={health?.database?.status || 'unknown'}
          />
          <ServiceStatus
            name="调度器"
            status={health?.scheduler?.status || 'unknown'}
          />
          <ServiceStatus
            name="日志服务"
            status={health?.log_service?.status || 'unknown'}
          />
        </div>
      </Panel>

      <Panel
        title="最近运行"
        loading={isPending}
        extra={<span className="dashboard-refresh-note">每 30 秒自动刷新</span>}
      >
        {recentRuns.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无运行记录"
            className="dashboard-empty"
          />
        ) : (
          <div className="dashboard-table-wrap">
            <table className="dashboard-table" aria-label="最近同步运行记录">
              <thead>
                <tr>
                  {['状态', '类型', '表单', '数据量', '耗时', '开始时间'].map(
                    (heading) => (
                      <th key={heading} scope="col">
                        {heading}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {recentRuns.slice(0, 8).map((run) => (
                  <tr key={run.run_id}>
                    <td>
                      <SyncStatusTag status={run.status} />
                    </td>
                    <td>
                      <SyncTypeTag type={run.sync_type} />
                    </td>
                    <td className="dashboard-table__number">
                      {run.form_count}
                    </td>
                    <td className="dashboard-table__number">
                      {formatNumber(run.total_records)}
                    </td>
                    <td>{formatDuration(run.duration_seconds)}</td>
                    <td>
                      <time dateTime={run.started_at || undefined}>
                        {run.started_at
                          ? new Date(run.started_at).toLocaleTimeString('zh-CN')
                          : '-'}
                      </time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
};

function healthOverall(health: V1HealthStatus | undefined): HealthLevel {
  if (!health) return 'unknown';
  const items = [
    health.kingdee_api,
    health.database,
    health.scheduler,
    health.log_service,
  ];
  if (items.some((item) => !item)) return 'unknown';
  if (items.every((item) => item.status === 'ok')) return 'ok';
  return 'error';
}

function healthLabel(level: HealthLevel): string {
  if (level === 'ok') return '全部服务正常';
  if (level === 'error') return '存在异常服务';
  return '服务状态未知';
}

const KpiCard: React.FC<{
  title: string;
  value: string;
  unit?: string;
  note: string;
  icon: React.ReactNode;
  tone: 'primary' | 'success' | 'error' | 'neutral';
}> = ({ title, value, unit, note, icon, tone }) => (
  <article className={`dashboard-kpi dashboard-kpi--${tone}`}>
    <div className="dashboard-kpi__heading">
      <span>{title}</span>
      <span className="dashboard-kpi__icon" aria-hidden="true">
        {icon}
      </span>
    </div>
    <div className="dashboard-kpi__value">
      {value}
      {unit && <span className="dashboard-kpi__unit">{unit}</span>}
    </div>
    <div className="dashboard-kpi__note">{note}</div>
  </article>
);

const ServiceStatus: React.FC<{ name: string; status: string }> = ({
  name,
  status,
}) => {
  const level: HealthLevel =
    status === 'ok' ? 'ok' : status === 'unknown' ? 'unknown' : 'error';
  return (
    <div className={`dashboard-service dashboard-service--${level}`}>
      <span className="dashboard-service__indicator" aria-hidden="true">
        <span className="dashboard-status-dot" />
      </span>
      <div className="dashboard-service__content">
        <span className="dashboard-service__name">{name}</span>
        <span className="dashboard-service__description">
          {level === 'ok'
            ? '连接与响应正常'
            : level === 'error'
              ? '请检查服务状态'
              : '暂未获取状态'}
        </span>
      </div>
      <span className="dashboard-service__status">
        {level === 'ok' ? '正常' : level === 'error' ? '异常' : '未知'}
      </span>
    </div>
  );
};

export default DashboardPage;
