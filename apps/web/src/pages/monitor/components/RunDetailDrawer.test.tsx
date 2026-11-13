import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as v1 from '@/services/v1';
import RunDetailDrawer from './RunDetailDrawer';

vi.mock('@/services/v1', async (importOriginal) => {
  const actual = await importOriginal<typeof v1>();
  return {
    ...actual,
    getRun: vi.fn(),
    retryFailedForms: vi.fn(),
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
    <QueryClientProvider client={queryClient}>
      {/* antd 6 的 useApp() 需真实 App 包装才有 message 实例（原因：断言 toast 文案） */}
      <App>{children}</App>
    </QueryClientProvider>
  );
};

const mockOnClose = vi.fn();

/** partial 运行详情：failed_forms>0 使重试按钮渲染 */
const partialRun = {
  run_id: 'run-retry',
  status: 'partial' as const,
  sync_type: 'incremental' as const,
  started_at: '2026-11-12 20:00:00',
  finished_at: '2026-11-12 20:02:18',
  duration_seconds: 138,
  total_records: 419,
  success_records: 418,
  failed_records: 1,
  form_count: 21,
  success_forms: 20,
  failed_forms: 1,
};

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

describe('RunDetailDrawer 重试的 409 文案分支', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(v1.getRun).mockResolvedValue(partialRun);
  });

  /** 渲染抽屉并等待重试按钮出现，返回按钮元素 */
  const openWithRetryButton = async () => {
    render(<RunDetailDrawer runId="run-retry" onClose={mockOnClose} />, {
      wrapper: createWrapper(),
    });
    const btn = await screen.findByRole('button', {
      name: '重试 1 个失败表单',
    });
    return btn;
  };

  it('排队守卫拦截：提示服务端排队信息而非“任务正在运行”', async () => {
    const btn = await openWithRetryButton();
    vi.mocked(v1.retryFailedForms).mockRejectedValue(
      new v1.ApiProblemError(
        409,
        'TARGET_DB_GRANT_QUEUE_BUSY',
        '目标库内存授予排队 10m（阈值 1m），本轮跳过',
      ),
    );
    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.getByText(/目标库内存授予排队 10m/)).toBeInTheDocument();
    });
    expect(
      screen.queryByText(/请检查是否有同步任务正在运行/),
    ).not.toBeInTheDocument();
  });

  it('排队守卫拦截且 message 为空：走排队兜底文案', async () => {
    const btn = await openWithRetryButton();
    vi.mocked(v1.retryFailedForms).mockRejectedValue(
      new v1.ApiProblemError(409, 'TARGET_DB_GRANT_QUEUE_BUSY', ''),
    );
    fireEvent.click(btn);
    await waitFor(() => {
      expect(screen.getByText(/目标库内存授予排队拥堵/)).toBeInTheDocument();
    });
  });

  it('ALREADY_RUNNING：维持“检查是否有任务在运行”的原有文案', async () => {
    const btn = await openWithRetryButton();
    vi.mocked(v1.retryFailedForms).mockRejectedValue(
      new v1.ApiProblemError(409, 'ALREADY_RUNNING', 'busy'),
    );
    fireEvent.click(btn);
    await waitFor(() => {
      expect(
        screen.getByText('重试失败，请检查是否有同步任务正在运行'),
      ).toBeInTheDocument();
    });
  });
});
