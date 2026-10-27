import {
  ApiOutlined,
  CheckCircleFilled,
  DatabaseOutlined,
  ExclamationCircleFilled,
  QuestionCircleFilled,
} from '@ant-design/icons';
import React from 'react';
import Panel from '@/components/Panel';
import ServiceStatusTag from '@/components/ServiceStatusTag';

interface DataSourceStatusProps {
  kingdeeApi?: { status: string; response_ms?: number };
  database?: { status: string; response_ms?: number };
  loading?: boolean;
}

const statusIcon = (status?: string) => {
  if (status === 'ok')
    return <CheckCircleFilled className="data-status-icon is-ok" />;
  if (status === 'error') {
    return <ExclamationCircleFilled className="data-status-icon is-error" />;
  }
  return <QuestionCircleFilled className="data-status-icon is-unknown" />;
};

const DataSourceStatus: React.FC<DataSourceStatusProps> = ({
  kingdeeApi,
  database,
  loading,
}) => {
  const sources = [
    {
      key: 'kingdee',
      name: '金蝶 API',
      description: '业务数据查询服务',
      icon: <ApiOutlined />,
      status: kingdeeApi?.status,
      response: kingdeeApi?.response_ms,
    },
    {
      key: 'database',
      name: '业务数据库',
      description: '同步数据存储服务',
      icon: <DatabaseOutlined />,
      status: database?.status,
      response: database?.response_ms,
    },
  ];

  return (
    <Panel
      title="数据源连接"
      loading={loading}
      extra={
        <span className="data-panel-caption">{sources.length} 项服务</span>
      }
    >
      <div className="data-source-grid">
        {sources.map((source) => (
          <div className="data-source-card" key={source.key}>
            <div className="data-source-icon">{source.icon}</div>
            <div className="data-source-content">
              <div className="data-source-heading">
                <strong>{source.name}</strong>
                <ServiceStatusTag status={source.status} />
              </div>
              <div className="data-source-meta">
                <span>{source.description}</span>
                {source.response !== undefined && (
                  <span className="data-response-time">
                    响应 {source.response} ms
                  </span>
                )}
              </div>
            </div>
            {statusIcon(source.status)}
          </div>
        ))}
      </div>
    </Panel>
  );
};

export default DataSourceStatus;
