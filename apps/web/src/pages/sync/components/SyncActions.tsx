import {
  PlayCircleOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Button } from 'antd';
import React from 'react';
import type { SyncMode } from '../types';

interface SyncActionsProps {
  mode: SyncMode;
  selectedForms: string[];
  isRunning: boolean;
  onStart: () => void;
  onStop: () => void;
  onQuickSync: () => void;
}

const MODE_LABELS: Record<SyncMode, string> = {
  incremental: '增量',
  full: '全量',
  reset: '重置',
};

/** 同步操作按钮组 */
const SyncActions: React.FC<SyncActionsProps> = ({
  mode,
  selectedForms,
  isRunning,
  onStart,
  onStop,
  onQuickSync,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          size="large"
          disabled={isRunning}
          onClick={onStart}
          className="flex-1"
        >
          {isRunning ? '同步中...' : '启动同步'}
        </Button>
        <Button
          danger
          icon={<StopOutlined />}
          size="large"
          disabled={!isRunning}
          onClick={onStop}
        >
          停止
        </Button>
      </div>
      <Button
        icon={<ThunderboltOutlined />}
        disabled={isRunning}
        onClick={onQuickSync}
        style={{
          width: '100%',
          backgroundColor: '#0f172a',
          borderColor: 'var(--tk-primary)',
          color: 'var(--tk-primary)',
        }}
      >
        快速同步（
        {MODE_LABELS[mode]}
        {selectedForms.length > 0
          ? ` · ${selectedForms.length}个表单`
          : ' · 全部表单'}
        ）
      </Button>
    </div>
  );
};

export { SyncActions };
