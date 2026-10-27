import type { ProLayoutProps } from '@ant-design/pro-components';
import { theme as antdTheme } from 'antd';

export const themeConfig = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    fontFamily:
      "AlibabaSans, -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif",
    colorPrimary: '#0f766e',
    colorInfo: '#0f766e',
    colorSuccess: '#15803d',
    colorWarning: '#d97706',
    colorError: '#dc2626',
    colorText: '#334155',
    colorTextSecondary: '#64748b',
    colorBgLayout: '#f3f6f4',
    colorBgContainer: '#ffffff',
    colorBorder: '#e1e8e4',
    colorBorderSecondary: '#e9efec',
    borderRadius: 10,
    controlHeight: 40,
    motionDurationMid: '0.2s',
  },
  components: {
    Button: {
      fontWeight: 500,
      primaryShadow: '0 4px 12px rgba(15, 118, 110, 0.18)',
    },
    Table: {
      headerBg: '#f7f9f8',
      headerColor: '#52646c',
      rowHoverBg: '#f0f8f5',
    },
    Card: {
      headerBg: '#ffffff',
    },
    Tabs: {
      itemSelectedColor: '#0f766e',
      inkBarColor: '#0f766e',
    },
  },
};

const Settings: ProLayoutProps = {
  navTheme: 'realDark',
  colorPrimary: '#0f766e',
  layout: 'side',
  contentWidth: 'Fluid',
  fixedHeader: true,
  fixSiderbar: true,
  colorWeak: false,
  title: '',
  logo: false,
  iconfontUrl: '',
  siderWidth: 232,
  token: {
    sider: {
      colorMenuBackground: '#102c30',
      colorTextMenu: 'rgba(226, 239, 235, 0.68)',
      colorTextMenuSelected: '#f4fffc',
      colorBgMenuItemSelected: 'rgba(45, 212, 191, 0.14)',
      colorTextMenuActive: '#5eead4',
    },
    pageContainer: {
      colorBgPageContainer: 'transparent',
      paddingInlinePageContainerContent: 32,
      paddingBlockPageContainerContent: 28,
    },
    header: {
      colorBgHeader: 'rgba(255, 255, 255, 0.94)',
      heightLayoutHeader: 64,
    },
  },
};

export default Settings;
