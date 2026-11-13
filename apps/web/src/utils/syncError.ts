import { ApiProblemError } from '@/services/v1';

/**
 * 目标库内存授予排队守卫命中时，v1 写路径（手动触发 / 失败重试）返回的 409 错误码。
 * （原因：该 409 与"已有任务在跑"等待方向不同——前者需等外部报表作业释放授予，
 *  见 docs/adr/0007 排队守卫；混用文案会把排障引向错误一侧）
 */
export const TARGET_DB_GRANT_QUEUE_BUSY = 'TARGET_DB_GRANT_QUEUE_BUSY';

/** 判定错误是否为排队守卫拦截。 */
export function isGrantQueueBusyError(err: unknown): boolean {
  return (
    err instanceof ApiProblemError &&
    err.status === 409 &&
    err.code === TARGET_DB_GRANT_QUEUE_BUSY
  );
}

/**
 * 取排队守卫拦截的服务端提示（含实际排队时长与阈值）；
 * 服务端未给出 message 时回退调用方兜底文案。
 */
export function grantQueueMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiProblemError) {
    const msg = err.message?.trim();
    if (msg) return msg;
  }
  return fallback;
}
