import { App } from 'antd';
import React from 'react';
import PageHeader from '@/components/PageHeader';
import DataSourceStatus from './components/DataSourceStatus';
import FormsManager from './components/FormsManager';
import { useDataPage } from './hooks';
import type { FormItem } from './types';

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/**
 * 数据配置页：数据源状态 + 同步范围（表单管理）。
 *
 * （原因：把"数据链路是否通"和"哪些表单参与同步"集中到一页，
 *  运维人员先确认数据源正常，再调整同步范围）
 */
const DataPage: React.FC = () => {
  const { message } = App.useApp();
  const {
    allForms,
    formsLoading,
    diagInfo,
    diagLoading,
    statsMap,
    updateForm,
    updateFormConfig,
    updating,
    updatingConfig,
  } = useDataPage();

  const handleUpdateForm = async (formName: string, enabled: boolean) => {
    try {
      await updateForm(formName, enabled);
    } catch (err) {
      message.error(errorMessage(err) || '操作失败');
    }
  };

  const handleUpdateFormConfig = async (formName: string, data: Partial<FormItem>) => {
    try {
      await updateFormConfig(formName, data);
    } catch (err) {
      message.error(errorMessage(err) || '操作失败');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="数据配置" description="查看数据源状态，管理同步表单范围" />

      {/* 数据源状态 */}
      <DataSourceStatus
        kingdeeApi={diagInfo.kingdee_api}
        database={diagInfo.database}
        loading={diagLoading}
      />

      {/* 表单管理 */}
      <FormsManager
        forms={allForms}
        statsMap={statsMap}
        loading={formsLoading}
        onUpdateForm={handleUpdateForm}
        onUpdateFormConfig={handleUpdateFormConfig}
        updating={updating}
        updatingConfig={updatingConfig}
      />
    </div>
  );
};

export default DataPage;
