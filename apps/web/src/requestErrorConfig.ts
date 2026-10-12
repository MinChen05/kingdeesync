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
 * 从后端 problem 信封 `{"error":{"code","message"}}` 提取业务错误消息；
 * 结构不匹配时返回 undefined，由调用方回落到状态码文案（原因：非 v1 路由可能返回 HTML/纯文本）。
 */
function extractProblemMessage(data: unknown): string | undefined {
  if (typeof data !== 'object' || data === null) return undefined;
  const err = (data as { error?: unknown }).error;
  if (typeof err === 'object' && err !== null) {
    const msg = (err as { message?: unknown }).message;
    if (typeof msg === 'string' && msg) return msg;
  }
  return undefined;
}

/** 常见 HTTP 状态码的中文文案（原因：替换英文 "Response status:N"，非已知码回退通用文案） */
function statusTextCN(status: number): string {
  switch (status) {
    case 400:
      return '请求参数有误，请检查后重试';
    case 404:
      return '请求的资源不存在';
    case 409:
      return '操作冲突：资源当前状态不允许该操作';
    case 500:
      return '服务器内部错误，请稍后重试';
    case 502:
    case 503:
    case 504:
      return '服务暂时不可用，请稍后重试';
    default:
      return `请求失败（状态码 ${status}），请稍后重试`;
  }
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
    errorHandler: (error: Error & { response?: { status: number; data?: unknown }; request?: unknown; info?: ResponseStructure }, opts: { skipErrorHandler?: boolean } & Record<string, unknown>) => {
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
        // Axios 的错误：透出后端 problem 信封（{"error":{"code","message"}}）中的业务错误消息，
        // 否则只弹英文状态码，后端中文错误被吞（原因：审阅发现"错误提示英文且吞后端消息"）
        const status = error.response.status;
        const backendMessage = extractProblemMessage(error.response.data);
        message.error(
          backendMessage
            ? `服务响应异常（${status}）：${backendMessage}`
            : statusTextCN(status),
        );
      } else if (typeof navigator !== 'undefined' && !navigator.onLine) {
        message.error('网络不可用，请检查网络连接后重试。');
      } else if (error.request) {
        message.error('服务无响应，请检查后端服务是否正常运行。');
      } else {
        message.error('请求失败，请稍后重试。');
      }
    },
  },

  // 响应拦截器
  responseInterceptors: [],
};
