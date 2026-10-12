/**
 * 表单分类排序定义（原因：按业务模块分组，方便用户快速定位）。
 * 同步页与调度页共用（此前两处逐字相同的私有定义，收敛为单一来源）。
 */
export const FORM_CATEGORIES: Record<string, { label: string; forms: string[] }> = {
  procurement: { label: '采购', forms: ['采购订单', '采购入库单'] },
  sales: {
    label: '销售',
    forms: ['销售订单', '销售出库单', '销售退货单', '发货通知单'],
  },
  inventory: { label: '库存', forms: ['即时库存', '仓库'] },
  master: { label: '基础资料', forms: ['物料', '客户资料'] },
  production: {
    label: '生产',
    forms: [
      '生产订单主表',
      '生产订单明细',
      '生产入库单',
      '生产用料清单主表',
      '生产用料清单明细表',
    ],
  },
  bom: { label: 'BOM', forms: ['物料清单', '物料清单子项'] },
  planning: { label: '计划', forms: ['预测订单', '委外订单'] },
  finance: { label: '财务', forms: ['科目余额表', '应付单', '应收单'] },
};
