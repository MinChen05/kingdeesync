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
 * 异常表单 Top3：按失败记录数排序（后端 GetRiskItems(3) 仅返回 3 条，
 * 标题与数据条数保持一致，原因：避免承诺不存在的名次）。
 * 从 monitor 页面提升为共享组件，data 页面也可复用。
 */
const ErrorForms: React.FC<ErrorFormsProps> = ({ forms, loading }) => {
  return (
    <Panel
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: 'var(--tk-error)' }} />
          异常表单 Top3
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
              {/* 不再展示"运行 N 次"：total_runs 无后端数据来源恒为 0（原因：假数据误导判断） */}
              <Text type="secondary">失败 {form.failed_records || 0} 条</Text>
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
