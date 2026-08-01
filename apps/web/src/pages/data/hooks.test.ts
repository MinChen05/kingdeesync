import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import * as v1 from '@/services/v1';
import { useDataPage } from './hooks';

vi.mock('@/services/v1', async (importOriginal) => {
  const actual = await importOriginal<typeof v1>();
  return {
    ...actual,
    listForms: vi.fn(),
    getDiagnostics: vi.fn(),
  };
});

const wrap =
  (queryClient: QueryClient) =>
  ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);

describe('useDataPage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.clearAllMocks();
  });

  it('加载后返回表单列表和诊断信息', async () => {
    vi.mocked(v1.listForms).mockResolvedValue([
      { form_name: '物料', enabled: true, record_count: 100, error_count: 0 },
      { form_name: '供应商', enabled: false, record_count: 50, error_count: 2 },
    ]);
    vi.mocked(v1.getDiagnostics).mockResolvedValue({
      kingdee_api: { status: 'ok' },
      database: { status: 'ok' },
      scheduler: { status: 'ok' },
      log_service: { status: 'ok' },
    });

    const { result } = renderHook(() => useDataPage(), { wrapper: wrap(queryClient) });

    await waitFor(() => expect(result.current.formsLoading).toBe(false));

    expect(result.current.allForms).toHaveLength(2);
    expect(result.current.allForms[0].form_name).toBe('物料');
    expect(result.current.allForms[0].enabled).toBe(true);
    expect(result.current.diagInfo.kingdee_api?.status).toBe('ok');
    expect(result.current.statsMap.size).toBe(2);
  });
});
