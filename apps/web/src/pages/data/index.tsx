import React from 'react';
import PageHeader from '@/components/PageHeader';
import DataSourceStatus from './components/DataSourceStatus';
import FormsManager from './components/FormsManager';
import { useDataPage } from './hooks';
import type { FormItem } from './types';

/**
 * 数据配置页：数据源状态 + 同步范围（表单管理）。
 *
 * （原因：把"数据链路是否通"和"哪些表单参与同步"集中到一页，
 *  运维人员先确认数据源正常，再调整同步范围）
 */
const DataPage: React.FC = () => {
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

  // 失败一律 rethrow 且不再弹 toast：成功/失败提示由 FormsManager 统一负责
  // （原因：此前 catch 吞错导致组件层"失败也报成功"，且与组件层形成双重 toast）
  const handleUpdateForm = async (formName: string, enabled: boolean) => {
    await updateForm(formName, enabled);
  };

  const handleUpdateFormConfig = async (
    formName: string,
    data: Partial<FormItem>,
  ) => {
    await updateFormConfig(formName, data);
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
