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

# Driver 18+ requires explicit Encrypt/TrustServerCertificate
if "ODBC Driver 18" in driver:
    trust_cert = 'yes' if config['SQLSERVER']['trust_server_certificate'] else 'no'
    encrypt = config['SQLSERVER']['encrypt']
    conn_str += f"TrustServerCertificate={trust_cert};Encrypt={encrypt};"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

query = """
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'AP_Payable'
AND COLUMN_NAME IN ('FENTRYDISCOUNTRATE', 'FENTRYTAXRATE')
ORDER BY COLUMN_NAME
"""

cursor.execute(query)
rows = cursor.fetchall()

if rows:
    print("找到以下列:")
    for row in rows:
        print(f"  列名: {row[0]}, 类型: {row[1]}, 长度: {row[2]}, 可空: {row[3]}")
else:
    print("未找到 FENTRYDISCOUNTRATE 和 FENTRYTAXRATE 列")
    print("\n检查 AP_Payable 表的所有列:")
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'AP_Payable'
        ORDER BY ORDINAL_POSITION
    """)
    all_cols = cursor.fetchall()
    for col in all_cols:
        print(f"  {col[0]} ({col[1]})")

cursor.close()
conn.close()
