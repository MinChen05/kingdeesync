/**
 * 代理配置：开发环境将 /api/** 代理到 Go 后端
 */
export default {
  dev: {
    '/api/': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
  test: {
    '/api/': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
};
