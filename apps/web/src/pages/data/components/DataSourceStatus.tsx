import {
  CheckCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { Space, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import ServiceStatusTag from '@/components/ServiceStatusTag';

const { Text } = Typography;

interface DataSourceStatusProps {
  kingdeeApi?: { status: string; response_ms?: number };
  database?: { status: string; response_ms?: number };
  loading?: boolean;
}

/**
 * 数据源状态卡片：金蝶 API + 数据库连接状态。
 *
 * （原因：运维人员首先需要确认数据链路是否正常，再操作表单）
 */
const DataSourceStatus: React.FC<DataSourceStatusProps> = ({
  kingdeeApi,
  database,
  loading,
}) => {
  // 状态文案/颜色收敛到 ServiceStatusTag（原因：DRY），此处仅保留卡片右侧图标
  const statusIcon = (status?: string) =>
    status === 'ok' ? (
      <CheckCircleOutlined style={{ color: 'var(--tk-success)' }} />
    ) : (
      <ExclamationCircleOutlined style={{ color: 'var(--tk-error)' }} />
    );

  const kdStatus = kingdeeApi?.status;
  const dbStatus = database?.status;

  return (
    <Panel title="数据源状态" loading={loading}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* 金蝶 API */}
        <div
          className="flex items-center justify-between rounded-lg border border-gray-700/50 px-4 py-3"
          style={{ backgroundColor: '#0f172a' }}
        >
          <Space>
            <CloudServerOutlined style={{ color: 'var(--tk-primary)', fontSize: 18 }} />
            <div>
              <Text strong>金蝶 API</Text>
              <div>
                <ServiceStatusTag status={kdStatus} />
                {kingdeeApi?.response_ms !== undefined && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {kingdeeApi.response_ms}ms
                  </Text>
                )}
              </div>
            </div>
          </Space>
          {statusIcon(kdStatus)}
        </div>

        {/* 数据库 */}
        <div
          className="flex items-center justify-between rounded-lg border border-gray-700/50 px-4 py-3"
          style={{ backgroundColor: '#0f172a' }}
        >
          <Space>
            <DatabaseOutlined style={{ color: 'var(--tk-success)', fontSize: 18 }} />
            <div>
              <Text strong>数据库</Text>
              <div>
                <ServiceStatusTag status={dbStatus} />
                {database?.response_ms !== undefined && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {database.response_ms}ms
                  </Text>
                )}
              </div>
            </div>
          </Space>
          {statusIcon(dbStatus)}
        </div>
      </div>
    </Panel>
  );
};

export default DataSourceStatus;
