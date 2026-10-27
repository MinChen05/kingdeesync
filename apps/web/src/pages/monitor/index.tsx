import React from 'react';
import PageHeader from '@/components/PageHeader';
import CoreMetrics from './components/CoreMetrics';
import ErrorForms from './components/ErrorForms';
import ErrorLogPanel from './components/ErrorLogPanel';
import HistoryTable from './components/HistoryTable';
import RecentErrors from './components/RecentErrors';
import SystemDiagnostics from './components/SystemDiagnostics';
import { useMonitorPage } from './hooks';
import './index.less';

/**
 * 监控分析聚合页（排障决策中心）。
 *
 * 信息架构（按真实排障动线分层）：
 * - 核心指标：先判断"有没有问题"
 * - 最近异常：定位"哪些运行失败了"
 * - 错误日志：钻取"具体什么原因"（支持 ?form= 联动与重跑入口）
 * - 同步历史：追溯任意运行，行点击查看完整详情
 * - 异常表单 Top3 + 系统诊断：聚合分析与环境状态
 */
const MonitorPage: React.FC = () => {
  const {
    stats,
    statsLoading,
    recentErrors,
    recentErrorsLoading,
    topErrors,
    topErrorsLoading,
    diagInfo,
    diagLoading,
    refreshDiag,
  } = useMonitorPage();

  return (
    <div className="page-stack monitor-page">
      <PageHeader
        title="监控分析"
        description="从运行趋势到异常明细，快速定位并处理同步问题"
      />

      <CoreMetrics stats={stats} loading={statsLoading} />
      <HistoryTable />
      <div className="monitor-analysis-grid">
        <RecentErrors runs={recentErrors} loading={recentErrorsLoading} />
        <ErrorLogPanel />
      </div>

      <div className="monitor-secondary-grid">
        <ErrorForms forms={topErrors} loading={topErrorsLoading} />
        <SystemDiagnostics
          info={diagInfo}
          loading={diagLoading}
          onRefresh={refreshDiag}
        />
      </div>
    </div>
  );
};

export default MonitorPage;
