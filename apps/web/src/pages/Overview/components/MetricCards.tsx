import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import React from 'react';
import { formatDuration } from '@/utils/format';
import type { TodayStats } from '../hooks';

interface MetricCardsProps {
  today: TodayStats;
}

interface Metric {
  title: string;
  value: React.ReactNode;
  suffix?: string;
  icon: React.ReactNode;
  iconColor: string;
  change?: number | null;
  upIsGood?: boolean;
  valueColor?: string;
}

function compareRate(current?: number, previous?: number): number | null {
  if (current == null || previous == null || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

const MetricItem: React.FC<Metric> = ({
  title,
  value,
  suffix,
  icon,
  iconColor,
  change,
  upIsGood = true,
  valueColor,
}) => {
  const isUp = (change ?? 0) >= 0;
  const isGood = change == null ? true : upIsGood === isUp;
  const changeColor = isGood ? 'var(--tk-success)' : 'var(--tk-error)';

  return (
    <>
      <div className="overview-metric-top">
        <span>{title}</span>
        <span className="overview-metric-icon" style={{ color: iconColor }}>
          {icon}
        </span>
      </div>
      <div className="overview-metric-value" style={{ color: valueColor }}>
        {value}
        {suffix && <span className="overview-metric-suffix">{suffix}</span>}
      </div>
      <div
        className="overview-metric-change"
        style={{ color: change != null ? changeColor : undefined }}
      >
        {change != null && (
          <>
            {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{' '}
            {Math.abs(change).toFixed(0)}% <span>较昨日</span>
          </>
        )}
      </div>
    </>
  );
};

const MetricCards: React.FC<MetricCardsProps> = ({ today }) => {
  const syncCount = today.sync_count || 0;
  const successRate =
    today.success_rate != null ? Number(today.success_rate.toFixed(1)) : 0;
  const failCount = today.fail_count || 0;
  const avgDuration = formatDuration(today.avg_duration);

  const metrics: Metric[] = [
    {
      title: '今日同步运行',
      value: syncCount,
      suffix: '次',
      icon: <ThunderboltOutlined />,
      iconColor: 'var(--tk-primary)',
      change: compareRate(syncCount, today.yesterday_sync_count),
    },
    {
      title: '同步成功率',
      value: successRate,
      suffix: '%',
      icon: <CheckCircleOutlined />,
      iconColor: 'var(--tk-success)',
      change: compareRate(successRate, today.yesterday_success_rate),
    },
    {
      title: '失败运行',
      value: failCount,
      suffix: '次',
      icon: <ExclamationCircleOutlined />,
      iconColor: failCount > 0 ? 'var(--tk-error)' : 'var(--tk-success)',
      valueColor: failCount > 0 ? 'var(--tk-error)' : undefined,
      change: null,
    },
    {
      title: '平均同步耗时',
      value: avgDuration,
      icon: <ClockCircleOutlined />,
      iconColor: 'var(--tk-warning)',
      change: null,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.title} className="metric-card overview-metric">
          <MetricItem {...metric} />
        </div>
      ))}
    </div>
  );
};

export default MetricCards;
