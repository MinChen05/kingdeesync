import {
  CheckCircleFilled,
  CloseCircleFilled,
  CloudServerOutlined,
  DatabaseOutlined,
  QuestionCircleFilled,
  ReloadOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import { App, Button, Tag } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import type { V1Diagnostics } from '@/services/v1';
import type { ConfigData } from '../types';

interface ConfigPanelProps {
  config: ConfigData;
  loading?: boolean;
  diagnostics?: V1Diagnostics;
  diagLoading?: boolean;
  onTestConnections?: () => Promise<unknown>;
  testing?: boolean;
}

const ConfigRow: React.FC<{ label: string; value: React.ReactNode }> = ({
  label,
  value,
}) => (
  <div className="system-config-row">
    <span className="system-config-label">{label}</span>
    <span className="system-config-value">{value}</span>
  </div>
);

const ConfigGroup: React.FC<{
  title: string;
  description: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, description, icon, children }) => (
  <section className="system-config-group">
    <div className="system-config-group-header">
      <span className="system-config-group-icon">{icon}</span>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
    <div className="system-config-list">{children}</div>
  </section>
);

const HealthLevel: React.FC<{
  name: string;
  description: string;
  status?: string;
  response?: number;
}> = ({ name, description, status, response }) => {
  const unknown = !status || status === 'unknown';
  const ok = status === 'ok' || status === 'healthy';
  const level = unknown ? 'unknown' : ok ? 'ok' : 'error';

  return (
    <div className={`system-health-card is-${level}`}>
      <span className="system-health-icon">
        {unknown ? (
          <QuestionCircleFilled />
        ) : ok ? (
          <CheckCircleFilled />
        ) : (
          <CloseCircleFilled />
        )}
      </span>
      <div className="system-health-content">
        <div className="system-health-heading">
          <strong>{name}</strong>
          <span>{unknown ? '状态未知' : ok ? '运行正常' : '连接异常'}</span>
        </div>
        <div className="system-health-meta">
          <span>{description}</span>
          {response !== undefined && <span>响应 {response} ms</span>}
        </div>
      </div>
    </div>
  );
};

const ConfigPanel: React.FC<ConfigPanelProps> = ({
  config,
  loading,
  diagnostics,
  diagLoading,
  onTestConnections,
  testing,
}) => {
  const { message } = App.useApp();

  const handleTest = async () => {
    try {
      await onTestConnections?.();
      message.success('连接测试完成');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '测试失败');
    }
  };

  const kd = config.kingdee;
  const db = config.database;
  const sync = config.sync;

  return (
    <div className="system-config-stack">
      <Panel
        title="运行参数"
        loading={loading}
        extra={
          <span className="system-panel-caption">当前生效配置 · 只读</span>
        }
      >
        <div className="system-config-grid">
          <ConfigGroup
            title="金蝶 API"
            description="数据查询与访问控制"
            icon={<CloudServerOutlined />}
          >
            <ConfigRow label="API 地址" value={kd?.query_url || '-'} />
            <ConfigRow label="账号" value={kd?.username || '-'} />
            <ConfigRow label="账号 ID" value={kd?.acct_id || '-'} />
            <ConfigRow label="LCID" value={kd?.lcid || '-'} />
            <ConfigRow label="页面大小" value={kd?.page_size ?? '-'} />
            <ConfigRow label="最大页数" value={kd?.max_pages ?? '-'} />
            <ConfigRow label="限流 QPS" value={kd?.rate_limit_qps ?? '-'} />
            <ConfigRow
              label="保持会话"
              value={kd?.keep_session_alive ? '是' : '否'}
            />
          </ConfigGroup>
          <ConfigGroup
            title="业务数据库"
            description="同步结果存储连接"
            icon={<DatabaseOutlined />}
          >
            <ConfigRow
              label="类型"
              value={
                <Tag className="system-neutral-tag">{db?.type || '-'}</Tag>
              }
            />
            <ConfigRow
              label="地址"
              value={db?.host ? `${db.host}:${db.port}` : '-'}
            />
            <ConfigRow label="数据库" value={db?.database || '-'} />
            <ConfigRow label="用户" value={db?.user || '-'} />
          </ConfigGroup>
          <ConfigGroup
            title="同步策略"
            description="调度频率与执行边界"
            icon={<SyncOutlined />}
          >
            <ConfigRow
              label="同步模式"
              value={
                <Tag className="system-primary-tag">
                  {sync?.sync_type || '-'}
                </Tag>
              }
            />
            <ConfigRow
              label="同步间隔"
              value={
                sync?.sync_interval != null ? `${sync.sync_interval} 秒` : '-'
              }
            />
            <ConfigRow
              label="表单并发"
              value={sync?.table_concurrency ?? '-'}
            />
            <ConfigRow
              label="时间窗口"
              value={
                sync?.time_window_days != null
                  ? `${sync.time_window_days} 天`
                  : '-'
              }
            />
            <ConfigRow
              label="同步时段"
              value={
                sync?.time_window_start && sync?.time_window_end
                  ? `${sync.time_window_start} — ${sync.time_window_end}`
                  : '不限制'
              }
            />
            <ConfigRow
              label="自动同步"
              value={
                <Tag
                  className={
                    sync?.auto_sync
                      ? 'system-success-tag'
                      : 'system-neutral-tag'
                  }
                >
                  {sync?.auto_sync ? '已开启' : '已关闭'}
                </Tag>
              }
            />
          </ConfigGroup>
        </div>
      </Panel>
      <Panel
        title="服务健康"
        loading={diagLoading}
        extra={
          <Button
            loading={testing}
            icon={<ReloadOutlined />}
            onClick={handleTest}
          >
            测试全部连接
          </Button>
        }
      >
        <div className="system-health-grid">
          <HealthLevel
            name="金蝶 API"
            description="业务数据查询服务"
            status={diagnostics?.kingdee_api?.status}
            response={diagnostics?.kingdee_api?.response_ms}
          />
          <HealthLevel
            name="业务数据库"
            description="同步数据存储服务"
            status={diagnostics?.database?.status}
            response={diagnostics?.database?.response_ms}
          />
          <HealthLevel
            name="任务调度器"
            description="自动同步调度服务"
            status={diagnostics?.scheduler?.status}
          />
          <HealthLevel
            name="日志服务"
            description="运行日志采集服务"
            status={diagnostics?.log_service?.status}
          />
        </div>
      </Panel>
    </div>
  );
};

export default ConfigPanel;
