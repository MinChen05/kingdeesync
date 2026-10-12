/**
 * 从未知异常提取可展示消息。
 * （原因：schedule/sync/data 三页面曾有逐字相同的私有实现，收敛为单一工具）
 */
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
