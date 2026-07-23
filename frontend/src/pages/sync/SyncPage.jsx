/* Hallmark · genre: modern-minimal · macrostructure: Workbench · design-system: design.md · designed-as-app */
import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import Badge from '../../components/common/Badge';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../../contexts/ToastContext';
import { startSync, getSyncStatus, stopSync } from '../../api/sync';

const MODES = [
  { key: 'incremental', label: '增量', desc: '仅同步变更数据' },
  { key: 'full', label: '全量', desc: '完整拉取所有数据' },
  { key: 'reset', label: '重置', desc: '清空后重新全量' },
];

export default function SyncPage() {
  const { forms, config, loading: appLoading } = useApp();
  const { addToast } = useToast();
  const [selectedForms, setSelectedForms] = useState([]);
  const [syncType, setSyncType] = useState('incremental');
  const [syncing, setSyncing] = useState(false);
  const [currentRun, setCurrentRun] = useState(null);
  const [statusInfo, setStatusInfo] = useState(null);

  useEffect(() => {
    if (config?.sync?.default_forms) {
      setSelectedForms(config.sync.default_forms);
    }
  }, [config]);

  useEffect(() => {
    if (!syncing) return;
    const interval = setInterval(async () => {
      try {
        const res = await getSyncStatus(currentRun);
        setStatusInfo(res.data);
        if (['success', 'failed', 'partial'].includes(res.data.status)) {
          setSyncing(false);
          addToast(`同步完成: ${res.data.status}`, res.data.status === 'success' ? 'success' : 'error');
        }
      } catch (_) {
        // polling error — let centralized handler deal with it
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [syncing, currentRun, addToast]);

  const handleStart = async () => {
    if (selectedForms.length === 0) {
      addToast('请至少选择一个表单', 'error');
      return;
    }
    try {
      setSyncing(true);
      setStatusInfo(null);
      const res = await startSync(selectedForms, syncType);
      setCurrentRun(res.data.run_id);
      addToast('同步任务已启动', 'success');
    } catch (_) {
      setSyncing(false);
      addToast('启动同步失败', 'error');
    }
  };

  const handleStop = async () => {
    try {
      await stopSync(currentRun);
      addToast('已请求停止同步', 'success');
      setSyncing(false);
    } catch (_) {
      addToast('停止同步失败', 'error');
    }
  };

  const toggleForm = (name) => {
    setSelectedForms(prev =>
      prev.includes(name) ? prev.filter(f => f !== name) : [...prev, name]
    );
  };

  const activeMode = MODES.find(m => m.key === syncType);
  const enabledForms = forms.filter(f => f.enabled !== false);

  return (
    <PageShell title="数据同步">
      <div className="grid grid-cols-5 gap-5">

        {/* Left: mode + forms */}
        <div className="col-span-3 space-y-4">
          {/* Mode selector */}
          <Card>
            <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-3">
              同步模式
            </div>
            <div className="grid grid-cols-3 gap-3">
              {MODES.map(m => (
                <button
                  key={m.key}
                  disabled={syncing}
                  onClick={() => setSyncType(m.key)}
                  className={`text-left px-3.5 py-3 rounded-md border transition-all duration-120 ${
                    syncType === m.key
                      ? 'border-accent bg-accent/5 text-ink'
                      : 'border-rule/60 hover:border-rule hover:bg-paper-2 text-ink-2'
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <div className="text-sm font-semibold">{m.label}</div>
                  <div className="text-xs text-ink-2 mt-0.5">{m.desc}</div>
                </button>
              ))}
            </div>
          </Card>

          {/* Forms list */}
          <Card>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-medium text-ink-2 uppercase tracking-wide">
                选择表单
              </div>
              <div className="text-xs text-ink-2">
                已选 {selectedForms.length} / {enabledForms.length}
              </div>
            </div>
            <div className="max-h-72 overflow-y-auto space-y-1">
              {appLoading ? (
                <div className="text-sm text-ink-2">加载中...</div>
              ) : enabledForms.length === 0 ? (
                <div className="text-sm text-ink-2">暂无可用表单</div>
              ) : (
                enabledForms.map(f => (
                  <label
                    key={f.form_name}
                    className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm cursor-pointer transition-colors ${
                      selectedForms.includes(f.form_name)
                        ? 'bg-accent/5 text-ink'
                        : 'text-ink-2 hover:bg-paper-2'
                    }`}
                  >
                    <input
                      type="checkbox"
                      disabled={syncing}
                      checked={selectedForms.includes(f.form_name)}
                      onChange={() => toggleForm(f.form_name)}
                      className="accent-accent"
                    />
                    <span className="font-mono text-xs">{f.form_name}</span>
                  </label>
                ))
              )}
            </div>
          </Card>
        </div>

        {/* Right: control panel */}
        <div className="col-span-2">
          <Card className="sticky top-6">
            <div className="text-xs font-medium text-ink-2 uppercase tracking-wide mb-4">
              执行控制
            </div>

            <div className="mb-4">
              <div className="text-2xl font-bold text-ink">
                {selectedForms.length}
              </div>
              <div className="text-xs text-ink-2 mt-0.5">
                已选择表单
              </div>
            </div>

            {statusInfo && (
              <div className="mb-4 px-3 py-2.5 bg-paper-2 rounded-md space-y-1.5">
                <div className="flex items-center gap-2">
                  <Badge variant={
                    statusInfo.status === 'running' ? 'warning' :
                    statusInfo.status === 'success' ? 'success' :
                    statusInfo.status === 'failed' ? 'critical' : 'default'
                  }>
                    {statusInfo.status}
                  </Badge>
                  <span className="text-sm text-ink">{statusInfo.message || ''}</span>
                </div>
                <div className="text-xs text-ink-2">
                  已用 {Math.floor(statusInfo.elapsed_seconds || 0)}s
                </div>
              </div>
            )}

            <div className="space-y-2">
              {syncing ? (
                <Button variant="danger" onClick={handleStop} className="w-full">
                  停止同步
                </Button>
              ) : (
                <Button variant="primary" onClick={handleStart} className="w-full">
                  开始同步
                </Button>
              )}
              <div className="text-[10px] text-ink-2 text-center">
                当前模式：{activeMode?.label}
              </div>
            </div>
          </Card>
        </div>

      </div>
    </PageShell>
  );
}
