/* Hallmark · genre: modern-minimal · macrostructure: Document · design-system: design.md · designed-as-app */

import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import Badge from '../../components/common/Badge';
import { useApp } from '../../contexts/AppContext';
import { getConfig, updateConfig } from '../../api/config';
import { testConnections } from '../../api/diagnostics';

export default function SettingsPage() {
  const { addToast, refreshConfig } = useApp();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState({});

  useEffect(() => {
    getConfig()
      .then(r => {
        setConfig(r.data);
      })
      .catch(err => {
        addToast(`加载配置失败: ${err.message ?? '未知错误'}`, 'error');
      })
      .finally(() => setLoading(false));
  }, [addToast]);

  if (loading) {
    return (
      <PageShell title="设置">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-32 bg-surface-2 rounded-md" />
          <div className="h-40 bg-surface-2 rounded-lg" />
          <div className="h-40 bg-surface-2 rounded-lg" />
        </div>
      </PageShell>
    );
  }

  const saveSection = async (section, payload) => {
    setSaving(prev => ({ ...prev, [section]: true }));
    try {
      await updateConfig({ [section]: payload });
      setConfig(prev => ({
        ...prev,
        [section]: { ...prev[section], ...payload },
      }));
      await refreshConfig();
      addToast('设置已保存', 'success');
    } catch (_) {
      addToast('保存失败', 'error');
    } finally {
      setSaving(prev => ({ ...prev, [section]: false }));
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await testConnections();
      addToast(
        `测试完成: API=${res.data.kingdee_api ? 'OK' : 'FAIL'}, DB=${res.data.database ? 'OK' : 'FAIL'}`,
        res.data.kingdee_api && res.data.database ? 'success' : 'error'
      );
    } catch (_) {
      addToast('连接测试失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  const sync = config?.sync || {};
  const db = config?.database || {};

  const InputField = ({ label, value, type = 'text', onChange, suffix }) => (
    <div>
      <label className="text-xs font-semibold text-steel uppercase tracking-wide">{label}</label>
      <div className="mt-1 flex items-center gap-2">
        <input
          type={type}
          value={value}
          onChange={onChange}
          className="block w-full border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:outline-none focus:ring-2 focus:ring-accent/50 transition-shadow"
        />
        {suffix && <span className="text-xs text-steel whitespace-nowrap">{suffix}</span>}
      </div>
    </div>
  );

  const SelectField = ({ label, value, onChange, options }) => (
    <div>
      <label className="text-xs font-semibold text-steel uppercase tracking-wide">{label}</label>
      <select
        value={value}
        onChange={onChange}
        className="mt-1 block w-full border border-rule rounded-md px-2.5 py-1.5 text-sm bg-paper focus:outline-none focus:ring-2 focus:ring-accent/50 transition-shadow"
      >
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );

  return (
    <PageShell
      title="设置"
      right={
        <Button variant="secondary" onClick={handleTest} loading={testing}>
          测试连接
        </Button>
      }
    >
      <div className="space-y-6">

        {/* Sync strategy */}
        <Card>
          <div className="flex items-center justify-between mb-5">
            <div className="text-sm font-semibold">同步策略</div>
            {saving.sync && <span className="text-xs text-steel animate-pulse">保存中...</span>}
          </div>

          <div className="space-y-4">
            {/* Auto-sync toggle */}
            <div className="flex items-center justify-between p-3 bg-surface-2 rounded-lg">
              <div>
                <div className="text-sm font-medium">自动同步</div>
                <div className="text-xs text-steel">启用后按间隔自动执行同步任务</div>
              </div>
              <button
                onClick={() => saveSection('sync', { auto_sync: !sync.auto_sync })}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  sync.auto_sync ? 'bg-accent' : 'bg-rule'
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-paper rounded-full shadow-sm transition-transform ${
                    sync.auto_sync ? 'translate-x-5' : ''
                  }`}
                />
              </button>
            </div>

            {/* Grid fields */}
            <div className="grid grid-cols-2 gap-4">
              <InputField
                label="同步间隔"
                type="number"
                value={sync.sync_interval || 120}
                onChange={e => saveSection('sync', { sync_interval: Number(e.target.value) })}
                suffix="分钟"
              />
              <SelectField
                label="默认同步类型"
                value={sync.sync_type || 'incremental'}
                onChange={e => saveSection('sync', { sync_type: e.target.value })}
                options={[
                  { value: 'incremental', label: '增量' },
                  { value: 'full', label: '全量' },
                ]}
              />
              <InputField
                label="增量时间窗口"
                type="number"
                value={sync.time_window_days || 30}
                onChange={e => saveSection('sync', { time_window_days: Number(e.target.value) })}
                suffix="天"
              />
              <InputField
                label="表并发数"
                type="number"
                value={sync.table_concurrency || 8}
                onChange={e => saveSection('sync', { table_concurrency: Number(e.target.value) })}
              />
            </div>
          </div>
        </Card>

        {/* Database */}
        <Card>
          <div className="text-sm font-semibold mb-3">数据库</div>
          <div className="flex items-center gap-3 text-sm">
            <Badge variant="default">{db.type || 'sqlserver'}</Badge>
            <span className="text-steel">连接信息已在服务器端配置</span>
          </div>
        </Card>

        {/* Kingdee */}
        <Card>
          <div className="text-sm font-semibold mb-3">金蝶连接</div>
          <div className="text-sm text-steel">
            金蝶 API 连接信息已在服务器端配置，如需修改请联系管理员。
          </div>
        </Card>

      </div>
    </PageShell>
  );
}
