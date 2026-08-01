import {
  ClockCircleOutlined,
  PlayCircleOutlined,
  ScheduleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { Button } from 'antd';
import React from 'react';

interface SchedulerControlProps {
  enabled: boolean;
  jobCount: number;
  enabledCount: number;
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
  starting: boolean;
  pausing: boolean;
  stopping: boolean;
}

/**
 * 调度器状态卡片：状态指示 + 统计指标 + 控制按钮
 */
const SchedulerControl: React.FC<SchedulerControlProps> = ({
  enabled,
  jobCount,
  enabledCount,
  onStart,
  onPause,
  onStop,
  starting,
  pausing,
  stopping,
}) => {
  const dotColor = enabled ? '#22c55e' : '#f59e0b';

  return (
    <div className="glass-card" style={{ padding: '20px 24px' }}>
      <div className="flex items-center justify-between" style={{ flexWrap: 'wrap', gap: 16 }}>
        {/* 左侧：状态 + 指标 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 32, flexWrap: 'wrap' }}>
          {/* 状态指示 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              className="rounded-full"
              style={{
                width: 10,
                height: 10,
                backgroundColor: dotColor,
                boxShadow: `0 0 8px ${dotColor}, 0 0 16px ${dotColor}55`,
              }}
            />
            <span style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0' }}>
              {enabled ? '调度器运行中' : '调度器已停止'}
            </span>
          </div>

          {/* 指标 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ScheduleOutlined style={{ fontSize: 14, color: 'var(--tk-dim)' }} />
              <span style={{ fontSize: 13, color: 'var(--tk-dim)' }}>
                全部 <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{jobCount}</span>
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ClockCircleOutlined style={{ fontSize: 14, color: 'var(--tk-dim)' }} />
              <span style={{ fontSize: 13, color: 'var(--tk-dim)' }}>
                启用 <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{enabledCount}</span>
              </span>
            </div>
          </div>
        </div>

        {/* 右侧：操作按钮 */}
        <div style={{ display: 'flex', gap: 8 }}>
          {enabled ? (
            <>
              <Button
                size="small"
                loading={pausing}
                onClick={onPause}
                style={{
                  backgroundColor: 'rgba(148,163,184,0.08)',
                  borderColor: 'rgba(148,163,184,0.15)',
                  color: '#cbd5e1',
                }}
              >
                暂停
              </Button>
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                loading={stopping}
                onClick={onStop}
              >
                停止
              </Button>
            </>
          ) : (
            <Button
              type="primary"
              size="small"
              icon={<PlayCircleOutlined />}
              loading={starting}
              onClick={onStart}
            >
              启动调度
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SchedulerControl;
