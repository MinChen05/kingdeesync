import {
  CheckCircleFilled,
  DatabaseOutlined,
  RocketOutlined,
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
  /** 启动同步成功后触发数据刷新 */
  onSynced: () => void;
}

type HeroState = 'syncing' | 'healthy' | 'warning';

const STATE_META: Record<
  HeroState,
  { color: string; label: string; desc: string; icon: React.ReactNode }
> = {
  syncing: {
    color: 'var(--tk-primary)',
    label: '同步进行中',
    desc: '正在从金蝶云星空拉取数据并写入 Doris',
    icon: <SyncOutlined spin />,
  },
  healthy: {
    color: 'var(--tk-success)',
    label: '系统运行正常',
    desc: '各服务连接正常，数据同步就绪',
    icon: <CheckCircleFilled />,
  },
  warning: {
    color: 'var(--tk-warning)',
    label: '存在同步异常',
    desc: '今日出现失败任务，建议检查异常表单',
    icon: <WarningFilled />,
  },
};

/**
 * Hero 状态区：概览页第一视觉层级。
 * 用脉冲指示灯 + 状态文案让用户一眼判断系统好坏，右侧承载主操作（立即同步）或实时进度。
 */
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
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 24,
        flexWrap: 'wrap',
        padding: '26px 28px',
        borderRadius: 14,
        border: '1px solid rgba(148,163,184,0.14)',
        background: `linear-gradient(120deg, ${meta.color}14 0%, rgba(148,163,184,0.05) 45%, rgba(148,163,184,0.03) 100%)`,
        boxShadow:
          'inset 0 1px 0 rgba(255,255,255,0.04), 0 4px 20px rgba(2,6,23,0.35)',
        overflow: 'hidden',
      }}
    >
      {/* 状态光晕 */}
      <div
        style={{
          position: 'absolute',
          left: -40,
          top: -70,
          width: 240,
          height: 240,
          borderRadius: '50%',
          background: `radial-gradient(circle, ${meta.color}22 0%, transparent 70%)`,
          pointerEvents: 'none',
        }}
      />

      {/* 左侧：脉冲指示 + 状态文案 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          position: 'relative',
        }}
      >
        <span
          className="status-pulse"
          style={{ backgroundColor: meta.color, color: meta.color }}
        />
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 22,
              fontWeight: 700,
              color: '#f1f5f9',
            }}
          >
            <span style={{ color: meta.color, fontSize: 20 }}>{meta.icon}</span>
            {meta.label}
          </div>
          <div style={{ marginTop: 4, color: 'var(--tk-muted)', fontSize: 13 }}>
            {meta.desc} · 上次同步 {today.last_sync_time || '-'}
          </div>
        </div>
      </div>

      {/* 右侧：实时进度 或 主操作 */}
      {state === 'syncing' ? (
        <div style={{ minWidth: 300, flex: '0 1 360px', position: 'relative' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: 6,
              fontSize: 13,
            }}
          >
            <span style={{ color: 'var(--tk-text)' }}>
              <DatabaseOutlined style={{ color: meta.color, marginRight: 6 }} />
              {status.current_form || '初始化中...'}
            </span>
            <span style={{ color: 'var(--tk-muted)' }}>
              {status.progress || 0}% ·{' '}
              {formatDuration(status.elapsed_seconds || 0)}
            </span>
          </div>
          <Progress
            percent={status.progress || 0}
            showInfo={false}
            strokeColor={meta.color}
            trailColor="rgba(148,163,184,0.15)"
          />
        </div>
      ) : (
        <Button
          type="primary"
          size="large"
          icon={<RocketOutlined />}
          loading={starting}
          onClick={handleStart}
          style={{ position: 'relative' }}
        >
          立即同步
        </Button>
      )}
    </div>
  );
};

export default HeroStatus;
