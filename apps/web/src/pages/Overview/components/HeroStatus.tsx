import {
  CheckCircleFilled,
  DatabaseOutlined,
  PlayCircleOutlined,
  SyncOutlined,
  WarningFilled,
} from '@ant-design/icons';
import { App, Button, Progress } from 'antd';
import React, { useState } from 'react';
import { createRun } from '@/services/v1';
import { formatDuration } from '@/utils/format';
import type { SyncStatusInfo, TodayStats } from '../hooks';

interface HeroStatusProps {
  today: TodayStats;
  status: SyncStatusInfo;
  onSynced: () => void;
}

type HeroState = 'syncing' | 'healthy' | 'warning';

const STATE_META: Record<
  HeroState,
  { label: string; desc: string; icon: React.ReactNode }
> = {
  syncing: {
    label: '正在同步数据',
    desc: '数据正从金蝶云星空写入 SQL Server，请稍候',
    icon: <SyncOutlined spin />,
  },
  healthy: {
    label: '同步服务运行正常',
    desc: '数据链路连接稳定，所有同步服务均已就绪',
    icon: <CheckCircleFilled />,
  },
  warning: {
    label: '发现需要关注的异常',
    desc: '今日存在失败运行，建议前往监控分析查看详情',
    icon: <WarningFilled />,
  },
};

const HeroStatus: React.FC<HeroStatusProps> = ({ today, status, onSynced }) => {
  const { message } = App.useApp();
  const [starting, setStarting] = useState(false);

  const state: HeroState =
    status.status === 'running'
      ? 'syncing'
      : (today.fail_count || 0) > 0
        ? 'warning'
        : 'healthy';
  const meta = STATE_META[state];

  const handleStart = async () => {
    setStarting(true);
    try {
      await createRun({ sync_type: 'incremental' });
      message.success('同步已启动');
      onSynced();
    } catch {
      message.error('启动同步失败');
    } finally {
      setStarting(false);
    }
  };

  return (
    <section className={`overview-hero overview-hero--${state}`}>
      <div className="overview-hero-copy">
        <div className="overview-hero-kicker">
          <span className="status-pulse" />
          同步服务实时状态
        </div>
        <div className="overview-hero-title">
          <span>{meta.icon}</span>
          {meta.label}
        </div>
        <p className="overview-hero-description">{meta.desc}</p>
        <div className="overview-hero-meta">
          <span>上次同步</span>
          <strong>{today.last_sync_time || '暂无记录'}</strong>
        </div>
      </div>

      <div className="overview-hero-action">
        {state === 'syncing' ? (
          <div>
            <div className="hero-progress-label">
              <span>
                <DatabaseOutlined style={{ marginRight: 7 }} />
                {status.current_form || '正在初始化同步运行'}
              </span>
              <strong>
                {status.progress || 0}% ·{' '}
                {formatDuration(status.elapsed_seconds || 0)}
              </strong>
            </div>
            <Progress
              percent={status.progress || 0}
              showInfo={false}
              strokeColor="var(--tk-hero-accent)"
              trailColor="rgba(255,255,255,0.14)"
            />
          </div>
        ) : (
          <Button
            size="large"
            icon={<PlayCircleOutlined />}
            loading={starting}
            onClick={handleStart}
            block
          >
            立即增量同步
          </Button>
        )}
      </div>
    </section>
  );
};

export default HeroStatus;
