import React from 'react';
import ErrorForms from './components/ErrorForms';
import HealthGrid from './components/HealthGrid';
import HeroStatus from './components/HeroStatus';
import MetricCards from './components/MetricCards';
import RecentRuns from './components/RecentRuns';
import TrendChart from './components/TrendChart';
import { useOverviewData } from './hooks';

/**
 * 系统概览页（重构版）。
 *
 * 信息架构按运维决策优先级分层：
 *   1. HeroStatus  —— 一眼判断系统好坏 + 主操作
 *   2. MetricCards —— 核心 KPI（含昨日对比）
 *   3. TrendChart + ErrorForms —— 数据洞察（趋势 / 需处理的异常）
 *   4. HealthGrid + RecentRuns —— 系统详情（服务健康 / 最近活动）
 *
 * 本文件只做布局组装，不含业务与展示细节；新增面板 = 写组件 + 在此加一行。
 * （原因：保持页面入口精简、职责清晰，便于后续功能迭代扩展）
 */
const Overview: React.FC = () => {
  const { today, status, sources, trend, topForms, health, recent } =
    useOverviewData();

  const handleSynced = () => {
    today.refresh();
    status.refresh();
  };

  return (
    <div className="space-y-6">
      {/* 1. Hero 状态区 */}
      <HeroStatus
        today={today.data}
        status={status.data}
        onSynced={handleSynced}
      />

      {/* 2. KPI 指标卡 */}
      <MetricCards today={today.data} />

      {/* 3. 数据洞察：趋势(2/3) + 异常(1/3) */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <TrendChart trend={trend.data} loading={trend.loading} />
        </div>
        <ErrorForms topForms={topForms.data} loading={topForms.loading} />
      </div>

      {/* 4. 系统详情：健康(1/2) + 最近同步(1/2) */}
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
