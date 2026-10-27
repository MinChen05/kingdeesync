import {
  CloudSyncOutlined,
  GithubOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { Button, Tag } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';

const REPO_URL = 'https://github.com/MinChen05/kingdeesync';

interface AboutPanelProps {
  version: string;
}

const AboutPanel: React.FC<AboutPanelProps> = ({ version }) => {
  const techStack = [
    'Go',
    'Gin',
    'React',
    'Ant Design Pro',
    'SQL Server',
    'SQLite',
  ];

  return (
    <Panel
      title="产品信息"
      extra={
        <Button
          type="text"
          icon={<GithubOutlined />}
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          项目仓库
        </Button>
      }
    >
      <div className="system-about-layout">
        <section className="system-about-brand">
          <div className="system-about-logo">
            <CloudSyncOutlined />
          </div>
          <div className="system-about-name">
            <span className="system-about-eyebrow">
              DATA OPERATIONS WORKSPACE
            </span>
            <h2>金蝶数据同步工具</h2>
            <p>稳定、清晰地管理业务数据同步链路</p>
          </div>
          <Tag className="system-version-tag">v{version || '0.1.0'}</Tag>
        </section>
        <div className="system-about-details">
          <section className="system-about-section">
            <div className="system-about-section-heading">
              <h3>技术栈</h3>
              <span>支撑数据服务与操作界面的核心技术</span>
            </div>
            <div className="system-tech-list">
              {techStack.map((tech) => (
                <Tag key={tech}>{tech}</Tag>
              ))}
            </div>
          </section>
          <section className="system-about-section system-project-info">
            <div className="system-project-row">
              <span className="system-project-label">
                <SafetyCertificateOutlined /> 开源协议
              </span>
              <strong>MIT License</strong>
            </div>
            <div className="system-project-row">
              <span className="system-project-label">
                <GithubOutlined /> 源代码
              </span>
              <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
                MinChen05/kingdeesync
              </a>
            </div>
          </section>
        </div>
      </div>
    </Panel>
  );
};

export default AboutPanel;
