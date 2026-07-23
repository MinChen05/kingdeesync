/* Hallmark · genre: modern-minimal · macrostructure: Stat-Led · design-system: design.md · designed-as-app */
import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import { getTodayStats, getTrend7d, getTopForms7d } from '../../api/dashboard';
import ReactECharts from 'echarts-for-react';

function StatCard({ label, value, sub, accent = false }) {
  return (
    <Card className="relative">
      <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className={`text-2xl font-bold ${accent ? 'text-accent' : 'text-ink'}`}>
        {value ?? '—'}
      </div>
      {sub && (
        <div className="text-xs text-ink-2 mt-1.5">
          {sub}
        </div>
      )}
    </Card>
  );
}

function TrendChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <Card>
        <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-3">
          近 7 天同步趋势
        </div>
        <div className="h-56 flex items-center justify-center text-sm text-ink-2">
          暂无数据
        </div>
      </Card>
    );
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15,23,42,0.95)',
      textStyle: { color: '#f8fafc', fontSize: 12 },
    },
    grid: { top: 16, right: 16, bottom: 28, left: 44 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.day),
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: '次数',
      nameTextStyle: { color: '#64748b', fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#64748b', fontSize: 11 },
    },
    series: [
      {
        data: data.map(d => d.count),
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: 'var(--color-accent)', width: 2 },
        itemStyle: { color: 'var(--color-accent)' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(37,99,235,0.18)' },
              { offset: 1, color: 'rgba(37,99,235,0)' },
            ],
          },
        },
      },
    ],
  };

  return (
    <Card>
      <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-3">
        近 7 天同步趋势
      </div>
      <ReactECharts option={option} style={{ height: 220 }} />
    </Card>
  );
}

function TopErrors({ forms }) {
  if (!forms || forms.length === 0) {
    return (
      <Card>
        <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-3">
          异常表单 Top 5
        </div>
        <div className="h-56 flex items-center justify-center text-sm text-ink-2">
          暂无异常记录
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-3">
        近 7 天异常表单 Top 5
      </div>
      <div className="space-y-2">
        {forms.map((f, i) => (
          <div key={i} className="flex items-center justify-between text-sm py-1.5 border-b border-rule/40 last:border-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-ink-2">{String(i + 1).padStart(2, '0')}</span>
              <span className="font-medium text-ink">{f.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-2">{f.count} 次</span>
              <Badge variant="critical">
                {(100 - (f.rate ?? 0)).toFixed(1)}%
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function SkeletonStat() {
  return (
    <Card>
      <div className="animate-pulse space-y-2">
        <div className="h-2.5 bg-paper-2 rounded w-1/2" />
        <div className="h-6 bg-paper-2 rounded w-1/3" />
        <div className="h-2 bg-paper-2 rounded w-2/3" />
      </div>
    </Card>
  );
}

function SkeletonChart() {
  return (
    <Card>
      <div className="animate-pulse space-y-3">
        <div className="h-3 bg-paper-2 rounded w-1/3" />
        <div className="h-56 bg-paper-2 rounded" />
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  const [stats, setStats] = useState(null);
  const [trend, setTrend] = useState(null);
  const [topForms, setTopForms] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.allSettled([
      getTodayStats(),
      getTrend7d(),
      getTopForms7d(5),
    ]).then(([s, t, f]) => {
      const errors = [];

      if (s.status === 'fulfilled') {
        setStats(s.value.data);
      } else {
        errors.push(`今日统计: ${s.reason.message ?? '请求失败'}`);
      }

      if (t.status === 'fulfilled') {
        setTrend(t.value.data);
      } else {
        errors.push(`趋势数据: ${t.reason.message ?? '请求失败'}`);
      }

      if (f.status === 'fulfilled') {
        setTopForms(f.value.data);
      } else {
        errors.push(`异常表单: ${f.reason.message ?? '请求失败'}`);
      }

      if (errors.length > 0) {
        setError(errors.join('；'));
      }
    }).catch(err => {
      setError(`加载异常: ${err.message ?? '未知错误'}`);
    }).finally(() => {
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <PageShell title="同步概览">
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[0, 1, 2, 3].map(i => <SkeletonStat key={i} />)}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <SkeletonChart />
          <SkeletonChart />
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="同步概览">
      {error && (
        <div className="mb-4 px-3.5 py-2.5 bg-critical/5 border border-critical/15 rounded-md text-sm text-critical">
          部分数据加载失败：{error}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard
          label="今日同步次数"
          value={stats?.sync_count ?? 0}
          sub={`昨日: ${stats?.yday_count ?? 0}`}
          accent
        />
        <StatCard
          label="今日同步记录"
          value={stats?.sync_records ?? 0}
          sub={`昨日: ${stats?.yday_records ?? 0}`}
        />
        <StatCard
          label="今日成功率"
          value={`${stats?.success_rate ?? 0}%`}
          sub={`昨日: ${stats?.yday_rate ?? 0}%`}
        />
        <StatCard
          label="异常任务"
          value={stats?.fail_count ?? 0}
          sub={`昨日: ${stats?.yday_fail_count ?? 0}`}
          accent={stats?.fail_count > 0}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        <TrendChart data={trend} />
        <TopErrors forms={topForms} />
      </div>
    </PageShell>
  );
}
