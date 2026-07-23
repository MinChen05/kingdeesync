/* Hallmark · genre: modern-minimal · macrostructure: Workbench · design-system: design.md · designed-as-app */
import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import client from '../../api/client';

function formatDate(d) {
  if (!d) return '-';
  return d.replace('T', ' ').substring(0, 19);
}

function statusVariant(s) {
  if (s === 'success') return 'success';
  if (s === 'partial') return 'warning';
  return 'critical';
}

export default function HistoryPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    start_date: '',
    end_date: '',
    status: '',
    sync_type: '',
    form_name: '',
  });

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await client.get('/history', {
        params: { page, page_size: 20, ...filters },
        meta: { skipToast: true },
      });
      setItems(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (e) {
      setError(e.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page, filters]);

  const maxPage = Math.ceil(total / 20) || 1;
  const hasMore = page * 20 < total || items.length >= 20;

  return (
    <PageShell
      title="同步历史"
      subtitle="查看和管理历史同步记录"
    >
      {error && (
        <div className="mb-4 px-3.5 py-2.5 bg-critical/5 border border-critical/15 rounded-md text-sm text-critical">
          加载同步历史失败：{error}
        </div>
      )}

      {/* Filters */}
      <Card className="mb-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1">开始日期</label>
            <input
              type="date"
              value={filters.start_date}
              onChange={e => setFilters(f => ({ ...f, start_date: e.target.value }))}
              className="block w-40 border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1">结束日期</label>
            <input
              type="date"
              value={filters.end_date}
              onChange={e => setFilters(f => ({ ...f, end_date: e.target.value }))}
              className="block w-40 border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1">状态</label>
            <select
              value={filters.status}
              onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
              className="block w-36 border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:border-accent focus:outline-none"
            >
              <option value="">全部</option>
              <option value="success">成功</option>
              <option value="partial">部分成功</option>
              <option value="failed">失败</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1">同步类型</label>
            <select
              value={filters.sync_type}
              onChange={e => setFilters(f => ({ ...f, sync_type: e.target.value }))}
              className="block w-36 border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:border-accent focus:outline-none"
            >
              <option value="">全部</option>
              <option value="incremental">增量</option>
              <option value="full">全量</option>
            </select>
          </div>
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs font-medium text-ink-2 mb-1">表单搜索</label>
            <input
              type="text"
              value={filters.form_name}
              onChange={e => setFilters(f => ({ ...f, form_name: e.target.value }))}
              placeholder="输入表单名称"
              className="block w-full border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:border-accent focus:outline-none"
            />
          </div>
          <Button variant="primary" onClick={() => setPage(1)} size="sm">
            查询
          </Button>
        </div>
      </Card>

      {/* Table */}
      <Card className="p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-paper-2 border-b border-rule">
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">时间</th>
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">类型</th>
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">状态</th>
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">表单</th>
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">记录数</th>
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">耗时</th>
              <th className="text-left py-2.5 px-4 font-medium text-xs text-ink-2 uppercase tracking-wide">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-sm text-ink-2">
                  加载中...
                </td>
              </tr>
            )}
            {!loading && !error && items.length === 0 && (
              <tr>
                <td colSpan={7} className="py-8 text-center text-sm text-ink-2">
                  暂无符合条件的记录
                </td>
              </tr>
            )}
            {items.map(r => (
              <tr key={r.run_id} className="border-b border-rule/40 last:border-0 hover:bg-paper-2 transition-colors">
                <td className="py-2.5 px-4 text-ink-2">{formatDate(r.start_time)}</td>
                <td className="py-2.5 px-4">
                  <Badge variant="default">{r.sync_type}</Badge>
                </td>
                <td className="py-2.5 px-4">
                  <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                </td>
                <td className="py-2.5 px-4 max-w-xs truncate text-ink-2">{r.forms_synced || '-'}</td>
                <td className="py-2.5 px-4 text-ink-2">{r.total_records ?? '-'}</td>
                <td className="py-2.5 px-4 text-ink-2">
                  {r.duration_seconds ? Number(r.duration_seconds).toFixed(1) + 's' : '-'}
                </td>
                <td className="py-2.5 px-4">
                  <a
                    href={`/history/${r.run_id}`}
                    className="text-accent hover:text-accent-2 text-xs font-medium"
                  >
                    详情 →
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-rule/40 text-xs text-ink-2">
          <span>共 {total} 条，第 {page} / {maxPage} 页</span>
          <div className="flex gap-2">
            <Button variant="ghost" size="xs" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>
              上一页
            </Button>
            <Button variant="ghost" size="xs" onClick={() => setPage(p => p + 1)} disabled={!hasMore}>
              下一页
            </Button>
          </div>
        </div>
      </Card>
    </PageShell>
  );
}
