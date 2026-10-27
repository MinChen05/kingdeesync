import { ProCard } from '@ant-design/pro-components';
import React from 'react';

export interface PanelProps {
  title?: React.ReactNode;
  extra?: React.ReactNode;
  loading?: boolean;
  bodyStyle?: React.CSSProperties;
  className?: string;
  children: React.ReactNode;
}

const Panel: React.FC<PanelProps> = ({
  title,
  extra,
  loading = false,
  bodyStyle,
  className = '',
  children,
}) => {
  return (
    <ProCard
      className={`surface-panel ${className}`.trim()}
      loading={loading}
      variant="borderless"
      title={title ? <span className="panel-title">{title}</span> : undefined}
      extra={extra}
      styles={{ body: { padding: '20px 22px', ...bodyStyle } }}
    >
      {children}
    </ProCard>
  );
};

export default Panel;
