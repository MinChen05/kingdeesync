import { useQuery } from '@tanstack/react-query';
import { Typography } from 'antd';
import React from 'react';
import { DotIndicator } from '@/components/DotIndicator';
import { listRunEvents } from '@/services/v1';

const { Text } = Typography;

const LEVEL_TO_DOT: Record<string, 'ok' | 'error' | 'unknown'> = {
  ERROR: 'error',
  WARNING: 'unknown',
  INFO: 'ok',
};

const LEVEL_BAR_COLOR: Record<string, string> = {
  ERROR: 'var(--tk-error)',
  WARNING: 'var(--tk-warning)',
  INFO: 'var(--tk-success)',
};

interface RunTimelineProps {
  runId: string;
}

/**
 * 运行时间线：垂直展示同步事件，按时间排序。
 * 复用 RunErrorList 的色条 + DotIndicator 视觉模式。
 */
const RunTimeline: React.FC<RunTimelineProps> = ({ runId }) => {
  const { data: events, isPending } = useQuery({
    queryKey: ['v1', 'run-events', runId],
    queryFn: () => listRunEvents(runId),
    enabled: !!runId,
  });

  if (isPending) {
    return (
      <div
        style={{
          padding: '16px 20px',
          textAlign: 'center',
          color: 'var(--tk-dim)',
          fontSize: 13,
        }}
      >
        加载事件时间线...
      </div>
    );
  }

  if (!events || events.length === 0) {
    return null;
  }

  // Sort by created_at ascending
  const sorted = [...events].sort((a, b) =>
    a.created_at.localeCompare(b.created_at),
  );

  return (
    <div className="glass-card" style={{ padding: '16px 20px' }}>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: '#e2e8f0',
          marginBottom: 12,
        }}
      >
        事件时间线
        <Text
          style={{ fontWeight: 400, color: 'var(--tk-dim)', marginLeft: 8 }}
        >
          ({events.length} 条)
        </Text>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {sorted.map((event, index) => {
          const barColor = LEVEL_BAR_COLOR[event.level] || 'var(--tk-unknown)';
          const isLast = index === sorted.length - 1;
          const key = `${event.created_at}-${event.form_name}-${index}`;
          return (
            <div
              key={key}
              style={{
                display: 'flex',
                gap: 12,
                position: 'relative',
                paddingBottom: isLast ? 0 : 12,
              }}
            >
              {/* 时间线竖线 */}
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  width: 20,
                  flexShrink: 0,
                }}
              >
                <DotIndicator
                  type={LEVEL_TO_DOT[event.level] || 'unknown'}
                  size={8}
                />
                {!isLast && (
                  <div
                    style={{
                      flex: 1,
                      width: 2,
                      backgroundColor: 'rgba(100, 116, 139, 0.3)',
                      marginTop: 4,
                      minHeight: 8,
                    }}
                  />
                )}
              </div>
              {/* 事件内容 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginBottom: 2,
                  }}
                >
                  <span
                    style={{
                      borderLeft: `3px solid ${barColor}`,
                      paddingLeft: 8,
                      fontSize: 13,
                      fontWeight: 500,
                      color: '#e2e8f0',
                    }}
                  >
                    {event.form_name || '系统'}
                  </span>
                  <Text style={{ fontSize: 11, color: 'var(--tk-dim)' }}>
                    {formatEventTime(event.created_at)}
                  </Text>
                </div>
                <Text
                  style={{
                    fontSize: 12,
                    color: 'var(--tk-muted)',
                    display: 'block',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={event.message}
                >
                  {event.message}
                </Text>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

function formatEventTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export { RunTimeline };
