import { ExclamationCircleOutlined, HistoryOutlined } from '@ant-design/icons';
import { App, Button, InputNumber, Result, Typography } from 'antd';
import React, { useState } from 'react';
import Panel from '@/components/Panel';

const { Text } = Typography;

interface MaintenancePanelProps {
  onArchive: (days: number) => Promise<unknown>;
  archiving: boolean;
}

interface ArchiveResult {
  total_deleted?: number;
  errors_deleted?: number;
  runs_deleted?: number;
}

/**
 * 维护操作面板：归档历史数据。
 * 使用 .glass-card 样式包裹操作区，归档后展示删除统计。
 */
const MaintenancePanel: React.FC<MaintenancePanelProps> = ({
  onArchive,
  archiving,
}) => {
  const { message } = App.useApp();
  const [daysToKeep, setDaysToKeep] = useState(180);
  const [lastResult, setLastResult] = useState<ArchiveResult | null>(null);

  const handleArchive = async () => {
    try {
      const result = await onArchive(daysToKeep);
      setLastResult((result as ArchiveResult) || { total_deleted: 0 });
      message.success(`已归档 ${daysToKeep} 天前的历史数据`);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '归档失败');
    }
  };

  return (
    <Panel title="维护操作">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* 归档操作 */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <span style={{ color: 'var(--tk-warning)', fontSize: 18 }}>
              <ExclamationCircleOutlined />
            </span>
            <Text strong style={{ fontSize: 14, color: 'var(--tk-text)' }}>
              归档历史数据
            </Text>
          </div>
          <Text type="secondary" className="mb-4 block text-sm" style={{ paddingLeft: 26 }}>
            删除指定天数前的同步记录和错误日志，释放存储空间。
          </Text>
          <div className="flex items-center gap-4">
            <InputNumber
              min={30}
              max={730}
              value={daysToKeep}
              onChange={(v) => setDaysToKeep(v || 180)}
              addonAfter="天"
              style={{ width: 160 }}
            />
            <Button
              type="primary"
              danger
              loading={archiving}
              onClick={handleArchive}
            >
              执行归档
            </Button>
          </div>
          <Text type="secondary" className="mt-3 block text-xs">
            最小保留 30 天，最大 730 天，默认 180 天。
          </Text>
        </div>

        {/* 上次归档结果 */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <span style={{ color: 'var(--tk-primary)', fontSize: 18 }}>
              <HistoryOutlined />
            </span>
            <Text strong style={{ fontSize: 14, color: 'var(--tk-text)' }}>
              上次归档结果
            </Text>
          </div>
          {lastResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 12px' }}>
                <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>错误日志</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--tk-text)' }}>
                  {lastResult.errors_deleted ?? 0} 条
                </span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 12px' }}>
                <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>同步记录</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--tk-text)' }}>
                  {lastResult.runs_deleted ?? 0} 条
                </span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 12px', borderTop: '1px solid rgba(148,163,184,0.12)' }}>
                <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>合计</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--tk-primary)' }}>
                  {lastResult.total_deleted ?? 0} 条
                </span>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 80 }}>
              <Text type="secondary" style={{ fontSize: 13 }}>
                尚未执行归档操作
              </Text>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
};

export default MaintenancePanel;
