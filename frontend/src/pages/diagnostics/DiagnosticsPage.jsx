/* Hallmark · genre: modern-minimal · macrostructure: Document · design-system: design.md · designed-as-app */

import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import { getDiagnostics, testConnections } from '../../api/diagnostics';
import { useToast } from '../../contexts/ToastContext';

export default function DiagnosticsPage() {
  const { addToast } = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getDiagnostics();
      setData(res.data);
    } catch (_) {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleTest = async () => {
    setTesting(true);
    try {
      await testConnections();
      await load();
      addToast('连接测试完成', 'success');
    } catch (_) {
      addToast('连接测试失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  const handleExport = () => {
    if (!data) return;
    const content = JSON.stringify(data, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `diagnostics-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    addToast('诊断信息已导出', 'success');
  };

  if (loading) {
    return (
      <PageShell title="系统诊断">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-40 bg-surface-2 rounded-md" />
          <div className="grid grid-cols-2 gap-4">
            <div className="h-24 bg-surface-2 rounded-lg" />
            <div className="h-24 bg-surface-2 rounded-lg" />
          </div>
        </div>
      </PageShell>
    );
  }

  if (!data) {
    return (
      <PageShell title="系统诊断">
        <Card>
          <div className="text-sm text-steel mb-2">无法获取诊断信息</div>
          <Button onClick={handleTest}>重新测试连接</Button>
        </Card>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="系统诊断"
      right={
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleTest} loading={testing}>
            重新测试
          </Button>
          <Button variant="ghost" onClick={handleExport}>
            导出
          </Button>
        </div>
      }
    >
      {/* Connection status */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-2">金蝶 API</div>
          <div className="flex items-center gap-2">
            <Badge variant={data.kingdee_api?.status === 'ok' ? 'success' : 'critical'}>
              {data.kingdee_api?.status || 'unknown'}
            </Badge>
          </div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-2">数据库</div>
          <div className="flex flex-col gap-1">
            <Badge variant={data.database?.status === 'ok' ? 'success' : 'critical'}>
              {data.database?.status || 'unknown'}
            </Badge>
            <span className="text-xs text-steel font-mono">
              {data.database?.type || ''}
              {data.database?.type && data.database?.version ? ' · ' : ''}
              {data.database?.version ? data.database.version.slice(0, 40) : ''}
            </span>
          </div>
        </Card>
      </div>

      {/* Environment */}
      <Card className="mb-6">
        <div className="text-sm font-semibold mb-3">环境信息</div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">Python</div>
            <div className="font-mono">{data.environment?.python_version || '-'}</div>
          </div>
          <div>
            <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">运行模式</div>
            <div>{data.environment?.mode || '-'}</div>
          </div>
        </div>
      </Card>

      {/* Messages */}
      {data.messages && data.messages.length > 0 && (
        <Card className="mb-6">
          <div className="text-sm font-semibold mb-3">测试消息</div>
          <ul className="list-disc pl-5 text-sm text-steel space-y-1">
            {data.messages.map((m, i) => (
              <li key={i}>{typeof m === 'string' ? m : JSON.stringify(m)}</li>
            ))}
          </ul>
        </Card>
      )}

      {/* Recent errors */}
      {data.recent_errors && data.recent_errors.length > 0 && (
        <Card>
          <div className="text-sm font-semibold mb-3">最近错误 ({data.recent_errors.length})</div>
          <div className="space-y-3">
            {data.recent_errors.map((e, i) => (
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
