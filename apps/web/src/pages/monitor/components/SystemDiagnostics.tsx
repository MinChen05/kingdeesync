import { ReloadOutlined } from '@ant-design/icons';
import { Button, Descriptions, Space, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import ServiceStatusTag from '@/components/ServiceStatusTag';
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
            <ServiceStatusTag status={info.kingdee_api?.status} />
            {info.kingdee_api?.response_ms !== undefined && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {info.kingdee_api.response_ms}ms
              </Text>
            )}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="数据库">
          <Space>
            <ServiceStatusTag status={info.database?.status} />
            {info.database?.response_ms !== undefined && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {info.database.response_ms}ms
              </Text>
            )}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="调度器">
          <ServiceStatusTag status={info.scheduler?.status} />
        </Descriptions.Item>
        <Descriptions.Item label="日志服务">
          <ServiceStatusTag status={info.log_service?.status} />
        </Descriptions.Item>
      </Descriptions>
    </Panel>
  );
};

export default SystemDiagnostics;
