"""检查数据库中的空值和超长数据"""

import os
import sys

import pyodbc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.config_manager import config_manager


def check_db_null_data():
    """检查数据库中的空值"""

    db_config = config_manager.get_db_config()
    if db_config["type"] != "sqlserver":
        print("此脚本仅支持 SQL Server")
        return

    config = db_config["sqlserver"]
    trust_cert = "yes" if str(config.get("trust_server_certificate", "true")).lower() == "true" else "no"
    encrypt = "yes" if str(config.get("encrypt", "false")).lower() == "true" else "no"

    conn_str = (
        f"DRIVER={{{config.get('driver', 'ODBC Driver 17 for SQL Server')}}};"
        f"SERVER={config['host']},{config.get('port', 1433)};"
        f"DATABASE={config['database']};"
        f"UID={config['user']};"
        f"PWD={config['password']};"
        f"TrustServerCertificate={trust_cert};"
        f"Encrypt={encrypt};"
    )

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    print("=" * 60)
    print("检查数据库中的空值")
    print("=" * 60)

    # 检查生产订单主表
    print("\n【生产订单主表 - prd_mo】")
    cursor.execute("SELECT COUNT(*) FROM prd_mo WHERE FBILLNO IS NULL")
    null_count = cursor.fetchone()[0]
    print(f"FBILLNO 为空的记录数: {null_count}")

    if null_count > 0:
        cursor.execute("SELECT TOP 10 FID, FBILLNO, FDATE, FMATERIALNUMBER FROM prd_mo WHERE FBILLNO IS NULL")
        print("\n前10条空数据:")
        for row in cursor.fetchall():
            print(f"  FID: {row[0]}, FBILLNO: {row[1]}, FDATE: {row[2]}, FMATERIALNUMBER: {row[3]}")

    # 检查预测订单
    print("\n【预测订单 - pln_forecast】")
    cursor.execute("""
        SELECT TOP 10 
            FENTRYID,
            LEN(FMATERIALNAME) as name_len,
            LEN(FCUSTNAME) as cust_len,
            LEN(FORA_BASE_FNAME) as base_len
        FROM pln_forecast
        WHERE LEN(FMATERIALNAME) > 256 
           OR LEN(FCUSTNAME) > 256 
           OR LEN(FORA_BASE_FNAME) > 256
    """)

    long_data = cursor.fetchall()
    if long_data:
        print(f"超长字段记录数: {len(long_data)}")
        print("\n前10条超长数据:")
        for row in long_data:
            print(f"  FENTRYID: {row[0]}, 物料名长度: {row[1]}, 客户名长度: {row[2]}, 基地名长度: {row[3]}")
    else:
        print("未发现超长字段")

    # 统计各表记录数
    print("\n【表记录统计】")
    tables = ["prd_mo", "pln_forecast", "saleorder", "sal_outstock", "PUR_PurchaseOrder"]
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} 条")
        except Exception:
            print(f"  {table}: 表不存在或查询失败")

    conn.close()
    print("\n" + "=" * 60)
    print("检查完成")


if __name__ == "__main__":
    try:
        check_db_null_data()
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
