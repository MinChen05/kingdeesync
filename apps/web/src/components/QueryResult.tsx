import { Button, Empty, Spin, Typography } from 'antd';
import React from 'react';
import { ApiProblemError } from '@/services/v1';

const { Text } = Typography;

interface QueryResultProps {
  /** 查询状态 */
  status: 'pending' | 'error' | 'empty' | 'success';
  /** 错误对象（error 状态时使用） */
  error?: Error | ApiProblemError;
  /** 重试回调 */
  onRetry?: () => void;
  /** 空状态描述 */
  emptyDescription?: string;
  /** 成功时的渲染函数 */
  children: (data: unknown) => React.ReactNode;
  /** 实际数据（success 状态时传入） */
  data?: unknown;
}

/**
 * 统一查询状态组件：pending / error / empty / success 四态渲染。
 *
 * 用法：
 * ```tsx
 * <QueryResult status={req.status} error={req.error} onRetry={() => req.refetch()}>
 *   {(data) => <MyTable items={data} />}
 * </QueryResult>
 * ```
 */
const QueryResult: React.FC<QueryResultProps> = ({
  status,
  error,
  onRetry,
  emptyDescription = '暂无数据',
  children,
  data,
}) => {
  if (status === 'pending') {
    return <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />;
  }

  if (status === 'error') {
    const isApiError = error instanceof ApiProblemError;
    const message = isApiError
      ? error.message
      : error?.message || '请求失败';
    const code = isApiError ? error.code : undefined;

    return (
      <div style={{ textAlign: 'center', padding: '40px 20px' }}>
        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
          {code ? `[${code}] ` : ''}{message}
        </Text>
        {onRetry && (
          <Button type="primary" size="small" onClick={onRetry}>
            重试
          </Button>
        )}
      </div>
    );
  }

  if (status === 'empty') {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={emptyDescription}
      />
    );
  }

  // success
  return <>{children(data!)}</>;
};

export { QueryResult };
export type { QueryResultProps };
export default QueryResult;
