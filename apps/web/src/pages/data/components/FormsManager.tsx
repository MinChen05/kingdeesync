import { App, Collapse, Table, Tag } from 'antd';
import React, { useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import type { FormItem, FormStat } from '../types';
import { useFormColumns } from './FormColumns';
import { FormToolbar } from './FormToolbar';
import FormConfigDrawer from './FormConfigDrawer';

const { Panel: CollapsePanel } = Collapse;

interface FormsManagerProps {
  forms: FormItem[];
  statsMap: Map<string, FormStat>;
  loading?: boolean;
  onUpdateForm: (formName: string, enabled: boolean) => void;
  onUpdateFormConfig: (formName: string, data: Partial<FormItem>) => void;
  updating?: boolean;
  updatingConfig?: boolean;
}

type SortField = 'errors' | 'last_sync' | 'none';

/**
 * 表单管理：按启用状态分组、批量操作、排序、搜索。
 */
const FormsManager: React.FC<FormsManagerProps> = ({
  forms,
  statsMap,
  loading,
  onUpdateForm,
  onUpdateFormConfig,
  updating,
  updatingConfig,
}) => {
  const { message } = App.useApp();
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('last_sync');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [configDrawerVisible, setConfigDrawerVisible] = useState(false);
  const [editingForm, setEditingForm] = useState<FormItem | null>(null);

  // 分组：已启用 / 已禁用
  const { enabledForms, disabledForms } = useMemo(() => {
    let filtered = forms;

    if (search) {
      const s = search.toLowerCase();
      filtered = filtered.filter((f) => f.form_name.toLowerCase().includes(s));
    }

    if (sortField === 'errors') {
      filtered = [...filtered].sort((a, b) => {
        const aErr = statsMap.get(a.form_name)?.failed_records || 0;
        const bErr = statsMap.get(b.form_name)?.failed_records || 0;
        return sortOrder === 'asc' ? aErr - bErr : bErr - aErr;
      });
    } else if (sortField === 'last_sync') {
      filtered = [...filtered].sort((a, b) => {
        const aTime = a.last_sync_time || '';
        const bTime = b.last_sync_time || '';
        return sortOrder === 'asc'
          ? aTime.localeCompare(bTime)
          : bTime.localeCompare(aTime);
      });
    }

    return {
      enabledForms: filtered.filter((f) => f.enabled),
      disabledForms: filtered.filter((f) => !f.enabled),
    };
  }, [forms, search, sortField, sortOrder, statsMap]);

  const handleToggle = async (formName: string, enabled: boolean) => {
    try {
      await onUpdateForm(formName, enabled);
      message.success(`${formName} 已${enabled ? '启用' : '禁用'}`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleBatchToggle = async (list: FormItem[], enable: boolean) => {
    if (list.length === 0) return;
    for (const f of list) {
      try {
        await onUpdateForm(f.form_name, enable);
      } catch (_err) {
        // continue
      }
    }
    message.success(`已${enable ? '启用' : '禁用'} ${list.length} 个表单`);
  };

  const columns = useFormColumns({
    statsMap,
    updating,
    onToggle: handleToggle,
    onEdit: (form) => {
      setEditingForm(form);
      setConfigDrawerVisible(true);
    },
  });

  return (
    <>
      <Panel
      title={
        <span style={{ fontWeight: 600 }}>
          同步范围（表单管理）({forms.length}个)
        </span>
      }
      loading={loading}
    >
      <FormToolbar
        search={search}
        onSearchChange={setSearch}
        sortField={sortField}
        onSortChange={(v) => {
          setSortField(v as SortField);
          if (v !== 'none' && !sortOrder) setSortOrder('desc');
        }}
        sortOrder={sortOrder}
        onSortOrderChange={setSortOrder}
        forms={enabledForms}
        groupEnabled={true}
        onBatchToggle={handleBatchToggle}
      />

      <Collapse defaultActiveKey={['enabled']} ghost>
        <CollapsePanel
          header={
            <Tag color="success">已启用</Tag>
          }
          key="enabled"
        >
          <Table
            columns={columns}
            dataSource={enabledForms}
            rowKey="form_name"
            pagination={false}
            size="small"
            scroll={{ x: 800 }}
          />
        </CollapsePanel>
        <CollapsePanel
          header={
            <Tag color="default">已禁用</Tag>
          }
          key="disabled"
        >
          <Table
            columns={columns}
            dataSource={disabledForms}
            rowKey="form_name"
            pagination={false}
            size="small"
            scroll={{ x: 800 }}
          />
        </CollapsePanel>
      </Collapse>
      </Panel>
      <FormConfigDrawer
        visible={configDrawerVisible}
        form={editingForm}
        submitting={updatingConfig ?? false}
        onCancel={() => setConfigDrawerVisible(false)}
        onSubmit={(data) => {
          if (editingForm) {
            onUpdateFormConfig(editingForm.form_name, data);
            message.success(`${editingForm.form_name} 配置已更新`);
            setConfigDrawerVisible(false);
          }
        }}
      />
    </>
  );
};

export default FormsManager;
