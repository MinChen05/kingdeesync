import { request } from '@umijs/max';
import type { ApiResponse, SyncStatusData, SyncStopData } from './generated-api';

// ─── Sync ───

// 原因：仅保留有真实消费方的两个活函数（sync/hooks.ts 轮询 + 停止链路），
// 其余 37 个零消费方函数经 2026-11-16 逐函数盘点确认死代码后移除。
export async function getSyncStatus(
  runId?: string,
  opts?: { skipErrorHandler?: boolean },
) {
  return request<ApiResponse<SyncStatusData>>('/api/v1/sync/status', {
    method: 'GET',
    params: runId ? { run_id: runId } : undefined,
    ...(opts || {}),
  });
}

export async function stopSync(runId: string) {
  return request<ApiResponse<SyncStopData>>('/api/v1/sync/stop', {
    method: 'POST',
    params: { run_id: runId },
  });
}
