import { Typography } from 'antd';
import React from 'react';

const { Title, Text } = Typography;

export interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  extra?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  extra,
}) => {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        <div className="page-eyebrow">
          <span />
          KINGDEE DATA SYNC
        </div>
        <Title level={2}>{title}</Title>
        {description && <Text type="secondary">{description}</Text>}
      </div>
      {extra && <div className="page-header-extra">{extra}</div>}
    </header>
  );
};

export default PageHeader;
