/**
 * 权限配置：所有路由公开访问（无登录）
 */
export default function access() {
  return {
    canAdmin: true,
  };
}
