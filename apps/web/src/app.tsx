import type { MenuDataItem, Settings as LayoutSettings } from '@ant-design/pro-components';
import { SettingDrawer } from '@ant-design/pro-components';
import type { RequestConfig, RunTimeLayoutConfig } from '@umijs/max';
import { Link } from '@umijs/max';
import { App, ConfigProvider, theme as antdTheme, Typography } from 'antd';
import React, { useEffect } from 'react';

import defaultSettings from '../config/defaultSettings';
import { errorConfig, registerMessageInstance } from './requestErrorConfig';
import { getVersion } from './services/v1';
import GlobalSyncIndicator from './components/GlobalSyncIndicator';
import SyncLogo from './components/Logo';

const { Text } = Typography;

const isDev = process.env.NODE_ENV === 'development';

/**
 * 在 <App> 内部调用 useApp() 获取 message / notification 实例，并注册到 requestErrorConfig。
 * （原因：遵守 React Hooks 规则，同时将实例注入给模块级 errorHandler 使用）
 */
function RequestErrorBridge(): null {
  const { message, notification } = App.useApp();
  useEffect(() => {
    registerMessageInstance(message, notification);
  }, [message, notification]);
  return null;
}

const STORAGE_KEY = 'kingdee-sync-layout-settings';

/**
 * 初始化状态（无登录）
 */
export async function getInitialState(): Promise<{
  settings?: Partial<LayoutSettings>;
  settingDrawerOpen?: boolean;
  version?: string;
}> {
  let settings = defaultSettings as Partial<LayoutSettings>;
  let version = '';
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      settings = { ...settings, ...JSON.parse(stored) };
    }
  } catch {
    // ignore
  }
  try {
    const res = await getVersion();
    version = res?.version || '';
  } catch {
    // ignore
  }
  return {
    settings,
    settingDrawerOpen: false,
    version,
  };
}

/** 菜单名称映射（原因：避免 ProLayout 国际化报错，name 用英文 key，这里映射中文显示） */
const menuNameMap: Record<string, string> = {
  overview: '系统概览',
  sync: '同步管理',
  schedule: '任务调度',
  data: '数据配置',
  monitor: '监控分析',
  system: '系统管理',
};

/**
 * ProLayout 运行时配置
 */
export const layout: RunTimeLayoutConfig = ({
  initialState,
  setInitialState,
}) => {
  return {
    // 菜单名称映射：把英文 key 替换为中文显示
    menuDataRender: (menuList: MenuDataItem[]) => {
      const transform = (items: MenuDataItem[]): MenuDataItem[] =>
        items.map((item) => ({
          ...item,
          name: item.name ? menuNameMap[item.name] || item.name : item.name,
          children: item.children ? transform(item.children) : undefined,
        }));
      return transform(menuList);
    },
    // 无背景图
    bgLayoutImgList: [],
    // 无 footer
    footerRender: false,
    // 顶部操作区（无登录相关）
    actionsRender: () => [],
    // 无头像
    avatarProps: {
      src: '',
      title: '',
      render: () => null,
    },
    // 链接渲染
    menuItemRender: (item, dom) => {
      if (item.path) {
        return (
          <Link to={item.path} prefetch>
            {dom}
          </Link>
        );
      }
      return dom;
    },
    // 侧边栏底部显示版本号
    links: initialState?.version
      ? [
          <div key="version" className="px-4 py-2 text-center">
            <Text type="secondary" className="text-xs">
              v{initialState.version}
            </Text>
          </div>,
        ]
      : [],
    // 侧边栏头部：去掉 menuHeaderRender，把 Logo 放顶部 header（原因：避免上下重复显示）
    // mix 布局下 header 显示 Logo + 标题
    headerTitleRender: () => (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <SyncLogo size={28} />
        <span style={{ fontSize: 16, fontWeight: 600, color: '#f1f5f9', letterSpacing: 1 }}>金蝶数据同步</span>
      </div>
    ),
    childrenRender: (children) => {
      // 根据布局 navTheme 动态切换 antd 暗色算法，默认深色科技感
      // navTheme 类型为 'light' | 'realDark' | undefined，非 'light' 即视为深色（含默认 realDark）
      const navTheme = initialState?.settings?.navTheme;
      const isDark = navTheme !== 'light';
      return (
        <ConfigProvider
          theme={{
            algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
          }}
        >
          <App>
            <RequestErrorBridge />
            {children}
            <GlobalSyncIndicator />
            {/* 布局设置抽屉仅开发环境可用（原因：全局样式硬编码深色玻璃拟态，
                生产环境切亮色主题会出现视觉破损；内部工具固定深色主题） */}
            {isDev && (
              <SettingDrawer
                disableUrlParams
                enableDarkTheme
                collapse={initialState?.settingDrawerOpen}
                onCollapseChange={(open) => {
                  setInitialState((s) => ({
                    ...s,
                    settingDrawerOpen: open,
                  }));
                }}
                settings={initialState?.settings}
                onSettingChange={(settings) => {
                  try {
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
                  } catch {
                    // ignore
                  }
                  setInitialState((s) => ({
                    ...s,
                    settings,
                  }));
                }}
              />
            )}
          </App>
        </ConfigProvider>
      );
    },
    // layout 配置（从 defaultSettings）
    ...initialState?.settings,
  };
};

/**
 * Request 配置
 */
export const request: RequestConfig = {
  baseURL: isDev ? '' : '',
  ...errorConfig,
};
