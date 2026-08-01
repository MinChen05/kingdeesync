import React from 'react';
import { ProCard } from '@ant-design/pro-components';

export interface PanelProps {
  /** 面板标题 */
  title?: React.ReactNode;
  /** 标题右侧操作区 */
  extra?: React.ReactNode;
  /** 加载态（显示骨架屏） */
  loading?: boolean;
  /** 自定义内容区内边距等样式 */
  bodyStyle?: React.CSSProperties;
  children: React.ReactNode;
}

/**
 * 通用面板容器：统一深色玻璃拟态卡片风格与标题样式。
 * 所有面板都基于它，后续调整整体视觉（圆角/描边/内边距）只需改这里。（原因：收敛风格、便于扩展）
 */
const Panel: React.FC<PanelProps> = ({ title, extra, loading = false, bodyStyle, children }) => {
  const body: React.CSSProperties = { padding: '18px 20px', ...bodyStyle };
  return (
    <ProCard
      loading={loading}
      variant="borderless"
      title={title ? <span className="overview-panel-title">{title}</span> : undefined}
      extra={extra}
      styles={{ body }}
    >
      {children}
    </ProCard>
  );
};

export default Panel;
