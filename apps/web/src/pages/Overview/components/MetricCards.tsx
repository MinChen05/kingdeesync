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
  /** 较昨日变化百分比；null/undefined 表示无对比数据 */
  change?: number | null;
  /** 上升是否为好事（失败次数等逆向指标为 false） */
  upIsGood?: boolean;
  valueColor?: string;
}

/** 计算较昨日变化百分比；无昨日数据时返回 null */
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
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 22,
          color: iconColor,
          background: `${iconColor}1a`,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: 'var(--tk-muted)' }}>{title}</div>
        <div
          style={{
            fontSize: 26,
            fontWeight: 700,
            color: valueColor || '#f8fafc',
            fontVariantNumeric: 'tabular-nums',
            lineHeight: 1.25,
          }}
        >
          {value}
          {suffix ? (
            <span
              style={{
                fontSize: 13,
                fontWeight: 400,
                color: 'var(--tk-dim)',
                marginLeft: 4,
              }}
            >
              {suffix}
            </span>
          ) : null}
        </div>
        {change != null && (
          <div style={{ fontSize: 12, color: changeColor, marginTop: 2 }}>
            {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{' '}
            {Math.abs(change).toFixed(0)}%
            <span style={{ color: 'var(--tk-dim)', marginLeft: 4 }}>较昨日</span>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * KPI 指标卡：4 项核心指标，含昨日对比。
 * 每卡一张玻璃拟态小卡片，可独立增减指标。（原因：指标卡独立成卡，便于后续扩展新指标）
 */
const MetricCards: React.FC<MetricCardsProps> = ({ today }) => {
  const syncCount = today.sync_count || 0;
  const successRate =
    today.success_rate != null ? Number(today.success_rate.toFixed(1)) : 0;
  const failCount = today.fail_count || 0;
  const avgDuration = formatDuration(today.avg_duration);

  const metrics: Metric[] = [
    {
      title: '今日同步',
      value: syncCount,
      suffix: '次',
      icon: <ThunderboltOutlined />,
      iconColor: 'var(--tk-primary)',
      change: compareRate(syncCount, today.yesterday_sync_count),
      upIsGood: true,
    },
    {
      title: '成功率',
      value: successRate,
      suffix: '%',
      icon: <CheckCircleOutlined />,
      iconColor: 'var(--tk-success)',
      change: compareRate(successRate, today.yesterday_success_rate),
      upIsGood: true,
    },
    {
      title: '失败次数',
      value: failCount,
      suffix: '次',
      icon: <ExclamationCircleOutlined />,
      iconColor: failCount > 0 ? 'var(--tk-error)' : 'var(--tk-success)',
      valueColor: failCount > 0 ? 'var(--tk-error)' : '#f8fafc',
      change: null,
    },
    {
      title: '平均耗时',
      value: avgDuration,
      icon: <ClockCircleOutlined />,
      iconColor: 'var(--tk-warning)',
      change: null,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((m) => (
        <div
          key={m.title}
          className="glass-card"
          style={{ padding: '18px 20px' }}
        >
          <MetricItem {...m} />
        </div>
      ))}
    </div>
  );
};

export default MetricCards;
