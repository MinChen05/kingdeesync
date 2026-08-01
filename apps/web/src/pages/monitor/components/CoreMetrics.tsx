import {
  ClockCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Col, Row, Statistic } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import type { StatsSummary } from '../types';

interface CoreMetricsProps {
  stats: StatsSummary;
  loading?: boolean;
}

/**
 * 核心指标：成功率 + 今日同步 + 失败数 + 平均耗时。
 *
 * （原因：运维人员第一眼需要判断系统健康度）
 */
const CoreMetrics: React.FC<CoreMetricsProps> = ({ stats, loading }) => {
  const successRateColor =
    stats.success_rate >= 80
      ? 'var(--tk-success)'
      : stats.success_rate >= 50
        ? 'var(--tk-warning)'
        : 'var(--tk-error)';

  return (
    <Panel title="核心指标" loading={loading}>
      <Row gutter={16}>
        <Col span={6}>
          <Statistic
            title="总运行次数（最近100次）"
            value={stats.total_runs}
            prefix={<ThunderboltOutlined style={{ color: 'var(--tk-primary)' }} />}
            valueStyle={{ color: 'var(--tk-text)' }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="成功率"
            value={stats.success_rate}
            precision={1}
            suffix="%"
            valueStyle={{ color: successRateColor }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="失败次数"
            value={stats.failed_runs}
            prefix={<CloseCircleOutlined style={{ color: 'var(--tk-error)' }} />}
            valueStyle={{
              color: stats.failed_runs > 0 ? 'var(--tk-error)' : 'var(--tk-text)',
            }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="平均耗时"
            value={stats.avg_duration_sec}
            precision={0}
            suffix="秒"
            prefix={<ClockCircleOutlined style={{ color: 'var(--tk-muted)' }} />}
            valueStyle={{ color: 'var(--tk-text)' }}
          />
        </Col>
      </Row>
    </Panel>
  );
};

export default CoreMetrics;
