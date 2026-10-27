import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import React from 'react';
import Panel from '@/components/Panel';
import { formatDuration } from '@/utils/format';
import type { StatsSummary } from '../types';

interface CoreMetricsProps {
  stats: StatsSummary;
  loading?: boolean;
}

const CoreMetrics: React.FC<CoreMetricsProps> = ({ stats, loading }) => {
  const successRateTone =
    stats.success_rate >= 80
      ? 'success'
      : stats.success_rate >= 50
        ? 'warning'
        : 'error';

  const metrics = [
    {
      key: 'runs',
      label: '运行次数',
      value: stats.total_runs.toLocaleString(),
      note: '最近 100 次',
      icon: <ThunderboltOutlined />,
      tone: 'primary',
    },
    {
      key: 'rate',
      label: '运行成功率',
      value: `${stats.success_rate.toFixed(1)}%`,
      note: `${stats.success_runs} 次成功`,
      icon: <CheckCircleOutlined />,
      tone: successRateTone,
    },
    {
      key: 'failed',
      label: '失败次数',
      value: stats.failed_runs.toLocaleString(),
      note: stats.failed_runs > 0 ? '需要关注' : '当前无失败',
      icon: <CloseCircleOutlined />,
      tone: stats.failed_runs > 0 ? 'error' : 'neutral',
    },
    {
      key: 'duration',
      label: '平均耗时',
      value: formatDuration(stats.avg_duration_sec),
      note: '单次运行',
      icon: <ClockCircleOutlined />,
      tone: 'neutral',
    },
  ];

  return (
    <Panel title="核心指标" loading={loading}>
      <div className="monitor-metrics">
        {metrics.map((metric) => (
          <div
            className={`monitor-metric monitor-metric--${metric.tone}`}
            key={metric.key}
          >
            <div className="monitor-metric__heading">
              <span>{metric.label}</span>
              <span className="monitor-metric__icon" aria-hidden="true">
                {metric.icon}
              </span>
            </div>
            <div className="monitor-metric__value">{metric.value}</div>
            <div className="monitor-metric__note">{metric.note}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
};

export default CoreMetrics;
