import { Typography } from 'antd';
import React from 'react';

const { Title, Text } = Typography;

export interface PageHeaderProps {
  /** 页面标题 */
  title: React.ReactNode;
  /** 标题下方的辅助说明 */
  description?: React.ReactNode;
  /** 右侧操作区（可选） */
  extra?: React.ReactNode;
}

/**
 * 页面头部：统一各业务页的标题 + 副标题排版。
 * 此前该模式在 5 个页面中重复出现，变化点稳定，收敛为一处。（原因：DRY，后续统一调整排版只需改这里）
 */
const PageHeader: React.FC<PageHeaderProps> = ({ title, description, extra }) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: 16,
        flexWrap: 'wrap',
      }}
    >
      <div>
        <Title level={3} className="!mb-1 !text-xl">
          {title}
        </Title>
        {description && (
          <Text type="secondary" className="text-sm">
            {description}
          </Text>
        )}
      </div>
      {extra}
    </div>
  );
};

export default PageHeader;
