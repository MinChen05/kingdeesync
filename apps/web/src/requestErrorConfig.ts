import type { RequestConfig } from '@umijs/max';
import type { MessageInstance } from 'antd/es/message/interface';
import type { NotificationInstance } from 'antd/es/notification/interface';

// 错误处理方案： 错误类型
enum ErrorShowType {
  SILENT = 0,
  WARN_MESSAGE = 1,
  ERROR_MESSAGE = 2,
  NOTIFICATION = 3,
  REDIRECT = 9,
}
// 与后端约定的响应数据格式（支持 ok 和 success 两种字段名）
interface ResponseStructure {
  ok?: boolean;
  success?: boolean;
  data?: unknown;
  errorCode?: number;
  errorMessage?: string;
  error?: string;
  showType?: ErrorShowType;
}

/**
 * 全局 message / notification 实例持有者。
 * 由 RequestErrorBridge 在 <App> 内部通过 useApp() 注入（原因：遵守 Hooks 规则，消费动态主题上下文）。
 */
let messageInstance: MessageInstance | null = null;
let notificationInstance: NotificationInstance | null = null;

/**
 * 从 <App> 内部注入 message 和 notification 实例到 errorHandler 可访问的作用域。
 */
export function registerMessageInstance(
  msg: MessageInstance,
  notif: NotificationInstance,
): void {
  messageInstance = msg;
  notificationInstance = notif;
}

/**
 * 获取当前 message 实例（原因：正常情况下 <App> 渲染后必然已注入）。
 */
function getMessage(): MessageInstance {
  if (messageInstance) return messageInstance;
  throw new Error('messageInstance not registered. RequestErrorBridge must be rendered inside <App>.');
}

/**
 * 获取当前 notification 实例（原因：正常情况下 <App> 渲染后必然已注入）。
 */
function getNotification(): NotificationInstance {
  if (notificationInstance) return notificationInstance;
  throw new Error('notificationInstance not registered. RequestErrorBridge must be rendered inside <App>.');
}

/**
 * @name 错误处理
 * pro 自带的错误处理，可以在这里做自己的改动
 * @doc https://umijs.org/docs/max/request#配置
 */
export const errorConfig: RequestConfig = {
  // 错误处理： umi@3 的错误处理方案。
  errorConfig: {
    // 错误抛出：适配后端 {ok: false, error: "xxx"} 格式（原因：后端使用 ok 字段而非 success）
    errorThrower: (res) => {
      const { ok, success, data, errorCode, errorMessage, error, showType } =
        res as unknown as ResponseStructure;
      const isFailed = ok === false || success === false;
      const msg = error || errorMessage;
      if (isFailed && msg) {
        const bizError = new Error(msg) as Error & { info: ResponseStructure };
        bizError.name = 'BizError';
        bizError.info = { errorCode, errorMessage: msg, showType, data };
        throw bizError;
      }
    },
    // 错误接收及处理
    errorHandler: (error: Error & { response?: { status: number }; request?: unknown; info?: ResponseStructure }, opts: { skipErrorHandler?: boolean } & Record<string, unknown>) => {
      if (opts?.skipErrorHandler) throw error;
      const message = getMessage();
      // 我们的 errorThrower 抛出的错误。
      if (error.name === 'BizError') {
        const errorInfo: ResponseStructure | undefined = error.info;
        if (errorInfo) {
          const { errorMessage, errorCode } = errorInfo;
          switch (errorInfo.showType) {
            case ErrorShowType.SILENT:
              // do nothing
              break;
            case ErrorShowType.WARN_MESSAGE:
              message.warning(errorMessage);
              break;
            case ErrorShowType.ERROR_MESSAGE:
              message.error(errorMessage);
              break;
            case ErrorShowType.NOTIFICATION:
              getNotification().open({
                message: String(errorCode),
                description: errorMessage,
              });
              break;
            case ErrorShowType.REDIRECT:
              window.location.href = '/user/login';
              break;
            default:
              message.error(errorMessage);
          }
        }
      } else if (error.response) {
        // Axios 的错误
        message.error(`Response status:${error.response.status}`);
      } else if (typeof navigator !== 'undefined' && !navigator.onLine) {
        message.error('网络不可用，请检查连接后重试。');
      } else if (error.request) {
        message.error('None response! Please retry.');
      } else {
        message.error('Request error, please retry.');
      }
    },
  },

  // 响应拦截器
  responseInterceptors: [],
};
