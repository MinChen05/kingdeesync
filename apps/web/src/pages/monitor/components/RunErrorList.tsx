import { Typography } from 'antd';
import React from 'react';
import { DotIndicator } from '@/components/DotIndicator';
import type { LogEntry } from '../types';

const { Text } = Typography;

const LEVEL_TO_DOT: Record<string, 'ok' | 'error' | 'unknown'> = {
  ERROR: 'error',
  WARNING: 'unknown',
  INFO: 'ok',
};

/** 错误级别 → 左侧色条 */
const LEVEL_BAR_COLOR: Record<string, string> = {
  ERROR: 'var(--tk-error)',
  WARNING: 'var(--tk-warning)',
  INFO: 'var(--tk-success)',
};

interface RunErrorListProps {
  errors: LogEntry[];
}

/** 运行错误列表：卡片化条目（左侧色条 + 表单名 + 消息 + 时间） */
const RunErrorList: React.FC<RunErrorListProps> = ({ errors }) => {
  if (errors.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 12px',
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--tk-success)',
          background: 'rgba(52, 211, 153, 0.06)',
          border: '1px solid rgba(52, 211, 153, 0.15)',
        }}
      >
        <DotIndicator level="ok" />
        本次运行无错误记录
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <Text strong style={{ color: 'var(--tk-text)' }}>
          错误记录
        </Text>
        <span
          style={{
            fontSize: 11,
            color: 'var(--tk-error)',
            background: 'rgba(248, 113, 113, 0.1)',
            border: '1px solid rgba(248, 113, 113, 0.2)',
            borderRadius: 999,
            padding: '1px 10px',
          }}
        >
          {errors.length} 条
        </span>
      </div>
      <div className="space-y-2">
        {errors.map((e, i) => (
          <div
            key={e.id ?? i}
            className="list-row"
            style={{
              borderLeft: `3px solid ${LEVEL_BAR_COLOR[e.level] || 'var(--tk-dim)'}`,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 13,
              }}
            >
              <DotIndicator level={LEVEL_TO_DOT[e.level] || 'unknown'} />
              <Text strong style={{ color: 'var(--tk-text)', fontSize: 13 }}>
                {e.form_name}
              </Text>
              <Text
                style={{
                  fontSize: 11,
                  color: 'var(--tk-muted)',
                  marginLeft: 'auto',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {e.created_at}
              </Text>
            </div>
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--tk-muted)', whiteSpace: 'pre-wrap' }}>
              {e.message}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export { RunErrorList };
