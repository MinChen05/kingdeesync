import { CheckCircleOutlined } from '@ant-design/icons';
import { Typography } from 'antd';
import React from 'react';
import type { LogEntry } from '../types';

const { Text } = Typography;

const LEVEL_META: Record<string, { label: string; tone: string }> = {
  ERROR: { label: '错误', tone: 'error' },
  WARNING: { label: '警告', tone: 'warning' },
  INFO: { label: '信息', tone: 'success' },
};

interface RunErrorListProps {
  errors: LogEntry[];
}

const RunErrorList: React.FC<RunErrorListProps> = ({ errors }) => {
  if (errors.length === 0) {
    return (
      <div className="monitor-no-errors" role="status">
        <CheckCircleOutlined aria-hidden="true" />
        本次运行无错误记录
      </div>
    );
  }

  return (
    <section className="monitor-errors" aria-label="运行错误记录">
      <div className="monitor-section-heading">
        <Text strong>错误记录</Text>
        <span className="monitor-count-badge monitor-count-badge--error">
          {errors.length} 条
        </span>
      </div>
      <div className="monitor-errors__list">
        {errors.map((error, index) => {
          const meta = LEVEL_META[error.level] || {
            label: error.level,
            tone: 'neutral',
          };
          return (
            <article
              key={error.id ?? index}
              className={`monitor-error-item monitor-error-item--${meta.tone}`}
            >
              <div className="monitor-error-item__heading">
                <span className="monitor-error-item__dot" aria-hidden="true" />
                <Text strong>{error.form_name || '系统'}</Text>
                <span className="monitor-error-item__level">{meta.label}</span>
                <time
                  className="monitor-error-item__time"
                  dateTime={error.created_at}
                >
                  {error.created_at}
                </time>
              </div>
              <div className="monitor-error-item__message">{error.message}</div>
              {error.detail && (
                <div className="monitor-error-item__detail">{error.detail}</div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
};

export { RunErrorList };
