import {
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { Button } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';

interface SchedulerControlProps {
  enabled: boolean;
  jobCount: number;
  enabledCount: number;
  onStart: () => void;
  onStop: () => void;
  starting: boolean;
  stopping: boolean;
}

const SchedulerControl: React.FC<SchedulerControlProps> = ({
  enabled,
  jobCount,
  enabledCount,
  onStart,
  onStop,
  starting,
  stopping,
}) => {
  return (
    <Panel
      title="调度器状态"
      extra={
        enabled ? (
          <Button
            danger
            icon={<StopOutlined />}
            loading={stopping}
            disabled={starting}
            onClick={onStop}
          >
            停止调度
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={starting}
            disabled={stopping}
            onClick={onStart}
          >
            启动调度
          </Button>
        )
      }
    >
      <div className="scheduler-control-content">
        <div className="scheduler-state">
          <span
            className={`scheduler-state-icon${enabled ? ' is-running' : ' is-stopped'}`}
          >
            {enabled ? <CheckCircleOutlined /> : <PauseCircleOutlined />}
          </span>
          <div>
            <div className="scheduler-state-title">
              <strong>{enabled ? '自动调度运行中' : '自动调度已停止'}</strong>
              <span
                className={`scheduler-state-badge${enabled ? ' is-running' : ''}`}
              >
                <span />
                {enabled ? '运行中' : '待机'}
              </span>
            </div>
            <p>
              {enabled
                ? '系统将按照任务计划自动执行，启用中的任务会按时触发'
                : '所有定时触发均已暂停，已有任务配置会继续保留'}
            </p>
          </div>
        </div>
        <div className="scheduler-metrics">
          <div>
            <CalendarOutlined />
            <span>全部任务</span>
            <strong>{jobCount}</strong>
          </div>
          <div>
            <CheckCircleOutlined />
            <span>已启用</span>
            <strong>{enabledCount}</strong>
          </div>
          <div>
            <ClockCircleOutlined />
            <span>已停用</span>
            <strong>{jobCount - enabledCount}</strong>
          </div>
        </div>
      </div>
    </Panel>
  );
};

export default SchedulerControl;
