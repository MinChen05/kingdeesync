import { Tag } from 'antd';
import React from 'react';

/** 同步运行状态 → 展示文案与 Tag 颜色（全站唯一收敛点） */
const STATUS_META: Record<string, { color: string; text: string }> = {
  success: { color: 'success', text: '成功' },
  failed: { color: 'error', text: '失败' },
  failed_abnormal_exit: { color: 'error', text: '异常退出' },
  partial: { color: 'warning', text: '部分完成' },
  running: { color: 'processing', text: '运行中' },
  idle: { color: 'default', text: '空闲' },
};

export interface SyncStatusTagProps {
  status?: string;
}

/**
 * 同步状态标签：统一各页面（监控历史、最近异常、上次同步、表单管理）的状态展示。
 * 此前同一映射在 4+ 处重复且文案不一致，收敛为一处。（原因：DRY + 状态语义全站一致）
 */
const SyncStatusTag: React.FC<SyncStatusTagProps> = ({ status }) => {
  const meta = STATUS_META[status || ''] || {
    color: 'default',
    text: status || '未知',
  };
  return <Tag color={meta.color}>{meta.text}</Tag>;
};

export default SyncStatusTag;
