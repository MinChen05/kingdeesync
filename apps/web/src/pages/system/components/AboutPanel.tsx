import { GithubOutlined, RocketOutlined } from '@ant-design/icons';
import { Tag, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';

const REPO_URL = 'https://github.com/MinChen05/kingdeesync';

const { Text, Title } = Typography;

interface AboutPanelProps {
  version: string;
}

/**
 * 关于面板：应用名称、版本、技术栈。
 * 居中品牌卡片设计。
 */
const AboutPanel: React.FC<AboutPanelProps> = ({ version }) => {
  const techStack = [
    { name: 'Go', color: '#0acf83' },
    { name: 'Gin', color: '#38bdf8' },
    { name: 'React', color: '#61dafb' },
    { name: 'Ant Design Pro', color: '#1677ff' },
    { name: 'Doris', color: '#f59e0b' },
    { name: 'SQLite', color: '#003b57' },
  ];

  return (
    <Panel title="关于">
      {/* 品牌区 */}
      <div
        className="glass-card"
        style={{
          padding: '32px',
          textAlign: 'center',
          marginBottom: 24,
          background: 'linear-gradient(135deg, rgba(56,189,248,0.08), rgba(129,140,248,0.08))',
        }}
      >
        <div style={{ fontSize: 36, marginBottom: 8 }}>
          <RocketOutlined style={{ color: 'var(--tk-primary)' }} />
        </div>
        <Title level={3} style={{ color: 'var(--tk-text-light)', marginBottom: 4 }}>
          金蝶数据同步工具
        </Title>
        <Text type="secondary" style={{ fontSize: 14 }}>
          Kingdee Data Sync Tool
        </Text>
        <div style={{ marginTop: 12 }}>
          <Tag
            color="processing"
            style={{
              fontSize: 13,
              padding: '4px 16px',
              borderRadius: 20,
              border: '1px solid var(--tk-primary)',
              color: 'var(--tk-primary)',
            }}
          >
            v{version || '0.1.0'}
          </Tag>
        </div>
      </div>

      {/* 技术栈 */}
      <div style={{ marginBottom: 24 }}>
        <Text strong style={{ fontSize: 13, color: 'var(--tk-text)', display: 'block', marginBottom: 12 }}>
          技术栈
        </Text>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {techStack.map((t) => (
            <Tag
              key={t.name}
              style={{
                fontSize: 12,
                padding: '2px 12px',
                borderRadius: 6,
                border: `1px solid ${t.color}40`,
                color: t.color,
                backgroundColor: `${t.color}10`,
              }}
            >
              {t.name}
            </Tag>
          ))}
        </div>
      </div>

      {/* 项目信息 */}
      <div className="glass-card" style={{ padding: '16px 20px' }}>
        <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
          <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>开源协议</span>
          <span style={{ fontSize: 12, color: 'var(--tk-text)' }}>MIT</span>
        </div>
        <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
          <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>仓库</span>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: 'var(--tk-primary)', display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none' }}
          >
            <GithubOutlined /> MinChen05/kingdeesync
          </a>
        </div>
      </div>
    </Panel>
  );
};

export default AboutPanel;
