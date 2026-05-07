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

# 检查字段定义
print("字段定义:")
cursor.execute("""
SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'AP_Payable'
AND COLUMN_NAME IN ('FENTRYDISCOUNTRATE', 'FENTRYTAXRATE')
""")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}({row[2]},{row[3]}), 可空: {row[4]}")

# 检查是否有任何非NULL值
print("\n检查非NULL值:")
cursor.execute("""
SELECT COUNT(*) as total,
       SUM(CASE WHEN FENTRYDISCOUNTRATE IS NOT NULL THEN 1 ELSE 0 END) as discount_not_null,
       SUM(CASE WHEN FENTRYTAXRATE IS NOT NULL THEN 1 ELSE 0 END) as tax_not_null,
       SUM(CASE WHEN FENTRYDISCOUNTRATE = 0 THEN 1 ELSE 0 END) as discount_zero,
       SUM(CASE WHEN FENTRYTAXRATE = 0 THEN 1 ELSE 0 END) as tax_zero
FROM AP_Payable
""")
stats = cursor.fetchone()
print(f"  总记录: {stats[0]}")
print(f"  FENTRYDISCOUNTRATE 非NULL: {stats[1]}")
print(f"  FENTRYTAXRATE 非NULL: {stats[2]}")
print(f"  FENTRYDISCOUNTRATE = 0: {stats[3]}")
print(f"  FENTRYTAXRATE = 0: {stats[4]}")

# 查看最近修改的记录
print("\n最近修改的10条记录 (FModifyDate > 2026-05-07 14:00:00):")
cursor.execute("""
SELECT TOP 10
    FBillNo,
    FENTRYDISCOUNTRATE,
    FENTRYTAXRATE,
    FModifyDate
FROM AP_Payable
WHERE FModifyDate > '2026-05-07 14:00:00'
ORDER BY FModifyDate DESC
""")
for row in cursor.fetchall():
    print(f"  {row[0]}: 折扣率={row[1]}, 税率={row[2]}, 修改时间={row[3]}")

cursor.close()
conn.close()
