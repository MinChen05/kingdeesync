import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import RunDetailDrawer from './RunDetailDrawer';
import * as v1 from '@/services/v1';

vi.mock('@/services/v1', async (importOriginal) => {
  const actual = await importOriginal<typeof v1>();
  return {
    ...actual,
    getRun: vi.fn(),
  };
});

/**
 * 每个用例使用独立 QueryClient，避免缓存串扰；
 * 关闭 retry 让失败用例快速落定。
 */
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const mockOnClose = vi.fn();

describe('RunDetailDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('当 runId 为 null 时不显示内容', () => {
    render(<RunDetailDrawer runId={null} onClose={mockOnClose} />, {
      wrapper: createWrapper(),
    });
    expect(screen.queryByText('运行详情')).not.toBeInTheDocument();
  });

  it('调用 getRun 获取数据', async () => {
    vi.mocked(v1.getRun).mockResolvedValue({
      run_id: 'run-001',
      status: 'success',
      sync_type: 'incremental',
      started_at: '2026-07-27 01:00:00',
      finished_at: '2026-07-27 01:05:30',
      duration_seconds: 330,
      total_records: 1000,
      success_records: 998,
      failed_records: 2,
      form_count: 5,
      success_forms: 5,
      failed_forms: 0,
    });

    render(<RunDetailDrawer runId="run-001" onClose={mockOnClose} />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(v1.getRun).toHaveBeenCalledWith('run-001');
    });
  });

  it('当无数据且非 loading 时显示空状态', async () => {
    vi.mocked(v1.getRun).mockRejectedValue(new Error('not found'));

    render(<RunDetailDrawer runId="run-001" onClose={mockOnClose} />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByText('未找到运行详情')).toBeInTheDocument();
    });
  });
});
