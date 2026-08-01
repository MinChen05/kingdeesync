import { WarningOutlined } from '@ant-design/icons';
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

/**
 * 近 7 天异常表单 Top5：排名 + 表单名 + 失败次数，最近错误信息悬浮可见。
 */
const ErrorForms: React.FC<ErrorFormsProps> = ({ topForms, loading }) => {
  return (
    <Panel title="近 7 天异常表单" loading={loading}>
      {topForms.length > 0 ? (
        <div className="space-y-2">
          {topForms.map((form, idx) => (
            <Link
              key={form.form_name}
              to={`/monitor?form=${encodeURIComponent(form.form_name)}`}
              className="list-row"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                textDecoration: 'none',
              }}
            >
              <span
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 12,
                  fontWeight: 600,
                  flexShrink: 0,
                  color: 'var(--tk-error)',
                  background: 'rgba(248,113,113,0.16)',
                  boxShadow: '0 0 8px rgba(248,113,113,0.25)',
                }}
              >
                {idx + 1}
              </span>
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
