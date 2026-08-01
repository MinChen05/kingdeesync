import { Radio, Space, Typography } from 'antd';
import React from 'react';
import type { SyncMode } from '../types';

const { Text } = Typography;

interface ModeSelectorProps {
  mode: SyncMode;
  onChange: (mode: SyncMode) => void;
  disabled?: boolean;
}

const MODE_DESCRIPTIONS: Record<SyncMode, string> = {
  incremental: '仅同步自上次以来的变更数据',
  full: '全量拉取并合并数据',
  reset: '清空后全量拉取（耗时较长）',
};

/** 同步模式选择器 */
const ModeSelector: React.FC<ModeSelectorProps> = ({
  mode,
  onChange,
  disabled,
}) => {
  return (
    <div>
      <Text strong className="mb-2 block">
        同步模式
      </Text>
      <Radio.Group
        value={mode}
        onChange={(e) => onChange(e.target.value)}
        buttonStyle="solid"
        disabled={disabled}
        className="w-full"
      >
        <Space size="middle">
          {(['incremental', 'full', 'reset'] as SyncMode[]).map((m) => (
            <Radio.Button key={m} value={m}>
              {m === 'incremental' ? '增量' : m === 'full' ? '全量' : '重置'}
            </Radio.Button>
          ))}
        </Space>
      </Radio.Group>
      <div style={{ fontSize: 12, color: 'var(--tk-dim)', marginTop: 6 }}>
        {MODE_DESCRIPTIONS[mode]}
      </div>
    </div>
  );
};

export { ModeSelector };
