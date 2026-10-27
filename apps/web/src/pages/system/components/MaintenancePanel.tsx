import {
  DeleteOutlined,
  HistoryOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { App, Button, InputNumber, Popconfirm } from 'antd';
import React, { useState } from 'react';
import Panel from '@/components/Panel';

interface MaintenancePanelProps {
  onArchive: (days: number) => Promise<unknown>;
  archiving: boolean;
}

interface ArchiveResult {
  total_deleted?: number;
  errors_deleted?: number;
  runs_deleted?: number;
}

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
      message.success(
        `已清理 ${daysToKeep} 天前的同步记录和错误日志（保留最近 ${daysToKeep} 天）`,
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : '归档失败');
    }
  };

  return (
    <Panel
      title="历史数据维护"
      extra={<span className="system-panel-caption">操作前请确认保留周期</span>}
    >
      <div className="system-maintenance-grid">
        <section className="system-archive-card">
          <div className="system-maintenance-heading">
            <span className="system-maintenance-icon is-warning">
              <DeleteOutlined />
            </span>
            <div>
              <h3>归档历史数据</h3>
              <p>清理过期同步记录与错误日志，释放数据库存储空间</p>
            </div>
          </div>
          <div className="system-archive-warning">
            <SafetyCertificateOutlined />
            <span>归档将永久删除目标数据，执行后无法恢复。</span>
          </div>
          <div className="system-archive-controls">
            <label htmlFor="archive-days">保留最近</label>
            <InputNumber
              id="archive-days"
              min={30}
              max={730}
              value={daysToKeep}
              onChange={(value) => setDaysToKeep(value || 180)}
              addonAfter="天"
              disabled={archiving}
            />
            <Popconfirm
              title="确认执行归档？"
              description={`将删除 ${daysToKeep} 天前的同步记录和错误日志，删除后不可恢复。`}
              okText="确认删除"
              okButtonProps={{ danger: true }}
              cancelText="取消"
              onConfirm={handleArchive}
            >
              <Button
                type="primary"
                danger
                loading={archiving}
                icon={<DeleteOutlined />}
              >
                执行归档
              </Button>
            </Popconfirm>
          </div>
          <p className="system-maintenance-help">
            可设置 30—730 天，默认保留最近 180 天。
          </p>
        </section>
        <section className="system-archive-result">
          <div className="system-maintenance-heading">
            <span className="system-maintenance-icon is-primary">
              <HistoryOutlined />
            </span>
            <div>
              <h3>上次归档结果</h3>
              <p>本次会话最近一次操作的清理统计</p>
            </div>
          </div>
          {lastResult ? (
            <>
              <div className="system-archive-total">
                <span>清理记录合计</span>
                <strong>
                  {(lastResult.total_deleted ?? 0).toLocaleString()}
                </strong>
                <span>条</span>
              </div>
              <div className="system-archive-breakdown">
                <div>
                  <span>错误日志</span>
                  <strong>
                    {(lastResult.errors_deleted ?? 0).toLocaleString()} 条
                  </strong>
                </div>
                <div>
                  <span>同步记录</span>
                  <strong>
                    {(lastResult.runs_deleted ?? 0).toLocaleString()} 条
                  </strong>
                </div>
              </div>
            </>
          ) : (
            <div className="system-archive-empty">
              <HistoryOutlined />
              <span>尚未执行归档操作</span>
              <p>完成归档后，这里会显示清理数量</p>
            </div>
          )}
        </section>
      </div>
    </Panel>
  );
};

export default MaintenancePanel;
