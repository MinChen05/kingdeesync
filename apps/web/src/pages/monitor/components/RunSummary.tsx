import { Alert, Descriptions, Typography } from 'antd';
import React from 'react';
import SyncStatusTag from '@/components/SyncStatusTag';
import SyncTypeTag from '@/components/SyncTypeTag';
import { formatDuration } from '@/utils/format';
import type { RunDetail } from '../types';

const { Text } = Typography;

interface RunSummaryProps {
  detail: RunDetail;
}

/** 运行摘要：Alert + Descriptions 区块 */
const RunSummary: React.FC<RunSummaryProps> = ({ detail }) => {
  return (
    <>
      {detail.error_message && (
        <Alert
          type="error"
          showIcon
          message="运行错误"
          description={detail.error_message}
        />
      )}

      <Descriptions column={3} size="small" bordered>
        <Descriptions.Item label="类型">
          <SyncTypeTag type={detail.sync_type} />
        </Descriptions.Item>
        <Descriptions.Item label="状态">
          <SyncStatusTag status={detail.status} />
        </Descriptions.Item>
        <Descriptions.Item label="耗时">
          {formatDuration(detail.duration_seconds)}
        </Descriptions.Item>
        <Descriptions.Item label="开始时间" span={2}>
          {detail.start_time || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="结束时间">
          {detail.end_time || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="表单">
          {detail.success_forms}/{detail.form_count} 成功
        </Descriptions.Item>
        <Descriptions.Item label="总记录">
          {(detail.total_records || 0).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="失败记录">
          <Text
            style={{
              color: (detail.failed_records || 0) > 0 ? 'var(--tk-error)' : undefined,
            }}
          >
            {(detail.failed_records || 0).toLocaleString()}
          </Text>
        </Descriptions.Item>
      </Descriptions>
    </>
  );
};

export { RunSummary };
