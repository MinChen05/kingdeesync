"""
数据库字段精度优化方案

优化原则：
1. 金额类：decimal(18,2) - 节省空间，2位小数足够财务计算
2. 数量类：decimal(18,4) - 4位小数适应精密计量
3. 比率类：decimal(5,2) - 百分比格式，最多999.99%
4. 库存类：decimal(18,6) - 6位小数保持一定精度

存储空间对比：
- decimal(23,10): 13 字节
- decimal(18,2): 9 字节 (节省 31%)
- decimal(18,4): 9 字节 (节省 31%)
- decimal(5,2): 5 字节 (节省 62%)
"""

# 字段优化映射表
FIELD_OPTIMIZATION_MAP = {
    # 应付单表
    'AP_Payable': {
        'FPRICEQTY': ('decimal(18,4)', '价格数量'),
        'FALLAMOUNTFOR_D': ('decimal(18,2)', '价税合计金额'),
        'FNOTAXAMOUNTFOR': ('decimal(18,2)', '无税金额'),
        'FDISCOUNTAMOUNTFOR': ('decimal(18,2)', '折扣金额'),
        'FENTRYDISCOUNTRATE': ('decimal(5,2)', '折扣率'),
        'FENTRYTAXRATE': ('decimal(5,2)', '税率'),
    },

    # 应收单表
    'AR_receivable': {
        'FTAXPRICE': ('decimal(18,2)', '含税单价'),
        'FPRICEQTY': ('decimal(18,4)', '价格数量'),
        'FALLAMOUNTFOR_D': ('decimal(18,2)', '价税合计金额'),
    },

    # 物料表
    'bd_material': {
        'F_JY_QTY': ('decimal(18,4)', '数量1'),
        'F_JY_QTY1': ('decimal(18,4)', '数量2'),
    },

    # 工程BOM表
    'eng_bom': {
        'FQTY': ('decimal(18,4)', '数量'),
    },

    # 工程BOM子项表
    'eng_bomchild': {
        'FNUMERATOR': ('decimal(18,4)', '分子'),
        'FDENOMINATOR': ('decimal(18,4)', '分母'),
        'FQTY': ('decimal(18,4)', '数量'),
        'FACTUALQTY': ('decimal(18,4)', '实际数量'),
    },

    # 总账科目余额表
    'GL_RPT_AccountBalance': {
        'FBEGINYEARDEBITLOCAL': ('decimal(18,2)', '年初借方本位币'),
        'FBEGINYEARCREDITLOCAL': ('decimal(18,2)', '年初贷方本位币'),
        'FBEGINDEBIT': ('decimal(18,2)', '期初借方'),
        'FBEGINDEBITLOCAL': ('decimal(18,2)', '期初借方本位币'),
        'FBEGINCREDIT': ('decimal(18,2)', '期初贷方'),
        'FBEGINCREDITLOCAL': ('decimal(18,2)', '期初贷方本位币'),
        'FDEBIT': ('decimal(18,2)', '借方'),
        'FDEBITLOCAL': ('decimal(18,2)', '借方本位币'),
        'FCREDIT': ('decimal(18,2)', '贷方'),
        'FCREDITLOCAL': ('decimal(18,2)', '贷方本位币'),
        'FYTDDEBIT': ('decimal(18,2)', '年初至今借方'),
        'FYTDDEBITLOCAL': ('decimal(18,2)', '年初至今借方本位币'),
        'FYTDCREDIT': ('decimal(18,2)', '年初至今贷方'),
        'FYTDCREDITLOCAL': ('decimal(18,2)', '年初至今贷方本位币'),
        'FENDDEBIT': ('decimal(18,2)', '期末借方'),
        'FENDDEBITLOCAL': ('decimal(18,2)', '期末借方本位币'),
        'FENDCREDIT': ('decimal(18,2)', '期末贷方'),
        'FENDCREDITLOCAL': ('decimal(18,2)', '期末贷方本位币'),
        'FPROFITLOCAL': ('decimal(18,2)', '本期损益本位币'),
        'FYTDPROFITLOCAL': ('decimal(18,2)', '年初至今损益本位币'),
    },

    # 生产计划BOM表
    'prd_ppbom': {
        'FBASEQTY': ('decimal(18,4)', '基本数量'),
        'FQTY': ('decimal(18,4)', '数量'),
    },

    # 生产计划BOM子项表
    'prd_ppbomentry': {
        'FBASESTDQTY': ('decimal(18,4)', '基本标准数量'),
        'FBASENEEDQTY': ('decimal(18,4)', '基本需求数量'),
        'FBASEMUSTQTY': ('decimal(18,4)', '基本必需数量'),
        'FSTDQTY': ('decimal(18,4)', '标准数量'),
        'FNEEDQTY': ('decimal(18,4)', '需求数量'),
        'FMUSTQTY': ('decimal(18,4)', '必需数量'),
        'FBASEPICKEDQTY': ('decimal(18,4)', '基本已领数量'),
    },

    # 采购订单表
    'pur_purchaseorder': {
        'FQTY': ('decimal(18,4)', '数量'),
    },

    # 销售订单表
    'saleorder': {
        'FQTY': ('decimal(18,4)', '数量'),
        'FStockOutQty': ('decimal(18,4)', '已出库数量'),
    },

    # 即时库存表
    'STK_INVENTORY': {
        'FBASEQTY': ('decimal(18,6)', '基本数量'),
    },
}

print("=" * 80)
print("数据库字段精度优化方案")
print("=" * 80)

total_tables = len(FIELD_OPTIMIZATION_MAP)
total_fields = sum(len(fields) for fields in FIELD_OPTIMIZATION_MAP.values())

print(f"\n涉及表数量: {total_tables}")
print(f"涉及字段数量: {total_fields}")

print("\n详细优化方案:")
print("-" * 80)

for table, fields in FIELD_OPTIMIZATION_MAP.items():
    print(f"\n表名: {table}")
    for field, (new_type, desc) in fields.items():
        print(f"  {field:30} decimal(23,10) -> {new_type:15} ({desc})")

print("\n" + "=" * 80)
print("预计存储空间节省: 约 30-60%")
print("=" * 80)
