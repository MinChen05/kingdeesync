/* Hallmark · genre: modern-minimal · macrostructure: Workbench · design-system: design.md · designed-as-app */

import { useState, useEffect } from 'react';
import PageShell from '../../components/common/PageShell';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';
import { useApp } from '../../contexts/AppContext';
import { getForms, updateForm } from '../../api/forms';

export default function FormsPage() {
  const { addToast, refreshForms } = useApp();
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState({});
  const [editingForm, setEditingForm] = useState(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getForms();
      setForms(res.data || []);
    } catch (e) {
      setError(e.message || '加载表单列表失败');
    } finally {
      setLoading(false);
    }
  };

  const toggleEnabled = async (formName) => {
    const form = forms.find(f => f.form_name === formName);
    if (!form) return;
    setSaving(prev => ({ ...prev, [formName]: true }));
    try {
      await updateForm(formName, { enabled: !form.enabled });
      setForms(prev =>
        prev.map(f =>
          f.form_name === formName ? { ...f, enabled: !f.enabled } : f
        )
      );
      await refreshForms();
      addToast(`${formName} 已${!form.enabled ? '启用' : '禁用'}`, 'success');
    } catch (_) {
      addToast('操作失败', 'error');
    } finally {
      setSaving(prev => ({ ...prev, [formName]: false }));
    }
  };

  const startEdit = (formName) => {
    const form = forms.find(f => f.form_name === formName);
    if (!form) return;
    setEditingForm(formName);
    setEditValue(form.incremental_field ?? '');
  };

  const cancelEdit = () => {
    setEditingForm(null);
    setEditValue('');
  };

  const saveIncrementalField = async (formName) => {
    if (!formName) return;
    setSaving(prev => ({ ...prev, [formName]: true }));
    try {
      await updateForm(formName, { incremental_field: editValue });
      setForms(prev =>
        prev.map(f =>
          f.form_name === formName ? { ...f, incremental_field: editValue } : f
        )
      );
      await refreshForms();
      setEditingForm(null);
      setEditValue('');
      addToast('已保存', 'success');
    } catch (_) {
      addToast('保存失败', 'error');
    } finally {
      setSaving(prev => ({ ...prev, [formName]: false }));
    }
  };

  const enabledCount = forms.filter(f => f.enabled).length;

  return (
    <PageShell title="表单管理">
      {/* Stats bar */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">总表单</div>
          <div className="text-xl font-semibold">{forms.length}</div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">已启用</div>
          <div className="text-xl font-semibold text-success">{enabledCount}</div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-steel uppercase tracking-wide mb-1">已禁用</div>
          <div className="text-xl font-semibold">{forms.length - enabledCount}</div>
        </Card>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-critical/5 border border-critical/20 rounded-lg text-sm text-critical">
          {error}
        </div>
      )}

      <Card>
        {loading ? (
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-12 bg-surface-2 rounded-lg" />
            ))}
          </div>
        ) : forms.length === 0 ? (
          <div className="text-sm text-steel py-8 text-center">暂无表单</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-paper-2 text-xs font-semibold text-steel uppercase tracking-wide">
                  <th className="text-left py-2 px-3">表单名</th>
                  <th className="text-left py-2 px-3">目标表</th>
                  <th className="text-left py-2 px-3">增量字段</th>
                  <th className="text-left py-2 px-3">状态</th>
                  <th className="text-left py-2 px-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {forms.map(f => {
                  const isEditing = editingForm === f.form_name;
                  const isSaving = saving[f.form_name];
                  return (
                    <tr
                      key={f.form_name}
                      className="border-t border-rule hover:bg-paper-2 transition-colors"
                    >
                      <td className="py-2.5 px-3 font-mono font-medium">{f.form_name}</td>
                      <td className="py-2.5 px-3 font-mono text-steel">{f.table_name || '-'}</td>
                      <td className="py-2.5 px-3">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editValue}
                              onChange={e => setEditValue(e.target.value)}
                              onBlur={() => saveIncrementalField(f.form_name)}
                              onKeyDown={e => {
                                if (e.key === 'Enter') saveIncrementalField(f.form_name);
                                if (e.key === 'Escape') cancelEdit();
                              }}
                              className="w-48 border border-rule rounded-md px-2 py-1 text-sm font-mono bg-paper focus:outline-none focus:ring-2 focus:ring-accent/50"
                              autoFocus
                            />
                          </div>
                        ) : (
                          <span className="font-mono text-steel">{f.incremental_field || '-'}</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant={f.enabled ? 'success' : 'default'}>
                          {f.enabled ? '启用' : '禁用'}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-2">
                          <Button
                            variant={f.enabled ? 'secondary' : 'primary'}
                            size="xs"
                            onClick={() => toggleEnabled(f.form_name)}
                            loading={isSaving}
                          >
                            {f.enabled ? '禁用' : '启用'}
                          </Button>
                          {!isEditing && !isSaving && (
                            <Button variant="ghost" size="xs" onClick={() => startEdit(f.form_name)}>
                              编辑增量字段
                            </Button>
                          )}
                          {isEditing && (
                            <Button variant="ghost" size="xs" onClick={cancelEdit}>
                              取消
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </PageShell>
  );
}
