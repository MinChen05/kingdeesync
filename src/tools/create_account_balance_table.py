import pyodbc
import sys
import os

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.config_manager import config_manager
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_table():
    db_config = config_manager.get_db_config()
    if db_config['type'] == 'sqlserver':
        config = db_config['sqlserver']
        trust_cert = 'yes' if str(config.get('trust_server_certificate', 'true')).lower() == 'true' else 'no'
        encrypt = 'yes' if str(config.get('encrypt', 'auto')).lower() == 'true' else 'no'
        
        # 使用更稳健的连接字符串构建方式
        conn_str = (
            f"DRIVER={{{config['driver']}}};"
            f"SERVER={config['host']},{config['port']};"
            f"DATABASE={config['database']};"
            f"UID={{{config['user']}}};"
            f"PWD={{{config['password']}}};"
            f"TrustServerCertificate={trust_cert};"
            f"Encrypt={encrypt};"
        )
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            
            # 科目余额表 (GL_RPT_AccountBalance)
            # 根据 FieldKeys 推断字段类型
            # FBALANCEID (String?), FBALANCENAME (String), FDETAILNUMBER (String), FDETAILNAME (String)
            # 其余为金额字段 (Decimal)
            
            table_name = "GL_RPT_AccountBalance"
            drop_sql = f"IF OBJECT_ID('dbo.{table_name}', 'U') IS NOT NULL DROP TABLE dbo.{table_name};"
            
            create_sql = f"""
            CREATE TABLE dbo.{table_name} (
                FBALANCEID NVARCHAR(255),
                FBALANCENAME NVARCHAR(255),
                FDETAILNUMBER NVARCHAR(255),
                FDETAILNAME NVARCHAR(255),
                FBEGINYEARDEBITLOCAL DECIMAL(23, 10),
                FBEGINYEARCREDITLOCAL DECIMAL(23, 10),
                FBEGINDEBIT DECIMAL(23, 10),
                FBEGINDEBITLOCAL DECIMAL(23, 10),
                FBEGINCREDIT DECIMAL(23, 10),
                FBEGINCREDITLOCAL DECIMAL(23, 10),
                FDEBIT DECIMAL(23, 10),
                FDEBITLOCAL DECIMAL(23, 10),
                FCREDIT DECIMAL(23, 10),
                FCREDITLOCAL DECIMAL(23, 10),
                FYTDDEBIT DECIMAL(23, 10),
                FYTDDEBITLOCAL DECIMAL(23, 10),
                FYTDCREDIT DECIMAL(23, 10),
                FYTDCREDITLOCAL DECIMAL(23, 10),
                FENDDEBIT DECIMAL(23, 10),
                FENDDEBITLOCAL DECIMAL(23, 10),
                FENDCREDIT DECIMAL(23, 10),
                FENDCREDITLOCAL DECIMAL(23, 10),
                FPROFITLOCAL DECIMAL(23, 10),
                FYTDPROFITLOCAL DECIMAL(23, 10),
                SYNC_TIME DATETIME DEFAULT GETDATE()
            );
            """
            
            logger.info(f"正在创建表 {table_name}...")
            cursor.execute(drop_sql)
            cursor.execute(create_sql)
            conn.commit()
            logger.info(f"表 {table_name} 创建成功。")
            
        except Exception as e:
            logger.error(f"创建表失败: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
    else:
        logger.error("当前仅支持 SQL Server 数据库创建脚本。")

if __name__ == "__main__":
    create_table()
