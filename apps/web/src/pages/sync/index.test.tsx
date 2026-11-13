import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ApiProblemError } from '@/services/v1';
import { useSyncPage } from './hooks';
import SyncPage from './index';

vi.mock('./hooks', () => ({ useSyncPage: vi.fn() }));

// 子组件与本用例无关，替身暴露 onStart 以便直接驱动 handleStart 的错误分支
vi.mock('./components/LastSyncSummary', () => ({ default: () => null }));
vi.mock('./components/SyncProgressPanel', () => ({ default: () => null }));
vi.mock('./components/SyncLogViewer', () => ({ default: () => null }));
vi.mock('./components/SyncConfigPanel', () => ({
  default: ({
    onStart,
  }: {
    onStart: (mode: string, forms: string[]) => void;
  }) => (
    <button type="button" onClick={() => onStart('full', [])}>
      mock-start
    </button>
  ),
}));

type PageState = ReturnType<typeof useSyncPage>;

const basePageState: PageState = {
  forms: [],
  formsLoading: false,
  status: {
    run_id: '',
    status: 'idle',
    message: '',
    progress: 0,
    current_form: '',
    elapsed_seconds: 0,
    form_stats: [],
  },
  logs: [],
  logsLoading: false,
  lastRun: undefined,
  lastRunLoading: false,
  startSync: vi.fn(),
  stopSync: vi.fn(),
  starting: false,
  refreshLogs: vi.fn(),
};

const renderPage = (startSync: PageState['startSync']) => {
  vi.mocked(useSyncPage).mockReturnValue({ ...basePageState, startSync });
  // 真实 App 包装以启用 useApp() 的上下文 message（原因：antd 6 静态方法渲染到全局容器，断言不稳定）
  return render(
    <App>
      <SyncPage />
    </App>,
  );
};

const clickStart = async () => {
  fireEvent.click(screen.getByText('mock-start'));
};

describe('SyncPage 启动同步的 409 文案分支', () => {
  it('排队守卫拦截：提示服务端排队信息而非“已有任务在运行”', async () => {
    renderPage(() =>
      Promise.reject(
        new ApiProblemError(
          409,
          'TARGET_DB_GRANT_QUEUE_BUSY',
          '目标库内存授予排队 10m（阈值 1m），本轮跳过',
        ),
      ),
    );
    await clickStart();
    await waitFor(() => {
      expect(screen.getByText(/目标库内存授予排队 10m/)).toBeInTheDocument();
    });
    expect(screen.queryByText(/已有同步任务正在运行/)).not.toBeInTheDocument();
  });

  it('排队守卫拦截但服务端 message 为空：使用排队兜底文案', async () => {
    renderPage(() =>
      Promise.reject(
        new ApiProblemError(409, 'TARGET_DB_GRANT_QUEUE_BUSY', ''),
      ),
    );
    await clickStart();
    await waitFor(() => {
      expect(screen.getByText(/目标库内存授予排队拥堵/)).toBeInTheDocument();
    });
  });

  it('ALREADY_RUNNING：维持“已有任务在运行”文案', async () => {
    renderPage(() =>
      Promise.reject(new ApiProblemError(409, 'ALREADY_RUNNING', 'busy')),
    );
    await clickStart();
    await waitFor(() => {
      expect(
        screen.getByText('已有同步任务正在运行，请稍后再试'),
      ).toBeInTheDocument();
    });
  });

  it('非 409 错误仍走 errorMessage 通用错误提示', async () => {
    renderPage(() => Promise.reject(new Error('服务不可用')));
    await clickStart();
    await waitFor(() => {
      expect(screen.getByText('服务不可用')).toBeInTheDocument();
    });
  });
});
