"""
执行数据库字段精度优化脚本
"""
import sys
import pyodbc
sys.path.insert(0, '.')

from src.config.config_manager import config_manager

config = config_manager.config

driver = config['SQLSERVER']['driver']
database = config['SQLSERVER']['database']

conn_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER={config['SQLSERVER']['host']},{config['SQLSERVER']['port']};"
    f"DATABASE={database};"
    f"UID={config['SQLSERVER']['user']};"
    f"PWD={config['SQLSERVER']['password']};"
)

if "ODBC Driver 18" in driver or "ODBC Driver 17" in driver:
    trust_cert = 'yes' if config['SQLSERVER']['trust_server_certificate'] else 'no'
    conn_str += f"TrustServerCertificate={trust_cert};"

print("=" * 80)
print("数据库字段精度优化执行脚本")
print("=" * 80)
print(f"\n数据库: {database}")
print(f"服务器: {config['SQLSERVER']['host']}:{config['SQLSERVER']['port']}")
print("\n警告: 此操作将修改 11 个表的 49 个字段的精度")
print("\n开始执行优化...")

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

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

    total_tables = len(FIELD_OPTIMIZATION_MAP)
    total_fields = sum(len(fields) for fields in FIELD_OPTIMIZATION_MAP.values())

    print(f"\n涉及表数量: {total_tables}")
    print(f"涉及字段数量: {total_fields}\n")

    success_count = 0
    error_count = 0

    for table, fields in FIELD_OPTIMIZATION_MAP.items():
        print(f"\n正在优化表: {table}")

        for field, new_type in fields.items():
            try:
                sql = f"ALTER TABLE [dbo].[{table}] ALTER COLUMN [{field}] {new_type} NULL"
                cursor.execute(sql)
                conn.commit()
                print(f"  [OK] {field}: {new_type}")
                success_count += 1
            except Exception as e:
                print(f"  [FAIL] {field}: 失败 - {str(e)}")
                error_count += 1

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("优化完成！")
    print("=" * 80)
    print(f"成功: {success_count} 个字段")
    print(f"失败: {error_count} 个字段")
    print("=" * 80)

    if error_count == 0:
        print("\n建议执行以下操作:")
        print("1. 重建索引以优化性能")
        print("2. 更新统计信息")
        print("3. 验证数据完整性")

except Exception as e:
    print(f"\n执行失败: {str(e)}")
    sys.exit(1)
