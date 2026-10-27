import type { MenuDataItem } from '@ant-design/pro-components';
import type { RequestConfig, RunTimeLayoutConfig } from '@umijs/max';
import { Link, useLocation } from '@umijs/max';
import { App, ConfigProvider } from 'antd';
import React, { useEffect } from 'react';

import defaultSettings, { themeConfig } from '../config/defaultSettings';
import GlobalSyncIndicator from './components/GlobalSyncIndicator';
import SyncLogo from './components/Logo';
import { errorConfig, registerMessageInstance } from './requestErrorConfig';
import { getVersion } from './services/v1';

function RequestErrorBridge(): null {
  const { message, notification } = App.useApp();
  useEffect(() => {
    registerMessageInstance(message, notification);
  }, [message, notification]);
  return null;
}

function AppContent({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return (
    <ConfigProvider theme={themeConfig}>
      <App>
        <RequestErrorBridge />
        <div className="app-route-frame" key={location.pathname}>
          {children}
        </div>
        <GlobalSyncIndicator />
      </App>
    </ConfigProvider>
  );
}

export async function getInitialState(): Promise<{
  settings?: Partial<typeof defaultSettings>;
  version?: string;
}> {
  let version = '';
  try {
    const res = await getVersion();
    version = res?.version || '';
  } catch {
    version = '';
  }
  return { settings: defaultSettings, version };
}

const menuNameMap: Record<string, string> = {
  overview: '系统概览',
  dashboard: '数据看板',
  sync: '同步管理',
  schedule: '任务调度',
  data: '数据配置',
  monitor: '监控分析',
  system: '系统管理',
};

export const layout: RunTimeLayoutConfig = ({ initialState }) => ({
  menuDataRender: (menuList: MenuDataItem[]) => {
    const transform = (items: MenuDataItem[]): MenuDataItem[] =>
      items.map((item) => ({
        ...item,
        name: item.name ? menuNameMap[item.name] || item.name : item.name,
        children: item.children ? transform(item.children) : undefined,
      }));
    return transform(menuList);
  },
  bgLayoutImgList: [],
  footerRender: false,
  menuHeaderRender: () => (
    <div className="brand-lockup">
      <SyncLogo size={32} />
      <span className="brand-name">金蝶数据同步</span>
    </div>
  ),
  avatarProps: {
    src: '',
    title: '',
    render: () => null,
  },
  menuItemRender: (item, dom) =>
    item.path ? (
      <Link to={item.path} prefetch>
        {dom}
      </Link>
    ) : (
      dom
    ),
  links: initialState?.version
    ? [
        <div key="version" className="sider-version">
          <span>SYNC CONSOLE</span>
          <span>v{initialState.version}</span>
        </div>,
      ]
    : [],
  childrenRender: (children) => <AppContent>{children}</AppContent>,
  ...initialState?.settings,
});

export const request: RequestConfig = {
  ...errorConfig,
};
