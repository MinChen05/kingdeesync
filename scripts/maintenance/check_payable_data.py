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

# 检查数据库中的数据
query = """
SELECT TOP 10
    FBillNo,
    FENTRYDISCOUNTRATE,
    FENTRYTAXRATE,
    FModifyDate
FROM AP_Payable
ORDER BY FModifyDate DESC
"""

cursor.execute(query)
rows = cursor.fetchall()

print("数据库中最近的10条记录:")
for row in rows:
    print(f"  单据号: {row[0]}, 折扣率: {row[1]}, 税率: {row[2]}, 修改日期: {row[3]}")

# 统计非空值数量
cursor.execute("""
SELECT
    COUNT(*) as total,
    COUNT(FENTRYDISCOUNTRATE) as discount_count,
    COUNT(FENTRYTAXRATE) as tax_count
FROM AP_Payable
""")
stats = cursor.fetchone()
print(f"\n统计信息:")
print(f"  总记录数: {stats[0]}")
print(f"  FENTRYDISCOUNTRATE 非空: {stats[1]}")
print(f"  FENTRYTAXRATE 非空: {stats[2]}")

cursor.close()
conn.close()
