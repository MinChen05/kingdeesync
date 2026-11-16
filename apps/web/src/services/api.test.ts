import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from '@umijs/max';
import { stopSync } from './api';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const requestMock = vi.mocked(request);

describe('同步 API 契约', () => {
  beforeEach(() => {
    requestMock.mockReset();
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
});
