import { ReloadOutlined } from '@ant-design/icons';
import { Button, Typography } from 'antd';
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

const SystemDiagnostics: React.FC<SystemDiagnosticsProps> = ({
  info,
  loading,
  onRefresh,
}) => {
  const services: Array<{
    key: string;
    name: string;
    data?: { status: string; response_ms?: number };
  }> = [
    { key: 'kingdee', name: '金蝶 API', data: info.kingdee_api },
    { key: 'database', name: '数据库', data: info.database },
    { key: 'scheduler', name: '调度器', data: info.scheduler },
    { key: 'logs', name: '日志服务', data: info.log_service },
  ];

  return (
    <Panel
      title="系统诊断"
      extra={
        onRefresh && (
          <Button
            size="small"
            onClick={onRefresh}
            icon={<ReloadOutlined />}
            loading={loading}
            aria-label="重新检测系统服务"
          >
            重测
          </Button>
        )
      }
      loading={loading}
    >
      <div className="monitor-diagnostics">
        {services.map((service) => (
          <div className="monitor-diagnostic" key={service.key}>
            <Text className="monitor-diagnostic__name">{service.name}</Text>
            <div className="monitor-diagnostic__status">
              <ServiceStatusTag status={service.data?.status} />
              {service.data?.response_ms !== undefined && (
                <Text type="secondary">{service.data.response_ms} ms</Text>
              )}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
};

export default SystemDiagnostics;
