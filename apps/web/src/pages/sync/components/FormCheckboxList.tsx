import { Checkbox, Typography } from 'antd';
import React, { useMemo } from 'react';
import type { FormItem } from '../types';

const { Group: CheckboxGroup } = Checkbox;
const { Text } = Typography;

interface FormCheckboxListProps {
  forms: FormItem[];
  selected: string[];
  allSelected: boolean;
  onSelectedChange: (forms: string[]) => void;
  onSelectAll: (checked: boolean) => void;
  disabled?: boolean;
}

/** 表单分类排序定义，未列出的表单排在"其他"组（原因：按业务模块分组，方便用户快速定位） */
const FORM_ORDER: Record<string, number> = {
  // 采购
  采购订单: 10,
  采购入库单: 20,
  // 销售
  销售订单: 30,
  销售出库单: 40,
  销售退货单: 50,
  发货通知单: 60,
  // 库存
  即时库存: 70,
  仓库: 80,
  // 基础资料
  物料: 90,
  客户资料: 100,
  // 生产
  生产订单主表: 110,
  生产订单明细: 120,
  生产入库单: 130,
  生产用料清单主表: 140,
  生产用料清单明细表: 150,
  // BOM
  物料清单: 160,
  物料清单子项: 170,
  // 计划
  预测订单: 180,
  委外订单: 190,
  // 财务
  科目余额表: 200,
};

/** 表单勾选列表（含全选） */
const FormCheckboxList: React.FC<FormCheckboxListProps> = ({
  forms,
  selected,
  allSelected,
  onSelectedChange,
  onSelectAll,
  disabled,
}) => {
  // 按业务分类排序，未列出的表单排在最后（原因：按业务模块分组，方便用户快速定位）
  const sortedForms = useMemo(
    () =>
      [...forms].sort((a, b) => {
        const oa = FORM_ORDER[a.form_name] ?? 999;
        const ob = FORM_ORDER[b.form_name] ?? 999;
        if (oa !== ob) return oa - ob;
        return a.form_name.localeCompare(b.form_name, 'zh-Hans');
      }),
    [forms],
  );

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <Text strong>选择表单</Text>
        <Checkbox
          checked={allSelected}
          onChange={(e) => onSelectAll(e.target.checked)}
          disabled={disabled}
        >
          全选 ({sortedForms.length}个)
        </Checkbox>
      </div>
      <div
        className="max-h-60 overflow-y-auto rounded-md border border-gray-700/50 p-2"
        style={{ backgroundColor: '#0f172a' }}
      >
        <CheckboxGroup
          value={selected}
          onChange={(vals) => onSelectedChange(vals as string[])}
          disabled={disabled}
          className="flex flex-col gap-1"
        >
          {sortedForms.map((f) => (
            <Checkbox
              key={f.form_name}
              value={f.form_name}
              disabled={!f.enabled}
            >
              {f.form_name}
            </Checkbox>
          ))}
        </CheckboxGroup>
      </div>
      {selected.length === 0 && (
        <Text type="secondary" className="mt-1 block text-xs">
          未选择表单时将同步所有已启用的表单
        </Text>
      )}
    </div>
  );
};

export { FormCheckboxList };
