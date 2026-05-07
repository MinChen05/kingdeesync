"""
修复有索引依赖的字段精度
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
print("修复有索引依赖的字段精度")
print("=" * 80)

# 需要处理的字段和索引
INDEXED_FIELDS = [
    {
        'table': 'pur_purchaseorder',
        'field': 'FQTY',
        'new_type': 'decimal(18,4)',
        'index': 'IX_PUR_PurchaseOrder_Status_Date'
    },
    {
        'table': 'saleorder',
        'field': 'FQTY',
        'new_type': 'decimal(18,4)',
        'index': 'IX_saleorder_main'
    },
    {
        'table': 'STK_INVENTORY',
        'field': 'FBASEQTY',
        'new_type': 'decimal(18,6)',
        'index': 'IX_STK_INVENTORY_FULL_STOCK_DIMS'
    }
]

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    for item in INDEXED_FIELDS:
        table = item['table']
        field = item['field']
        new_type = item['new_type']
        index = item['index']

        print(f"\n处理表: {table}, 字段: {field}")

        # 1. 获取索引定义
        print(f"  获取索引 {index} 的定义...")
        cursor.execute(f"""
        SELECT
            i.is_unique,
            STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) as columns
        FROM sys.indexes i
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        WHERE i.object_id = OBJECT_ID('{table}')
        AND i.name = '{index}'
        GROUP BY i.is_unique
        """)

        result = cursor.fetchone()
        if not result:
            print(f"  [SKIP] 索引 {index} 不存在")
            continue

        is_unique = result[0]
        columns = result[1]
        unique_str = "UNIQUE" if is_unique else ""

        print(f"  索引类型: {unique_str if unique_str else 'NONCLUSTERED'}")
        print(f"  索引列: {columns}")

        # 2. 删除索引
        print(f"  删除索引 {index}...")
        cursor.execute(f"DROP INDEX [{index}] ON [dbo].[{table}]")
        conn.commit()
        print(f"  [OK] 索引已删除")

        # 3. 修改字段精度
        print(f"  修改字段 {field} 精度为 {new_type}...")
        cursor.execute(f"ALTER TABLE [dbo].[{table}] ALTER COLUMN [{field}] {new_type} NULL")
        conn.commit()
        print(f"  [OK] 字段精度已修改")

        # 4. 重建索引
        print(f"  重建索引 {index}...")
        cursor.execute(f"CREATE {unique_str} NONCLUSTERED INDEX [{index}] ON [dbo].[{table}] ({columns})")
        conn.commit()
        print(f"  [OK] 索引已重建")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("所有字段修复完成！")
    print("=" * 80)

except Exception as e:
    print(f"\n执行失败: {str(e)}")
    sys.exit(1)
