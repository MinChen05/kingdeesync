import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from '@umijs/max';
import { getSyncLogs, startSync, stopSync } from './api';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const requestMock = vi.mocked(request);

describe('同步 API 契约', () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it('启动请求返回并保留 run_id', async () => {
    requestMock.mockResolvedValue({
      ok: true,
      data: { run_id: 'run-001', dry_run: false },
      error: '',
      code: '',
    });

    const response = await startSync({ sync_type: 'full', forms: ['物料'] });

    expect(response.data.run_id).toBe('run-001');
    expect(requestMock).toHaveBeenCalledWith('/api/sync/start', {
      method: 'POST',
      data: { sync_type: 'full', forms: ['物料'] },
    });
  });

  it('停止请求必须指定 run_id', async () => {
    requestMock.mockResolvedValue({
      ok: true,
      data: { run_id: 'run-001', status: 'stopping' },
      error: '',
      code: '',
    });

    await stopSync('run-001');

    expect(requestMock).toHaveBeenCalledWith('/api/v1/sync/stop', {
      method: 'POST',
      params: { run_id: 'run-001' },
    });
  });

  it('日志请求按 run_id 隔离', async () => {
    requestMock.mockResolvedValue({
      ok: true,
      data: { run_id: 'run-001', logs: [] },
      error: '',
      code: '',
    });

    await getSyncLogs('run-001');

    expect(requestMock).toHaveBeenCalledWith('/api/sync/logs', {
      method: 'GET',
      params: { run_id: 'run-001' },
    });
  });
});
