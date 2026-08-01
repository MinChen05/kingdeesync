import { ClearOutlined, CopyOutlined } from '@ant-design/icons';
import { Button, Empty, Tooltip } from 'antd';
import React, { useEffect, useRef } from 'react';
import Panel from '@/components/Panel';
import type { V1RunEvent } from '@/services/v1';

interface SyncLogViewerProps {
  logs: V1RunEvent[];
  onClear: () => void;
}

/**
 * 实时日志查看器。
 */
const SyncLogViewer: React.FC<SyncLogViewerProps> = ({ logs, onClear }) => {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleCopy = () => {
    const text = logs
      .map(l => `${l.created_at} [${l.level}] ${l.form_name} ${l.message}`)
      .join('\n');
    navigator.clipboard?.writeText(text).catch(() => {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    });
  };

  return (
    <Panel
      title="实时日志"
      extra={
        logs.length > 0 && (
          <Button.Group size="small">
            <Tooltip title="复制">
              <Button icon={<CopyOutlined />} onClick={handleCopy} />
            </Tooltip>
            <Tooltip title="清空">
              <Button icon={<ClearOutlined />} onClick={onClear} />
            </Tooltip>
          </Button.Group>
        )
      }
    >
      <div
        className="h-64 overflow-y-auto rounded-md p-4 font-mono text-xs"
        style={{
          backgroundColor: '#020817',
          color: 'var(--tk-muted)',
          border: '1px solid rgba(148,163,184,0.08)',
        }}
      >
        {logs.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无日志"
            />
          </div>
        ) : (
          <div className="space-y-0.5">
            {logs.map((log) => (
              <div
                key={`${log.created_at}-${log.form_name}-${log.message}`}
                className="break-all leading-5"
              >
                <span style={{ color: 'var(--tk-unknown)' }}>
                  {log.created_at}
                </span>
                <span style={{ marginLeft: 8, color: '#cbd5e1' }}>
                  [{log.level}] {log.form_name} {log.message}
                </span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        )}
      </div>
    </Panel>
  );
};

export default SyncLogViewer;
