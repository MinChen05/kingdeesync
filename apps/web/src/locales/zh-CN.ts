/**
 * 最小化 locale 文件：消除 ProLayout 菜单国际化报错，并提供 ErrorBoundary 中文文案。
 * （原因：ProLayout 内部硬编码 intl.formatMessage({ id: 'menu.XXX' })，
 *  即使 locale 插件关闭也会报错；ErrorBoundary 的 app.error.* 键缺失时
 *  会回退到 defaultMessage 英文，此处补齐中文）
 */
export default {
  'menu.overview': '系统概览',
  'menu.dashboard': '数据看板',
  'menu.sync': '同步管理',
  'menu.schedule': '任务调度',
  'menu.data': '数据配置',
  'menu.monitor': '监控分析',
  'menu.system': '系统管理',

  'app.error.render.title': '页面出错了',
  'app.error.render.description':
    '抱歉，页面发生错误，请刷新页面或返回首页。',
  'app.error.chunk.title': '页面资源加载失败',
  'app.error.chunk.description.offline':
    '网络连接已断开，请检查网络后重新加载页面。',
  'app.error.chunk.description.online':
    '页面资源加载失败，请刷新页面重试。',
  'app.error.retry': '重试',
  'app.error.reload': '重新加载',
  'app.error.home': '返回首页',
};
