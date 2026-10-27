import {
  InfoCircleOutlined,
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
import './index.less';

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
    { key: 'about', label: '关于系统', icon: <InfoCircleOutlined /> },
  ];

  return (
    <div className="page-stack system-page">
      <PageHeader
        title="系统管理"
        description="查看运行参数与服务状态，执行数据维护和版本检查"
      />
      <Tabs
        className="system-tabs"
        activeKey={activeTab}
        onChange={setActiveTab}
        items={items}
        size="large"
      />
      <div className="system-tab-content" key={activeTab}>
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
