import { Tag } from 'antd';
import React from 'react';

/** 同步类型 → 展示文案与 Tag 颜色（全站唯一收敛点） */
const TYPE_META: Record<string, { color: string; text: string }> = {
  incremental: { color: 'blue', text: '增量' },
  full: { color: 'green', text: '全量' },
  reset: { color: 'orange', text: '重置' },
};

export interface SyncTypeTagProps {
  type?: string;
}

/**
 * 同步类型标签：统一增量/全量/重置的展示。
 * 此前映射重复 3 处，且 LastSyncSummary 中全量误用 blue，收敛时一并修正。（原因：DRY + 语义色一致）
 */
const SyncTypeTag: React.FC<SyncTypeTagProps> = ({ type }) => {
  const meta = TYPE_META[type || ''] || { color: 'orange', text: type || '-' };
  return <Tag color={meta.color}>{meta.text}</Tag>;
};

export default SyncTypeTag;
