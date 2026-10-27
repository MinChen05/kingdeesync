import {
  SearchOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
} from '@ant-design/icons';
import { Button, Input, Select, Tooltip } from 'antd';
import React from 'react';

interface FormToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  sortField: string;
  onSortChange: (value: string) => void;
  sortOrder: 'asc' | 'desc';
  onSortOrderChange: (value: 'asc' | 'desc') => void;
  resultCount: number;
  totalCount: number;
}

const FormToolbar: React.FC<FormToolbarProps> = ({
  search,
  onSearchChange,
  sortField,
  onSortChange,
  sortOrder,
  onSortOrderChange,
  resultCount,
  totalCount,
}) => (
  <div className="filter-toolbar data-filter-toolbar">
    <Input
      className="data-search-input"
      placeholder="搜索表单名称"
      aria-label="搜索表单名称"
      prefix={<SearchOutlined />}
      allowClear
      value={search}
      onChange={(event) => onSearchChange(event.target.value)}
    />
    <div className="data-sort-controls">
      <Select
        aria-label="排序字段"
        value={sortField}
        onChange={onSortChange}
        options={[
          { value: 'none', label: '默认排序' },
          { value: 'errors', label: '按错误数排序' },
          { value: 'last_sync', label: '按同步时间排序' },
        ]}
      />
      {sortField !== 'none' && (
        <Tooltip title={sortOrder === 'desc' ? '切换为升序' : '切换为降序'}>
          <Button
            className="data-sort-order"
            icon={
              sortOrder === 'desc' ? (
                <SortDescendingOutlined />
              ) : (
                <SortAscendingOutlined />
              )
            }
            onClick={() =>
              onSortOrderChange(sortOrder === 'desc' ? 'asc' : 'desc')
            }
          >
            {sortOrder === 'desc' ? '降序' : '升序'}
          </Button>
        </Tooltip>
      )}
    </div>
    <span className="data-filter-result">
      {search
        ? `筛选 ${resultCount} / ${totalCount}`
        : `共 ${totalCount} 个表单`}
    </span>
  </div>
);

export type { FormToolbarProps };
export { FormToolbar };
