import {
  CheckCircleOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { Space, Tag, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';

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
  const statusMeta = (status: string) => {
    if (status === 'ok')
      return {
        icon: <CheckCircleOutlined />,
        color: 'success' as const,
        text: '正常',
      };
    if (status === 'error')
      return {
        icon: <ExclamationCircleOutlined />,
        color: 'error' as const,
        text: '异常',
      };
    return {
      icon: <ExclamationCircleOutlined />,
      color: 'default' as const,
      text: '未知',
    };
  };

  const kd = kingdeeApi ? statusMeta(kingdeeApi.status) : statusMeta('unknown');
  const db = database ? statusMeta(database.status) : statusMeta('unknown');

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
                <Tag color={kd.color}>{kd.text}</Tag>
                {kingdeeApi?.response_ms !== undefined && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {kingdeeApi.response_ms}ms
                  </Text>
                )}
              </div>
            </div>
          </Space>
          {kd.icon}
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
                <Tag color={db.color}>{db.text}</Tag>
                {database?.response_ms !== undefined && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {database.response_ms}ms
                  </Text>
                )}
              </div>
            </div>
          </Space>
          {db.icon}
        </div>
      </div>
    </Panel>
  );
};

export default DataSourceStatus;
