import {
  SearchOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
} from '@ant-design/icons';
import { Button, Input, Select, Space } from 'antd';
import React from 'react';
import type { FormItem } from '../../data/types';

const { Option } = Select;

interface FormToolbarProps {
  search: string;
  onSearchChange: (v: string) => void;
  sortField: string;
  onSortChange: (v: string) => void;
  sortOrder: 'asc' | 'desc';
  onSortOrderChange: (v: 'asc' | 'desc') => void;
  /** 当前分组表单列表（用于批量操作） */
  forms: FormItem[];
  /** true = 当前组已启用，按钮执行"批量禁用" */
  groupEnabled: boolean;
  onBatchToggle: (forms: FormItem[], enable: boolean) => void;
}

/**
 * 表单工具栏：搜索 + 排序 + 批量操作。
 * 从 FormsManager 抽出，CollapsePanel 的 header 直接渲染此组件。
 */
const FormToolbar: React.FC<FormToolbarProps> = ({
  search,
  onSearchChange,
  sortField,
  onSortChange,
  sortOrder,
  onSortOrderChange,
  forms,
  groupEnabled,
  onBatchToggle,
}) => {
  return (
    <>
      {/* 搜索与排序 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input
          placeholder="搜索表单名称"
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 200 }}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        <Select
          placeholder="排序"
          style={{ width: 160 }}
          value={sortField}
          onChange={onSortChange}
        >
          <Option value="none">默认排序</Option>
          <Option value="errors">按错误数</Option>
          <Option value="last_sync">按上次同步时间</Option>
        </Select>
        {sortField !== 'none' && (
          <Select
            style={{ width: 100 }}
            value={sortOrder}
            onChange={onSortOrderChange}
          >
            <Option value="desc">
              <SortDescendingOutlined /> 降序
            </Option>
            <Option value="asc">
              <SortAscendingOutlined /> 升序
            </Option>
          </Select>
        )}
      </div>

      {/* 分组批量操作（渲染在 CollapsePanel header 中） */}
      <Space>
        <span style={{ fontSize: 12, color: 'var(--tk-dim)' }}>
          共 {forms.length} 个表单
        </span>
        <Button
          size="small"
          onClick={() => onBatchToggle(forms, !groupEnabled)}
          disabled={forms.length === 0}
        >
          {groupEnabled ? '批量禁用' : '批量启用'}
        </Button>
      </Space>
    </>
  );
};

export { FormToolbar };
export type { FormToolbarProps };
