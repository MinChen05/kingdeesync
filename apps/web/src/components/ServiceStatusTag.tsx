import { Tag } from 'antd';
import React from 'react';

export interface ServiceStatusTagProps {
  status?: string;
}

/**
 * 后端服务探活状态标签（正常/异常/未知）。
 * 此前"正常/异常/未知"映射在系统诊断、数据源状态等处各自实现，
 * 收敛为一处。（原因：DRY + 服务状态文案全站一致）
 */
const ServiceStatusTag: React.FC<ServiceStatusTagProps> = ({ status }) => {
  if (status === 'ok') return <Tag color="success">正常</Tag>;
  if (status === 'error') return <Tag color="error">异常</Tag>;
  return <Tag color="default">{status || '未知'}</Tag>;
};

export default ServiceStatusTag;
