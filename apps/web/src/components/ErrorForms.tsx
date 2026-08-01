import { ExclamationCircleOutlined } from '@ant-design/icons';
import { Empty, Space, Typography } from 'antd';
import React from 'react';
import Panel from '@/components/Panel';
import type { FormStat } from '@/types/form';

const { Text } = Typography;

interface ErrorFormsProps {
  forms: FormStat[];
  loading?: boolean;
}

/**
 * 异常表单 Top5：按失败记录数排序。
 * 从 monitor 页面提升为共享组件，data 页面也可复用。
 */
const ErrorForms: React.FC<ErrorFormsProps> = ({ forms, loading }) => {
  return (
    <Panel
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: 'var(--tk-error)' }} />
          异常表单 Top5
        </Space>
      }
      loading={loading}
    >
      {forms.length > 0 ? (
        <div className="space-y-2">
          {forms.map((form, i) => (
            <div
              key={form.form_name}
              className="list-row flex items-center justify-between text-sm"
            >
              <Space>
                <Text style={{ color: 'var(--tk-error)', fontWeight: 600 }}>
                  {i + 1}
                </Text>
                <Text style={{ color: 'var(--tk-text)' }}>{form.form_name}</Text>
              </Space>
              <Text type="secondary">
                失败 {form.failed_records || 0} · 运行 {form.total_runs || 0}次
              </Text>
            </div>
          ))}
        </div>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无异常数据"
        />
      )}
    </Panel>
  );
};

export { ErrorForms };
export type { ErrorFormsProps };
export default ErrorForms;
