import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import * as v1 from '@/services/v1';
import { useOverviewData } from './hooks';

vi.mock('@/services/v1', async (importOriginal) => {
  const actual = await importOriginal<typeof v1>();
  return {
    ...actual,
    getOverview: vi.fn(),
    listDataSources: vi.fn(),
  };
});

const wrap =
  (queryClient: QueryClient) =>
  ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);

describe('useOverviewData', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.clearAllMocks();
  });

  it('返回 loading=true 当未加载时', () => {
    vi.mocked(v1.getOverview).mockResolvedValue({
      today: { sync_count: 0, success_rate: 0, fail_count: 0, avg_duration: 0, yesterday_sync_count: 0, yesterday_success_rate: 0 },
      health: { kingdee_api: { status: 'unknown' }, database: { status: 'unknown' }, scheduler: { status: 'unknown' }, log_service: { status: 'unknown' } },
      trend: [],
      risks: [],
      recent_runs: [],
    });
    vi.mocked(v1.listDataSources).mockResolvedValue([]);

    const { result } = renderHook(() => useOverviewData(), { wrapper: wrap(queryClient) });

    expect(result.current.today.loading).toBe(true);
  });

  it('加载后返回正确数据', async () => {
    vi.mocked(v1.getOverview).mockResolvedValue({
      today: { sync_count: 10, success_rate: 95, fail_count: 1, avg_duration: 30, yesterday_sync_count: 8, yesterday_success_rate: 90 },
      health: { kingdee_api: { status: 'ok' }, database: { status: 'ok' }, scheduler: { status: 'ok' }, log_service: { status: 'ok' } },
      trend: [{ date: '2024-01-01', sync_count: 5, records: 100, success_rate: 100 }],
      risks: [{ form_name: '物料', failure_count: 3, last_error: 'timeout' }],
      recent_runs: [{ run_id: 'r1', status: 'success', sync_type: 'incremental', started_at: '2024-01-01 10:00:00', duration_seconds: 30, total_records: 100, success_records: 99, failed_records: 1, form_count: 5, success_forms: 4, failed_forms: 1 }],
    });
    vi.mocked(v1.listDataSources).mockResolvedValue([{ id: '1', name: 'kingdee', type: 'api', status: 'ok' }]);

    const { result } = renderHook(() => useOverviewData(), { wrapper: wrap(queryClient) });

    await waitFor(() => expect(result.current.today.loading).toBe(false));

    expect(result.current.today.data.sync_count).toBe(10);
    expect(result.current.trend.data).toHaveLength(1);
    expect(result.current.topForms.data).toHaveLength(1);
    expect(result.current.topForms.data[0].form_name).toBe('物料');
    expect(result.current.recent.data).toHaveLength(1);
    expect(result.current.recent.data[0].run_id).toBe('r1');
  });
});
