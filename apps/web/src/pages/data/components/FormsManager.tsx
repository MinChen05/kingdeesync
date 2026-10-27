import { CheckCircleFilled, PauseCircleOutlined } from '@ant-design/icons';
import { App, Button, Collapse, Empty, Table } from 'antd';
import React, { useMemo, useState } from 'react';
import Panel from '@/components/Panel';
import { errorMessage } from '@/utils/errorMessage';
import type { FormItem, FormStat } from '../types';
import { useFormColumns } from './FormColumns';
import FormConfigDrawer from './FormConfigDrawer';
import { FormToolbar } from './FormToolbar';

interface FormsManagerProps {
  forms: FormItem[];
  statsMap: Map<string, FormStat>;
  loading?: boolean;
  onUpdateForm: (formName: string, enabled: boolean) => Promise<void>;
  onUpdateFormConfig: (
    formName: string,
    data: Partial<FormItem>,
  ) => Promise<void>;
  updating?: boolean;
  updatingConfig?: boolean;
}

type SortField = 'errors' | 'last_sync' | 'none';

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

  const { enabledForms, disabledForms, filteredCount } = useMemo(() => {
    let filtered = forms;

    if (search) {
      const keyword = search.toLowerCase();
      filtered = filtered.filter((form) =>
        form.form_name.toLowerCase().includes(keyword),
      );
    }

    if (sortField === 'errors') {
      filtered = [...filtered].sort((a, b) => {
        const aErrors = statsMap.get(a.form_name)?.failed_records || 0;
        const bErrors = statsMap.get(b.form_name)?.failed_records || 0;
        return sortOrder === 'asc' ? aErrors - bErrors : bErrors - aErrors;
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
      enabledForms: filtered.filter((form) => form.enabled),
      disabledForms: filtered.filter((form) => !form.enabled),
      filteredCount: filtered.length,
    };
  }, [forms, search, sortField, sortOrder, statsMap]);

  const openConfig = (form: FormItem) => {
    setEditingForm(form);
    setConfigDrawerVisible(true);
  };

  const handleToggle = async (formName: string, enabled: boolean) => {
    try {
      await onUpdateForm(formName, enabled);
      message.success(`${formName} 已${enabled ? '启用' : '禁用'}`);
    } catch (error) {
      message.error(
        `${formName} ${enabled ? '启用' : '禁用'}失败：${errorMessage(error)}`,
      );
    }
  };

  const handleBatchToggle = async (list: FormItem[], enable: boolean) => {
    if (list.length === 0) return;
    let failed = 0;
    for (const form of list) {
      try {
        await onUpdateForm(form.form_name, enable);
      } catch {
        failed += 1;
      }
    }
    const completed = list.length - failed;
    if (failed === 0) {
      message.success(`已${enable ? '启用' : '禁用'} ${completed} 个表单`);
    } else {
      message.warning(
        `已${enable ? '启用' : '禁用'} ${completed} 个表单，失败 ${failed} 个，请检查后端服务后对失败表单重试`,
      );
    }
  };

  const columns = useFormColumns({
    statsMap,
    updating,
    onToggle: handleToggle,
    onEdit: openConfig,
  });

  const renderTable = (dataSource: FormItem[]) => (
    <Table<FormItem>
      className="data-forms-table"
      columns={columns}
      dataSource={dataSource}
      rowKey="form_name"
      rowClassName={() => 'interactive-list'}
      pagination={false}
      size="middle"
      scroll={{ x: 980 }}
      locale={{
        emptyText: (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={search ? '没有符合搜索条件的表单' : '当前分组暂无表单'}
          />
        ),
      }}
      onRow={(record) => ({
        onClick: () => openConfig(record),
        onKeyDown: (event) => {
          if (event.key === 'Enter') openConfig(record);
        },
        tabIndex: 0,
        'aria-label': `配置 ${record.form_name}`,
      })}
    />
  );

  const groupHeader = (title: string, list: FormItem[], enabled: boolean) => {
    const errorCount = list.reduce((total, form) => {
      const stat = statsMap.get(form.form_name);
      return total + (stat?.failed_records || form.error_count || 0);
    }, 0);

    return (
      <div className="data-group-header">
        <span className="data-group-title">
          {enabled ? (
            <CheckCircleFilled className="is-enabled" />
          ) : (
            <PauseCircleOutlined className="is-disabled" />
          )}
          <strong>{title}</strong>
          <span className="data-group-count">{list.length}</span>
          {errorCount > 0 && (
            <span className="data-group-errors">{errorCount} 个错误</span>
          )}
        </span>
        <Button
          size="small"
          disabled={list.length === 0 || updating}
          onClick={(event) => {
            event.stopPropagation();
            void handleBatchToggle(list, !enabled);
          }}
          onKeyDown={(event) => event.stopPropagation()}
        >
          {enabled ? '全部禁用' : '全部启用'}
        </Button>
      </div>
    );
  };

  return (
    <>
      <Panel
        title="同步范围"
        loading={loading}
        extra={
          <span className="data-panel-caption">
            已启用 {enabledForms.length} · 已停用 {disabledForms.length}
          </span>
        }
      >
        <FormToolbar
          search={search}
          onSearchChange={setSearch}
          sortField={sortField}
          onSortChange={(value) => setSortField(value as SortField)}
          sortOrder={sortOrder}
          onSortOrderChange={setSortOrder}
          resultCount={filteredCount}
          totalCount={forms.length}
        />
        <Collapse
          className="data-form-groups"
          defaultActiveKey={['enabled', 'disabled']}
          ghost
          items={[
            {
              key: 'enabled',
              label: groupHeader('运行中的表单', enabledForms, true),
              children: renderTable(enabledForms),
            },
            {
              key: 'disabled',
              label: groupHeader('已停用的表单', disabledForms, false),
              children: renderTable(disabledForms),
            },
          ]}
        />
      </Panel>
      <FormConfigDrawer
        visible={configDrawerVisible}
        form={editingForm}
        submitting={updatingConfig ?? false}
        onCancel={() => setConfigDrawerVisible(false)}
        onSubmit={async (data) => {
          if (!editingForm) return;
          try {
            await onUpdateFormConfig(editingForm.form_name, data);
            message.success(`${editingForm.form_name} 配置已更新`);
            setConfigDrawerVisible(false);
          } catch (error) {
            message.error(`配置更新失败：${errorMessage(error)}`);
          }
        }}
      />
    </>
  );
};

export default FormsManager;
