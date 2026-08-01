import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import * as v1 from '@/services/v1';
import { useSchedule } from './hooks';

vi.mock('@/services/v1', async (importOriginal) => {
  const actual = await importOriginal<typeof v1>();
  return {
    ...actual,
    listSchedules: vi.fn(),
    startScheduler: vi.fn(),
    stopScheduler: vi.fn(),
    createSchedule: vi.fn(),
    updateSchedule: vi.fn(),
    deleteSchedule: vi.fn(),
  };
});

const wrap =
  (queryClient: QueryClient) =>
  ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);

describe('useSchedule', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.clearAllMocks();
  });

  it('返回 loading=true 当未加载时', () => {
    vi.mocked(v1.listSchedules).mockResolvedValue([]);

    const { result } = renderHook(() => useSchedule(), { wrapper: wrap(queryClient) });

    expect(result.current.loading).toBe(true);
  });

  it('加载后返回调度列表', async () => {
    const schedules = [{ id: 1, name: 'daily', cron_expr: '0 2 * * *', sync_type: 'incremental', forms: '', enabled: true }];
    vi.mocked(v1.listSchedules).mockResolvedValue(schedules);

    const { result } = renderHook(() => useSchedule(), { wrapper: wrap(queryClient) });

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.jobs).toHaveLength(1);
    expect(result.current.jobs[0].name).toBe('daily');
  });
});
