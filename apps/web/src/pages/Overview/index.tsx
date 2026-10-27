import React from 'react';
import PageHeader from '@/components/PageHeader';
import ErrorForms from './components/ErrorForms';
import HealthGrid from './components/HealthGrid';
import HeroStatus from './components/HeroStatus';
import MetricCards from './components/MetricCards';
import RecentRuns from './components/RecentRuns';
import TrendChart from './components/TrendChart';
import { useOverviewData } from './hooks';

const Overview: React.FC = () => {
  const { today, status, sources, trend, topForms, health, recent } =
    useOverviewData();

  const handleSynced = () => {
    today.refresh();
    status.refresh();
  };

  return (
    <div className="page-stack">
      <PageHeader
        title="系统概览"
        description="掌握同步链路状态、数据趋势与需要关注的异常。"
        extra={<span className="page-header-badge">实时监测</span>}
      />
      <HeroStatus
        today={today.data}
        status={status.data}
        onSynced={handleSynced}
      />
      <MetricCards today={today.data} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <TrendChart trend={trend.data} loading={trend.loading} />
        </div>
        <ErrorForms topForms={topForms.data} loading={topForms.loading} />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <HealthGrid
          health={health.data}
          sources={sources.data}
          loading={health.loading}
        />
        <RecentRuns recent={recent.data} loading={recent.loading} />
      </div>
    </div>
  );
};

export default Overview;
