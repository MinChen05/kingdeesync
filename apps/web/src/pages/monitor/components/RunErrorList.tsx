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

interface RunErrorListProps {
  errors: LogEntry[];
}

/** 运行错误列表 */
const RunErrorList: React.FC<RunErrorListProps> = ({ errors }) => {
  if (errors.length === 0) return null;

  return (
    <div>
      <Text strong className="mb-2 block">
        错误记录（{errors.length}）
      </Text>
      <div className="space-y-2">
        {errors.map((e) => (
          <div key={e.id} className="list-row">
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
                type="secondary"
                style={{ fontSize: 12, marginLeft: 'auto' }}
              >
                {e.created_at}
              </Text>
            </div>
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--tk-muted)' }}>
              {e.message}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export { RunErrorList };
