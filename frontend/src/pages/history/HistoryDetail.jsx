/* Hallmark · genre: modern-minimal · macrostructure: Document · design-system: design.md · designed-as-app */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import { getRunDetails } from '../../api/history';

function formatDate(d) {
  if (!d) return '-';
  return d.replace('T', ' ').substring(0, 19);
}

function statusVariant(status) {
  if (status === 'success') return 'success';
  if (status === 'partial') return 'attention';
  return 'critical';
}

export default function HistoryDetail() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getRunDetails(runId)
      .then(r => {
        setData(r.data);
      })
      .catch(_ => {
        setError('获取任务详情失败');
      })
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <PageShell title="任务详情">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-surface-2 rounded-md" />
          <div className="grid grid-cols-3 gap-4">
            <div className="h-20 bg-surface-2 rounded-lg" />
            <div className="h-20 bg-surface-2 rounded-lg" />
            <div className="h-20 bg-surface-2 rounded-lg" />
          </div>
        </div>
      </PageShell>
    );
  }

  if (error || !data) {
    return (
      <PageShell
        title="任务详情"
        right={
          <Button variant="ghost" onClick={() => navigate('/history')}>
            返回列表
          </Button>
        }
      >
        <Card>
          <div className="text-sm text-steel mb-2">{error || '任务不存在'}</div>
          <Button onClick={() => navigate('/history')}>返回列表</Button>
        </Card>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="任务详情"
      right={
        <Button variant="ghost" onClick={() => navigate('/history')}>
          返回列表
        </Button>
      }
    >
      {/* Header summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">运行 ID</div>
          <div className="text-sm font-mono">{data.run_id}</div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">状态</div>
          <Badge variant={statusVariant(data.status)}>{data.status}</Badge>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">耗时</div>
          <div className="text-sm">
            {data.duration_seconds ? Number(data.duration_seconds).toFixed(2) + 's' : '-'}
          </div>
        </Card>
      </div>

      {/* Meta block */}
      <Card className="mb-6">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">开始时间</div>
            <div>{formatDate(data.start_time)}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">结束时间</div>
            <div>{formatDate(data.end_time)}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">说明</div>
            <div>{data.message || '-'}</div>
          </div>
        </div>
      </Card>

      {/* Form-level stats */}
      <Card className="mb-6">
        <div className="text-sm font-semibold mb-4">表单级统计</div>
        {(!data.form_stats || data.form_stats.length === 0) ? (
          <div className="text-sm text-steel">暂无数据</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-paper-2 text-xs font-semibold text-steel uppercase tracking-wide">
                  <th className="text-left py-2 px-3">表单</th>
                  <th className="text-left py-2 px-3">目标表</th>
                  <th className="text-left py-2 px-3">拉取</th>
                  <th className="text-left py-2 px-3">写入</th>
                  <th className="text-left py-2 px-3">错误</th>
                  <th className="text-left py-2 px-3">状态</th>
                  <th className="text-left py-2 px-3">耗时(s)</th>
                </tr>
              </thead>
              <tbody>
                {data.form_stats.map((s, i) => (
                  <tr key={i} className="border-t border-rule hover:bg-paper-2 transition-colors">
                    <td className="py-2 px-3 font-mono">{s.form_name}</td>
                    <td className="py-2 px-3 font-mono text-steel">{s.table_name || '-'}</td>
                    <td className="py-2 px-3">{s.fetched_count}</td>
                    <td className="py-2 px-3">{s.inserted_count}</td>
                    <td className="py-2 px-3">{s.error_count}</td>
                    <td className="py-2 px-3">
                      <Badge variant={statusVariant(s.status)}>{s.status}</Badge>
                    </td>
                    <td className="py-2 px-3 font-mono">
                      {s.duration_seconds ? Number(s.duration_seconds).toFixed(2) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Errors */}
      {data.errors && data.errors.length > 0 && (
        <Card>
          <div className="text-sm font-semibold mb-4">错误摘要 ({data.errors.length})</div>
          <div className="space-y-3">
            {data.errors.map((e, i) => (
              <div key={i} className="text-sm border border-rule rounded-lg p-3 bg-surface-2">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="critical">{e.error_type || 'error'}</Badge>
                  <span className="font-mono font-semibold">{e.form_name}</span>
                </div>
                <div className="text-steel">{e.error_message}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </PageShell>
  );
}
