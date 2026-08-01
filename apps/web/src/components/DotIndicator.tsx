import React from 'react';
import type { HealthLevel } from '@/pages/Overview/types';

interface DotIndicatorProps {
  /** 状态等级 */
  level: HealthLevel;
  /** 自定义尺寸（默认 8px） */
  size?: number;
}

const COLORS = {
  ok: 'var(--tk-success)',
  error: 'var(--tk-error)',
  unknown: 'var(--tk-unknown)',
} as const;

const LABELS = {
  ok: '正常',
  error: '异常',
  unknown: '未知',
} as const;

/**
 * 发光状态指示灯：根据 HealthLevel 展示颜色与光晕。
 * 用在 HealthGrid 等需要快速识别服务状态的场景。
 */
const DotIndicator: React.FC<DotIndicatorProps> = ({
  level,
  size = 8,
}) => {
  const color = COLORS[level];
  const isUnknown = level === 'unknown';

  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow: isUnknown ? 'none' : `0 0 8px ${color}`,
        flexShrink: 0,
        display: 'inline-block',
      }}
      data-testid={`dot-indicator-${level}`}
    >
      <span className="sr-only">{LABELS[level]}</span>
    </span>
  );
};

export { DotIndicator };
export type { DotIndicatorProps };
export { LABELS as dotLabels };
export default DotIndicator;
