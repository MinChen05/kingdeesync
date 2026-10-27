import { useQuery } from '@tanstack/react-query';
import { Typography } from 'antd';
import React from 'react';
import { listRunEvents } from '@/services/v1';

const { Text } = Typography;

const LEVEL_META: Record<string, { label: string; tone: string }> = {
  ERROR: { label: '错误', tone: 'error' },
  WARNING: { label: '警告', tone: 'warning' },
  INFO: { label: '信息', tone: 'success' },
};

interface RunTimelineProps {
  runId: string;
}

const RunTimeline: React.FC<RunTimelineProps> = ({ runId }) => {
  const { data: events, isPending } = useQuery({
    queryKey: ['v1', 'run-events', runId],
    queryFn: () => listRunEvents(runId),
    enabled: !!runId,
  });

  if (isPending) {
    return (
      <div className="monitor-timeline-loading" role="status">
        加载事件时间线...
      </div>
    );
  }

  if (!events || events.length === 0) {
    return null;
  }

  const sorted = [...events].sort((a, b) =>
    a.created_at.localeCompare(b.created_at),
  );

  return (
    <section className="monitor-timeline" aria-labelledby={`timeline-${runId}`}>
      <div className="monitor-section-heading">
        <Text strong id={`timeline-${runId}`}>
          事件时间线
        </Text>
        <span className="monitor-count-badge">{events.length} 条</span>
      </div>
      <ol className="monitor-timeline__list">
        {sorted.map((event, index) => {
          const meta = LEVEL_META[event.level] || {
            label: event.level,
            tone: 'neutral',
          };
          const key = `${event.created_at}-${event.form_name}-${index}`;
          return (
            <li
              className={`monitor-timeline__item monitor-timeline__item--${meta.tone}`}
              key={key}
            >
              <div className="monitor-timeline__rail" aria-hidden="true">
                <span className="monitor-timeline__dot" />
              </div>
              <div className="monitor-timeline__content">
                <div className="monitor-timeline__heading">
                  <span className="monitor-timeline__form">
                    {event.form_name || '系统'}
                  </span>
                  <span className="monitor-timeline__level">{meta.label}</span>
                  <time
                    className="monitor-timeline__time"
                    dateTime={event.created_at}
                  >
                    {formatEventTime(event.created_at)}
                  </time>
                </div>
                <div
                  className="monitor-timeline__message"
                  title={event.message}
                >
                  {event.message}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
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
