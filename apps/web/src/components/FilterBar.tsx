import { SearchOutlined } from '@ant-design/icons';
import { Button, Input, Select } from 'antd';
import React from 'react';
import type { SelectProps } from 'antd';

interface FilterOption {
  label: string;
  value: string;
}

interface FilterBarProps {
  /** 状态筛选器配置 */
  statusOptions?: FilterOption[];
  statusValue?: string;
  onStatusChange?: (value: string) => void;
  /** 类型筛选器配置 */
  typeOptions?: FilterOption[];
  typeValue?: string;
  onTypeChange?: (value: string) => void;
  /** 搜索框 */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  /** 重置按钮 */
  onReset?: () => void;
  showReset?: boolean;
  /** 额外操作区（渲染在重置按钮之前） */
  extra?: React.ReactNode;
}

/**
 * 通用筛选栏：状态下拉 + 类型下拉 + 日期范围 + 搜索 + 重置。
 * 用于 HistoryTable、JobTable 等表格页的顶部筛选区。
 * 各字段可选，按需启用。
 */
const FilterBar: React.FC<FilterBarProps> = ({
  statusOptions,
  statusValue,
  onStatusChange,
  typeOptions,
  typeValue,
  onTypeChange,
  searchValue,
  onSearchChange,
  searchPlaceholder = '搜索',
  onReset,
  showReset = true,
  extra,
}) => {
  const selectStyle: SelectProps['style'] = { width: 100 };

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3">
      {statusOptions && (
        <Select
          placeholder="状态"
          allowClear
          style={selectStyle}
          value={statusValue}
          onChange={(v) => onStatusChange?.(v || '')}
          options={statusOptions}
        />
      )}

      {typeOptions && (
        <Select
          placeholder="类型"
          allowClear
          style={selectStyle}
          value={typeValue}
          onChange={(v) => onTypeChange?.(v || '')}
          options={typeOptions}
        />
      )}

      {onSearchChange && (
        <Input
          placeholder={searchPlaceholder}
          prefix={<SearchOutlined />}
          allowClear
          style={{ width: 180 }}
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      )}

      {extra}

      {showReset && onReset && (
        <Button size="small" onClick={onReset}>
          重置
        </Button>
      )}
    </div>
  );
};

export { FilterBar };
export type { FilterBarProps, FilterOption };
export default FilterBar;
