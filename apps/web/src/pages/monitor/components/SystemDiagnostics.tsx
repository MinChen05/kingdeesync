import { ReloadOutlined } from '@ant-design/icons';
import { Button, Descriptions, Space, Tag, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import type { DiagInfo } from '../types';

const { Text } = Typography;

interface SystemDiagnosticsProps {
  info: DiagInfo;
  loading?: boolean;
  onRefresh?: () => void;
}

/**
 * 系统诊断：4 服务状态。
 *
 * （原因：运维人员需要确认底层服务是否正常）
 */
const SystemDiagnostics: React.FC<SystemDiagnosticsProps> = ({
  info,
  loading,
  onRefresh,
}) => {
  const diagStatusTag = (status: string) => {
    if (status === 'ok') return <Tag color="success">正常</Tag>;
    if (status === 'error') return <Tag color="error">异常</Tag>;
    return <Tag color="default">{status || '未知'}</Tag>;
  };

  return (
    <Panel
      title="系统诊断"
      extra={
        onRefresh && (
          <Button size="small" onClick={onRefresh} icon={<ReloadOutlined />}>
            重测
          </Button>
        )
      }
      loading={loading}
    >
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="金蝶 API">
          <Space>
            {diagStatusTag(info.kingdee_api?.status || 'unknown')}
            {info.kingdee_api?.response_ms !== undefined && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {info.kingdee_api.response_ms}ms
              </Text>
            )}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="数据库">
          <Space>
            {diagStatusTag(info.database?.status || 'unknown')}
            {info.database?.response_ms !== undefined && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {info.database.response_ms}ms
              </Text>
            )}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="调度器">
          {diagStatusTag(info.scheduler?.status || 'unknown')}
        </Descriptions.Item>
        <Descriptions.Item label="日志服务">
          {diagStatusTag(info.log_service?.status || 'unknown')}
        </Descriptions.Item>
      </Descriptions>
    </Panel>
  );
};

export default SystemDiagnostics;
