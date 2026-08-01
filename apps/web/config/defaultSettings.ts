import type { ProLayoutProps } from '@ant-design/pro-components';

/**
 * @name
 */
const Settings: ProLayoutProps = {
  navTheme: 'realDark',
  colorPrimary: '#38bdf8',
  layout: 'mix',
  contentWidth: 'Fluid',
  fixedHeader: true,
  fixSiderbar: true,
  colorWeak: false,
  title: '',
  logo: false,
  iconfontUrl: '',
  token: {
    // 侧边栏：近黑蓝 + 玻璃质感，选中项主色半透明高亮
    sider: {
      colorMenuBackground: '#0d1526',
      colorTextMenu: 'rgba(226,232,240,0.72)',
      colorTextMenuSelected: '#ffffff',
      colorBgMenuItemSelected: 'rgba(56,189,248,0.16)',
      colorTextMenuActive: '#38bdf8',
    },
    // 页面容器：透明背景，透出全局深色渐变
    pageContainer: {
      colorBgPageContainer: 'transparent',
      paddingInlinePageContainerContent: 24,
      paddingBlockPageContainerContent: 24,
    },
    // Header：深色半透明，配合全局毛玻璃
    header: {
      colorBgHeader: 'rgba(13,21,38,0.85)',
      heightLayoutHeader: 56,
    },
  },
};

export default Settings;
