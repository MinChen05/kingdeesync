import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryResult } from './QueryResult';
import { ApiProblemError } from '@/services/v1';

describe('QueryResult', () => {
  it('pending 状态显示 Spin', () => {
    const { container } = render(
      <QueryResult status="pending">{() => null}</QueryResult>,
    );
    // Spin renders an ant-spin class
    expect(container.querySelector('.ant-spin')).toBeInTheDocument();
  });

  it('error 状态显示错误信息和重试按钮', () => {
    const retry = vi.fn();
    const { container } = render(
      <QueryResult
        status="error"
        error={new Error('连接超时')}
        onRetry={retry}
      >
        {() => null}
      </QueryResult>,
    );
    expect(container.textContent).toContain('连接超时');
    expect(container.querySelector('button')).not.toBeNull();
  });

  it('ApiProblemError 显示 code 和 message', () => {
    render(
      <QueryResult
        status="error"
        error={new ApiProblemError(503, 'UNAVAILABLE', '服务不可用')}
      >
        {() => null}
      </QueryResult>,
    );
    expect(screen.getByText('[UNAVAILABLE] 服务不可用')).toBeInTheDocument();
  });

  it('empty 状态显示空描述', () => {
    render(
      <QueryResult status="empty" emptyDescription="暂无同步记录">
        {() => null}
      </QueryResult>,
    );
    expect(screen.getByText('暂无同步记录')).toBeInTheDocument();
  });

  it('empty 状态使用默认描述', () => {
    render(<QueryResult status="empty">{() => null}</QueryResult>);
    expect(screen.getByText('暂无数据')).toBeInTheDocument();
  });

  it('success 状态渲染 children', () => {
    render(
      <QueryResult status="success" data={{ items: [1, 2] }}>
        {() => <div data-testid="content">渲染成功</div>}
      </QueryResult>,
    );
    expect(screen.getByText('渲染成功')).toBeInTheDocument();
  });

  it('没有 onRetry 时不显示重试按钮', () => {
    render(
      <QueryResult status="error" error={new Error('fail')}>
        {() => null}
      </QueryResult>,
    );
    expect(screen.queryByText('重试')).not.toBeInTheDocument();
  });
});
