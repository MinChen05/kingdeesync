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

# 查看 AP_Payable 表中所有 decimal 类型字段
print("AP_Payable 表中所有 decimal 类型字段:")
cursor.execute("""
SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'AP_Payable'
AND DATA_TYPE = 'decimal'
ORDER BY ORDINAL_POSITION
""")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}({row[2]},{row[3]})")

# 查看实际数据示例
print("\n实际数据示例（包含金额和比率字段）:")
cursor.execute("""
SELECT TOP 5
    FPRICEQTY,
    FALLAMOUNTFOR_D,
    FNOTAXAMOUNTFOR,
    FDISCOUNTAMOUNTFOR,
    FENTRYDISCOUNTRATE,
    FENTRYTAXRATE
FROM AP_Payable
WHERE FENTRYTAXRATE > 0
ORDER BY FModifyDate DESC
""")
for row in cursor.fetchall():
    print(f"  数量: {row[0]}, 价税合计: {row[1]}, 无税金额: {row[2]}, 折扣额: {row[3]}, 折扣率: {row[4]}, 税率: {row[5]}")

cursor.close()
conn.close()
