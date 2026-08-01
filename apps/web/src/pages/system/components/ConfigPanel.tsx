import { ReloadOutlined } from '@ant-design/icons';
import { App, Button, Tag } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import { DotIndicator } from '@/components/DotIndicator';
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

/* ── Config row helper ── */

const ConfigRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px' }}>
    <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>{label}</span>
    <span style={{ fontSize: 12, color: 'var(--tk-text)', fontWeight: 500, fontFamily: 'monospace' }}>
      {value}
    </span>
  </div>
);

/* ── Config group card ── */

const ConfigGroup: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, icon, children }) => (
  <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
    <div style={{ padding: '10px 14px', borderBottom: '1px solid rgba(148,163,184,0.08)', display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 14 }}>{icon}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--tk-text)' }}>{title}</span>
    </div>
    <div style={{ padding: '4px 0' }}>{children}</div>
  </div>
);

/* ── Health status grid ── */

const HealthLevel: React.FC<{
  name: string;
  status?: string;
  extra?: string;
}> = ({ name, status, extra }) => {
  const unknown = !status;
  const ok = status === 'ok' || status === 'healthy';
  const level = unknown ? 'unknown' : ok ? 'ok' : 'error';

  return (
    <div className="list-row" style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <DotIndicator level={level} />
        <span style={{ fontWeight: 600, color: 'var(--tk-text)', fontSize: 13 }}>{name}</span>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: 12,
            color: unknown ? 'var(--tk-dim)' : ok ? 'var(--tk-success)' : 'var(--tk-error)',
          }}
        >
          {unknown ? '未知' : ok ? '正常' : '异常'}
        </span>
      </div>
      {extra && (
        <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>
          <span style={{ color: '#cbd5e1' }}>{extra}</span>
        </span>
      )}
    </div>
  );
};

/* ── Main Panel ── */

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
    } catch (err) {
      message.error(err instanceof Error ? err.message : '测试失败');
    }
  };

  const kd = config.kingdee;
  const db = config.database;
  const sync = config.sync;

  return (
    <div className="space-y-6">
      {/* 配置总览 */}
      <Panel title="配置总览" loading={loading}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {/* 金蝶配置 */}
          <ConfigGroup title="金蝶 API" icon={<span style={{ color: 'var(--tk-primary)' }}>☁️</span>}>
            <ConfigRow label="API 地址" value={kd?.query_url || '-'} />
            <ConfigRow label="账号" value={kd?.username || '-'} />
            <ConfigRow label="账号 ID" value={kd?.acct_id || '-'} />
            <ConfigRow label="LCID" value={kd?.lcid || '-'} />
            <ConfigRow label="页面大小" value={kd?.page_size ?? '-'} />
            <ConfigRow label="最大页数" value={kd?.max_pages ?? '-'} />
            <ConfigRow label="限流 QPS" value={kd?.rate_limit_qps ?? '-'} />
            <ConfigRow label="保持会话" value={kd?.keep_session_alive ? '是' : '否'} />
          </ConfigGroup>

          {/* 数据库配置 */}
          <ConfigGroup title="数据库" icon={<span style={{ color: 'var(--tk-success)' }}>🗄️</span>}>
            <ConfigRow label="类型" value={<Tag color="blue">{db?.type || '-'}</Tag>} />
            <ConfigRow label="地址" value={db?.host ? `${db.host}:${db.port}` : '-'} />
            <ConfigRow label="数据库" value={db?.database || '-'} />
            <ConfigRow label="用户" value={db?.user || '-'} />
          </ConfigGroup>

          {/* 同步配置 */}
          <ConfigGroup title="同步设置" icon={<span style={{ color: 'var(--tk-indigo)' }}>🔄</span>}>
            <ConfigRow label="同步模式" value={<Tag color="green">{sync?.sync_type || '-'}</Tag>} />
            <ConfigRow label="同步间隔" value={sync?.sync_interval != null ? `${sync.sync_interval}s` : '-'} />
            <ConfigRow label="表单并发" value={sync?.table_concurrency ?? '-'} />
            <ConfigRow label="时间窗口" value={sync?.time_window_days != null ? `${sync.time_window_days}天` : '-'} />
            <ConfigRow label="自动同步" value={
              <Tag color={sync?.auto_sync ? 'green' : 'default'}>
                {sync?.auto_sync ? '开启' : '关闭'}
              </Tag>
            } />
          </ConfigGroup>
        </div>
      </Panel>

      {/* 连接状态 */}
      <Panel
        title="连接状态"
        extra={
          <Button
            size="small"
            loading={testing || diagLoading}
            icon={<ReloadOutlined />}
            onClick={handleTest}
          >
            测试连接
          </Button>
        }
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <HealthLevel
            name="金蝶 API"
            status={diagnostics?.kingdee_api?.status}
            extra={diagnostics?.kingdee_api?.response_ms != null ? `${diagnostics.kingdee_api.response_ms}ms` : undefined}
          />
          <HealthLevel
            name="数据库"
            status={diagnostics?.database?.status}
            extra={diagnostics?.database?.response_ms != null ? `${diagnostics.database.response_ms}ms` : undefined}
          />
          <HealthLevel
            name="调度器"
            status={diagnostics?.scheduler?.status}
          />
          <HealthLevel
            name="日志服务"
            status={diagnostics?.log_service?.status}
          />
        </div>
      </Panel>
    </div>
  );
};

export default ConfigPanel;
