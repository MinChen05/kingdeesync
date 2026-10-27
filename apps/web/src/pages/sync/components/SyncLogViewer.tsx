import {
  ArrowDownOutlined,
  ClearOutlined,
  CopyOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { App, Button, Tooltip } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import Panel from '@/components/Panel';
import type { V1RunEvent } from '@/services/v1';

interface SyncLogViewerProps {
  logs: V1RunEvent[];
  onClear: () => void;
}

const SyncLogViewer: React.FC<SyncLogViewerProps> = ({ logs, onClear }) => {
  const { message } = App.useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);

  useEffect(() => {
    if (following && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, following]);

  const handleCopy = async () => {
    const text = logs
      .map(
        (log) =>
          `${log.created_at} [${log.level}] ${log.form_name} ${log.message}`,
      )
      .join('\n');
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      message.success('日志已复制');
    } catch {
      message.error('复制失败，请手动选择日志内容');
    }
  };

  const scrollToLatest = () => {
    setFollowing(true);
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  return (
    <Panel
      title="运行日志"
      extra={
        <div className="sync-log-actions">
          <span>{logs.length} 条</span>
          <Button.Group size="small">
            <Tooltip title="复制全部日志">
              <Button
                aria-label="复制全部日志"
                icon={<CopyOutlined />}
                disabled={logs.length === 0}
                onClick={handleCopy}
              />
            </Tooltip>
            <Tooltip title="清空当前视图">
              <Button
                aria-label="清空当前日志视图"
                icon={<ClearOutlined />}
                disabled={logs.length === 0}
                onClick={() => {
                  setFollowing(true);
                  onClear();
                }}
              />
            </Tooltip>
          </Button.Group>
        </div>
      }
    >
      <div className="sync-log-shell">
        <div className="sync-log-toolbar">
          <span>
            <span
              className={`sync-log-live-dot${following ? ' is-active' : ''}`}
            />
            {following ? '自动跟随最新日志' : '已暂停自动跟随'}
          </span>
          <span>按时间正序</span>
        </div>
        <div
          ref={containerRef}
          className="sync-log-list"
          role="log"
          aria-label="同步运行日志"
          onScroll={(event) => {
            const element = event.currentTarget;
            const distanceToBottom =
              element.scrollHeight - element.scrollTop - element.clientHeight;
            setFollowing(distanceToBottom < 24);
          }}
        >
          {logs.length === 0 ? (
            <div className="sync-log-empty">
              <FileTextOutlined />
              <strong>暂无运行日志</strong>
              <span>任务启动后，执行事件将在这里按时间显示</span>
            </div>
          ) : (
            logs.map((log) => {
              const level = log.level.toLowerCase();
              const tone = ['error', 'warn', 'warning'].includes(level)
                ? level === 'error'
                  ? 'error'
                  : 'warning'
                : level === 'info'
                  ? 'info'
                  : 'neutral';
              return (
                <div
                  key={`${log.created_at}-${log.form_name}-${log.message}`}
                  className={`sync-log-entry is-${tone}`}
                >
                  <time>{log.created_at}</time>
                  <span className="sync-log-level">{log.level}</span>
                  <span className="sync-log-form">
                    {log.form_name || '系统'}
                  </span>
                  <span className="sync-log-message">{log.message}</span>
                </div>
              );
            })
          )}
        </div>
        {!following && logs.length > 0 && (
          <Button
            size="small"
            icon={<ArrowDownOutlined />}
            className="sync-log-latest"
            onClick={scrollToLatest}
          >
            回到最新
          </Button>
        )}
      </div>
    </Panel>
  );
};

export default SyncLogViewer;
