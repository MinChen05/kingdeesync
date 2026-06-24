import sys
import pyodbc
sys.path.insert(0, '.')

from src.config.config_manager import config_manager

config = config_manager.config

driver = config['SQLSERVER']['driver']
conn_str = (
    f"DRIVER={{{driver}}};"
    f"SERVER={config['SQLSERVER']['host']},{config['SQLSERVER']['port']};"
    f"DATABASE={config['SQLSERVER']['database']};"
    f"UID={config['SQLSERVER']['user']};"
    f"PWD={config['SQLSERVER']['password']};"
)

if "ODBC Driver 18" in driver:
    trust_cert = 'yes' if config['SQLSERVER']['trust_server_certificate'] else 'no'
    encrypt = config['SQLSERVER']['encrypt']
    conn_str += f"TrustServerCertificate={trust_cert};Encrypt={encrypt};"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# 获取所有同步表
cursor.execute("""
SELECT DISTINCT TABLE_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'dbo'
AND TABLE_NAME NOT LIKE '__stage%'
AND TABLE_NAME NOT LIKE 'sync_%'
ORDER BY TABLE_NAME
""")
tables = [row[0] for row in cursor.fetchall()]

print(f"找到 {len(tables)} 个表\n")

# 分析每个表的 decimal 字段
for table in tables:
    cursor.execute(f"""
    SELECT COLUMN_NAME, NUMERIC_PRECISION, NUMERIC_SCALE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = '{table}'
    AND DATA_TYPE = 'decimal'
    ORDER BY ORDINAL_POSITION
    """)

    decimal_fields = cursor.fetchall()
    if decimal_fields:
        print(f"\n{table} 表的 decimal 字段:")
        for field in decimal_fields:
            print(f"  {field[0]}: decimal({field[1]},{field[2]})")

cursor.close()
conn.close()
