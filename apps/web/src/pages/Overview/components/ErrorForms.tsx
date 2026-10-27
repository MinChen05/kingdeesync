import { ArrowRightOutlined, WarningOutlined } from '@ant-design/icons';
import { Link } from '@umijs/max';
import { Empty, Tag, Tooltip, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import type { TopForm } from '../hooks';

const { Text } = Typography;

interface ErrorFormsProps {
  topForms: TopForm[];
  loading?: boolean;
}

const ErrorForms: React.FC<ErrorFormsProps> = ({ topForms, loading }) => {
  return (
    <Panel
      title="近 7 天异常表单"
      loading={loading}
      extra={
        <Link
          to="/monitor"
          style={{ fontSize: 13, color: 'var(--tk-primary)' }}
          aria-label="查看全部异常"
        >
          <ArrowRightOutlined />
        </Link>
      }
    >
      {topForms.length > 0 ? (
        <div className="space-y-2">
          {topForms.map((form, index) => (
            <Link
              key={form.form_name}
              to={`/monitor?form=${encodeURIComponent(form.form_name)}`}
              className="list-row interactive-list"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                textDecoration: 'none',
              }}
            >
              <span className="error-rank">{index + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Tooltip
                  title={form.last_error || undefined}
                  placement="topLeft"
                >
                  <Text
                    strong
                    style={{
                      color: 'var(--tk-text)',
                      fontSize: 13,
                      display: 'block',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {form.form_name}
                  </Text>
                </Tooltip>
              </div>
              <Tag
                color="error"
                icon={<WarningOutlined />}
                style={{ flexShrink: 0, marginInlineEnd: 0 }}
              >
                {form.failure_count} 次
              </Tag>
            </Link>
          ))}
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="近 7 天无异常"
        />
      )}
    </Panel>
  );
};

export default ErrorForms;
