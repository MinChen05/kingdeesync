/**
 * 最小化 locale 文件，仅用于消除 ProLayout 菜单国际化报错。
 * （原因：ProLayout 内部硬编码 intl.formatMessage({ id: 'menu.XXX' })，
 *  即使 locale 插件关闭也会报错，补一个空映射即可消除）
 */
export default {
  'menu.overview': '系统概览',
  'menu.sync': '同步管理',
  'menu.schedule': '任务调度',
  'menu.data': '数据配置',
  'menu.monitor': '监控分析',
  'menu.system': '系统管理',
};
