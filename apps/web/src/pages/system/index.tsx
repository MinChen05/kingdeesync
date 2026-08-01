import {
  CheckCircleOutlined,
  SettingOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { Tabs } from 'antd';
import React, { useState } from 'react';
import PageHeader from '@/components/PageHeader';
import AboutPanel from './components/AboutPanel';
import ConfigPanel from './components/ConfigPanel';
import MaintenancePanel from './components/MaintenancePanel';
import { useSystemPage } from './hooks';

/**
 * 系统管理页：配置 + 维护 + 关于。
 *
 * 本文件只做布局组装，不含展示细节；与其他页面架构一致
 * （index 组装 + components/ 面板 + hooks 数据 + types 类型）。（原因：全站页面结构统一）
 */
const SystemPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('config');
  const {
    config,
    configLoading,
    version,
    diagnostics,
    diagLoading,
    archiveLogs,
    archiving,
    testConnections,
    testing,
  } = useSystemPage();

  const items = [
    { key: 'config', label: '系统配置', icon: <SettingOutlined /> },
    { key: 'maintenance', label: '维护操作', icon: <ToolOutlined /> },
    { key: 'about', label: '关于', icon: <CheckCircleOutlined /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="系统管理" description="系统配置、维护操作与版本信息" />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={items}
        size="large"
      />

      <div>
        {activeTab === 'config' && (
          <ConfigPanel
            config={config}
            loading={configLoading}
            diagnostics={diagnostics}
            diagLoading={diagLoading}
            onTestConnections={testConnections}
            testing={testing}
          />
        )}
        {activeTab === 'maintenance' && (
          <MaintenancePanel onArchive={archiveLogs} archiving={archiving} />
        )}
        {activeTab === 'about' && <AboutPanel version={version} />}
      </div>
    </div>
  );
};

export default SystemPage;
