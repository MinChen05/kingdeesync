import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// Marker to skip auto-toast when caller handles it explicitly
const SKIP_TOAST = Symbol('skipToast');

client.interceptors.request.use(config => {
  config.meta = config.meta || {};
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const config = error.config || {};
    const skip = config.meta?.skipToast;

    const status = error.response?.status;
    const serverMsg = error.response?.data?.detail || error.response?.data?.error;

    let message = serverMsg || error.message || '请求失败';

    // Friendly mapping for common cases
    if (!serverMsg && status === 404) message = '资源不存在';
    if (!serverMsg && status === 408) message = '请求超时';
    if (!serverMsg && status === 500) message = '服务器内部错误';
    if (!serverMsg && error.code === 'ECONNABORTED') message = '请求超时，请稍后重试';
    if (!serverMsg && error.code === 'ERR_NETWORK') message = '无法连接到服务器';

    console.error('API Error:', message, { status, path: config.url });

    if (!skip) {
      // Dispatch event for ToastContext to listen
      window.dispatchEvent(new CustomEvent('api-error', { detail: { message } }));
    }

    return Promise.reject(Object.assign(new Error(message), { status, skip }));
  }
);

export default client;

export { SKIP_TOAST };
