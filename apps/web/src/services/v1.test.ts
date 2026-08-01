import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from '@umijs/max';
import {
  getOverview,
  listRuns,
  getRun,
  listSchedules,
  createSchedule,
  ApiProblemError,
} from './v1';

vi.mock('@umijs/max', () => ({
  request: vi.fn(),
}));

const requestMock = vi.mocked(request);

describe('v1 客户端', () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it('getOverview 请求 /api/v1/overview 并解包 data', async () => {
    requestMock.mockResolvedValue({
      data: {
        today: { sync_count: 5 },
        health: { kingdee_api: { status: 'ok' } },
        trend: [],
        risks: [],
        recent_runs: [],
      },
    });

    const result = await getOverview();
    expect(result.today.sync_count).toBe(5);
    expect(requestMock).toHaveBeenCalledWith('/api/v1/overview', { method: 'GET' });
  });

  it('listRuns 请求 /api/v1/runs 并返回 data + meta', async () => {
    requestMock.mockResolvedValue({
      data: [{ run_id: 'r1', status: 'success' }],
      meta: { page: 1, page_size: 10, total: 1 },
    });

    const result = await listRuns({ status: 'success' });
    expect(result.data).toHaveLength(1);
    expect(result.data[0].run_id).toBe('r1');
    expect(result.meta.total).toBe(1);
    expect(requestMock).toHaveBeenCalledWith('/api/v1/runs', {
      method: 'GET',
      params: { status: 'success' },
    });
  });

  it('getRun 请求 /api/v1/runs/:runId', async () => {
    requestMock.mockResolvedValue({
      data: { run_id: 'r1', status: 'running' },
    });

    const result = await getRun('r1');
    expect(result.run_id).toBe('r1');
  });

  it('listSchedules 返回调度列表', async () => {
    requestMock.mockResolvedValue({
      data: [{ id: 1, name: 'test', cron_expr: '0 * * * *', sync_type: 'incremental', forms: '', enabled: true }],
    });

    const result = await listSchedules();
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('test');
  });

  it('createSchedule 发送 POST 并返回创建的调度', async () => {
    requestMock.mockResolvedValue({
      data: { id: 2, name: 'new-job', cron_expr: '0 */20 * * * *', sync_type: 'full', forms: '', enabled: true },
    });

    const result = await createSchedule({
      name: 'new-job',
      cron_expr: '0 */20 * * * *',
      sync_type: 'full',
    });
    expect(result.id).toBe(2);
    expect(requestMock).toHaveBeenCalledWith('/api/v1/schedules', {
      method: 'POST',
      data: { name: 'new-job', cron_expr: '0 */20 * * * *', sync_type: 'full' },
    });
  });

  it('将 409 problem 转换为 ApiProblemError', async () => {
    requestMock.mockResolvedValue({
      error: {
        code: 'RUN_ALREADY_ACTIVE',
        message: '同步任务正在运行',
      },
    });

    await expect(listRuns()).rejects.toThrow(ApiProblemError);
    await expect(listRuns()).rejects.toMatchObject({
      code: 'RUN_ALREADY_ACTIVE',
      message: '同步任务正在运行',
    });
  });

  it('ApiProblemError 继承自 Error', () => {
    const err = new ApiProblemError(500, 'INTERNAL', 'something broke');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiProblemError);
    expect(err.status).toBe(500);
    expect(err.code).toBe('INTERNAL');
    expect(err.message).toBe('something broke');
  });
});
