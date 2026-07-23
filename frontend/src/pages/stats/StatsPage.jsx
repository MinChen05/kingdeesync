import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import client from '../../api/client';

function todayStr() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function StatsPage() {
  const [fromDate, setFromDate] = useState(daysAgo(30));
  const [toDate, setToDate] = useState(todayStr());
  const [summary, setSummary] = useState(null);
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled([
        client.get('/stats/summary', { params: { from_date: fromDate, to_date: toDate }, meta: { skipToast: true } }),
        client.get('/stats/forms', { params: { from_date: fromDate, to_date: toDate, limit: 50 }, meta: { skipToast: true } }),
      ]);

      const errors = [];

      if (results[0].status === 'fulfilled') {
        setSummary(results[0].value.data);
      } else {
        errors.push(`总览统计: ${results[0].reason.message ?? '请求失败'}`);
      }

      if (results[1].status === 'fulfilled') {
        setForms(results[1].value.data || []);
      } else {
        errors.push(`表单统计: ${results[1].reason.message ?? '请求失败'}`);
      }

      if (errors.length > 0) {
        setError(errors.join('；'));
      }
    } catch (e) {
      setError(e.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [fromDate, toDate]);

  const topFailures = [...forms]
    .filter(f => f.total_errors > 0)
    .sort((a, b) => b.total_errors - a.total_errors)
    .slice(0, 5);

  return (
    <PageShell title="同步统计">
      {error && (
        <div className="mb-4 p-3 bg-critical/5 border border-critical/20 rounded-lg text-sm text-critical">
          部分数据加载失败：{error}
        </div>
      )}
      <Card className="mb-4">
        <div className="flex gap-4 items-end">
          <div>
            <label className="text-xs font-bold text-steel">起始日期</label>
            <input
              type="date"
              value={fromDate}
              onChange={e => setFromDate(e.target.value)}
              className="mt-1 block w-40 border border-hairline rounded-lg px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="text-xs font-bold text-steel">结束日期</label>
            <input
              type="date"
              value={toDate}
              onChange={e => setToDate(e.target.value)}
              className="mt-1 block w-40 border border-hairline rounded-lg px-2 py-1 text-sm"
            />
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="mt-1 px-4 py-1.5 rounded-full text-sm font-bold bg-ink-deep text-white hover:bg-charcoal disabled:opacity-50"
          >
            {loading ? '加载中...' : '查询'}
          </button>
        </div>
      </Card>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <Card>
          <div className="text-sm font-bold text-steel mb-1">总任务数</div>
          <div className="text-2xl font-bold text-ink-deep">{summary?.total_runs ?? '-'}</div>
        </Card>
        <Card>
          <div className="text-sm font-bold text-steel mb-1">成功任务</div>
          <div className="text-2xl font-bold text-ink-deep">{summary?.success_runs ?? '-'}</div>
        </Card>
        <Card>
          <div className="text-sm font-bold text-steel mb-1">失败任务</div>
          <div className="text-2xl font-bold text-ink-deep">{summary?.failed_runs ?? '-'}</div>
        </Card>
        <Card>
          <div className="text-sm font-bold text-steel mb-1">平均成功率</div>
          <div className="text-2xl font-bold text-ink-deep">
            {summary?.avg_success_rate != null ? `${summary.avg_success_rate}%` : '-'}
          </div>
        </Card>
      </div>

      <Card className="mb-6">
        <div className="text-lg font-bold mb-4">表级统计</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline-soft">
              <th className="text-left py-2 font-bold">表单</th>
              <th className="text-left py-2 font-bold">同步次数</th>
              <th className="text-left py-2 font-bold">拉取数</th>
              <th className="text-left py-2 font-bold">写入数</th>
              <th className="text-left py-2 font-bold">错误数</th>
              <th className="text-left py-2 font-bold">成功率</th>
            </tr>
          </thead>
          <tbody>
            {forms.length === 0 && !loading && !error && (
              <tr><td colSpan={6} className="py-4 text-center text-steel">暂无统计数据</td></tr>
            )}
            {forms.map(f => (
              <tr key={f.form_name} className="border-b border-hairline-soft">
                <td className="py-2">{f.form_name}</td>
                <td className="py-2">{f.sync_count}</td>
                <td className="py-2">{f.total_fetched}</td>
                <td className="py-2">{f.total_inserted}</td>
                <td className="py-2">{f.total_errors}</td>
                <td className="py-2">
                  {f.success_rate != null ? `${f.success_rate}%` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {topFailures.length > 0 && (
        <Card>
          <div className="text-lg font-bold mb-4">失败分布 Top 5</div>
          <div className="space-y-2">
            {topFailures.map(f => (
              <div key={f.form_name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-ink-deep">{f.form_name}</span>
                  <Badge variant="critical">错误 {f.total_errors}</Badge>
                </div>
                <span className="text-steel">成功率 {f.success_rate ?? '-'}%</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </PageShell>
  );
}
