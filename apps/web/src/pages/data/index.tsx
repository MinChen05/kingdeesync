import React from 'react';
import PageHeader from '@/components/PageHeader';
import DataSourceStatus from './components/DataSourceStatus';
import FormsManager from './components/FormsManager';
import { useDataPage } from './hooks';
import type { FormItem } from './types';
import './index.less';

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
    <div className="page-stack data-page">
      <PageHeader
        title="数据配置"
        description="确认数据链路健康状态，维护参与同步的表单与字段规则"
      />
      <DataSourceStatus
        kingdeeApi={diagInfo.kingdee_api}
        database={diagInfo.database}
        loading={diagLoading}
      />
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
