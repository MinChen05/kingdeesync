"""
生成数据库字段精度优化的 SQL 脚本
"""

# 字段优化映射表
FIELD_OPTIMIZATION_MAP = {
    'AP_Payable': {
        'FPRICEQTY': 'decimal(18,4)',
        'FALLAMOUNTFOR_D': 'decimal(18,2)',
        'FNOTAXAMOUNTFOR': 'decimal(18,2)',
        'FDISCOUNTAMOUNTFOR': 'decimal(18,2)',
        'FENTRYDISCOUNTRATE': 'decimal(5,2)',
        'FENTRYTAXRATE': 'decimal(5,2)',
    },
    'AR_receivable': {
        'FTAXPRICE': 'decimal(18,2)',
        'FPRICEQTY': 'decimal(18,4)',
        'FALLAMOUNTFOR_D': 'decimal(18,2)',
    },
    'bd_material': {
        'F_JY_QTY': 'decimal(18,4)',
        'F_JY_QTY1': 'decimal(18,4)',
    },
    'eng_bom': {
        'FQTY': 'decimal(18,4)',
    },
    'eng_bomchild': {
        'FNUMERATOR': 'decimal(18,4)',
        'FDENOMINATOR': 'decimal(18,4)',
        'FQTY': 'decimal(18,4)',
        'FACTUALQTY': 'decimal(18,4)',
    },
    'GL_RPT_AccountBalance': {
        'FBEGINYEARDEBITLOCAL': 'decimal(18,2)',
        'FBEGINYEARCREDITLOCAL': 'decimal(18,2)',
        'FBEGINDEBIT': 'decimal(18,2)',
        'FBEGINDEBITLOCAL': 'decimal(18,2)',
        'FBEGINCREDIT': 'decimal(18,2)',
        'FBEGINCREDITLOCAL': 'decimal(18,2)',
        'FDEBIT': 'decimal(18,2)',
        'FDEBITLOCAL': 'decimal(18,2)',
        'FCREDIT': 'decimal(18,2)',
        'FCREDITLOCAL': 'decimal(18,2)',
        'FYTDDEBIT': 'decimal(18,2)',
        'FYTDDEBITLOCAL': 'decimal(18,2)',
        'FYTDCREDIT': 'decimal(18,2)',
        'FYTDCREDITLOCAL': 'decimal(18,2)',
        'FENDDEBIT': 'decimal(18,2)',
        'FENDDEBITLOCAL': 'decimal(18,2)',
        'FENDCREDIT': 'decimal(18,2)',
        'FENDCREDITLOCAL': 'decimal(18,2)',
        'FPROFITLOCAL': 'decimal(18,2)',
        'FYTDPROFITLOCAL': 'decimal(18,2)',
    },
    'prd_ppbom': {
        'FBASEQTY': 'decimal(18,4)',
        'FQTY': 'decimal(18,4)',
    },
    'prd_ppbomentry': {
        'FBASESTDQTY': 'decimal(18,4)',
        'FBASENEEDQTY': 'decimal(18,4)',
        'FBASEMUSTQTY': 'decimal(18,4)',
        'FSTDQTY': 'decimal(18,4)',
        'FNEEDQTY': 'decimal(18,4)',
        'FMUSTQTY': 'decimal(18,4)',
        'FBASEPICKEDQTY': 'decimal(18,4)',
    },
    'pur_purchaseorder': {
        'FQTY': 'decimal(18,4)',
    },
    'saleorder': {
        'FQTY': 'decimal(18,4)',
        'FStockOutQty': 'decimal(18,4)',
    },
    'STK_INVENTORY': {
        'FBASEQTY': 'decimal(18,6)',
    },
}

# 生成 SQL 脚本
sql_script = []
sql_script.append("-- ========================================")
sql_script.append("-- 数据库字段精度优化脚本")
sql_script.append("-- 生成时间: 2026-05-07")
sql_script.append("-- 说明: 优化 decimal 字段精度，减少存储空间")
sql_script.append("-- ========================================")
sql_script.append("")
sql_script.append("USE [your_database];")
sql_script.append("GO")
sql_script.append("")

for table, fields in FIELD_OPTIMIZATION_MAP.items():
    sql_script.append(f"-- 优化表: {table}")
    sql_script.append(f"PRINT '正在优化表 {table}...';")

    for field, new_type in fields.items():
        sql_script.append(f"ALTER TABLE [dbo].[{table}] ALTER COLUMN [{field}] {new_type} NULL;")

    sql_script.append("GO")
    sql_script.append("")

sql_script.append("-- ========================================")
sql_script.append("-- 优化完成")
sql_script.append("-- ========================================")
sql_script.append("PRINT '所有字段优化完成！';")
sql_script.append("GO")

# 写入文件
with open('scripts/sql/optimize_decimal_fields.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(sql_script))

print("SQL 脚本已生成: scripts/sql/optimize_decimal_fields.sql")
print(f"涉及 {len(FIELD_OPTIMIZATION_MAP)} 个表")
print(f"涉及 {sum(len(fields) for fields in FIELD_OPTIMIZATION_MAP.values())} 个字段")
