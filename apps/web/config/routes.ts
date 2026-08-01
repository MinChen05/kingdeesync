/**
 * 金蝶数据同步工具 - Ant Design Pro 路由配置
 * name 使用英文 key，中文显示在 app.tsx 中映射（原因：避免 ProLayout 国际化报错）
 */
export default [
  {
    path: '/overview',
    name: 'overview',
    icon: 'dashboard',
    component: './Overview',
  },
  {
    path: '/sync',
    name: 'sync',
    icon: 'sync',
    component: './sync',
  },
  {
    path: '/schedule',
    name: 'schedule',
    icon: 'clockCircle',
    component: './schedule',
  },
  {
    path: '/data',
    name: 'data',
    icon: 'database',
    component: './data',
  },
  {
    path: '/monitor',
    name: 'monitor',
    icon: 'radarChart',
    component: './monitor',
  },
  {
    path: '/system',
    name: 'system',
    icon: 'setting',
    component: './system',
  },
  {
    path: '/',
    redirect: '/overview',
  },
  {
    component: './404',
    path: '/*',
  },
];
