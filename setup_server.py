"""金蝶数据同步工具 - 服务器配置脚本。"""

import configparser
import getpass
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.utils.crypto_util import decrypt_password, encrypt_password
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def print_header():
    """打印标题"""
    print("=" * 60)
    print("  金蝶数据同步工具 - 服务器配置向导")
    print("=" * 60)
    print()


def print_section(title):
    """打印章节标题"""
    print(f"\n{'─' * 40}")
    print(f"  {title}")
    print(f"{'─' * 40}")


def get_input(prompt, default=None, required=True):
    """获取用户输入"""
    while True:
        if default:
            value = input(f"{prompt} [{default}]: ").strip()
            if not value:
                return default
        else:
            value = input(f"{prompt}: ").strip()

        if value or not required:
            return value
        print("  ⚠ 此项为必填项，请重新输入")


def get_password(prompt, use_encryption=True):
    """获取密码（支持加密）"""
    password = getpass.getpass(f"{prompt}: ")

    if use_encryption and HAS_CRYPTO and password:
        try:
            encrypted = encrypt_password(password)
            print("  ✓ 密码已加密")
            return encrypted, True
        except Exception as e:
            print(f"  ⚠ 加密失败，将使用明文存储: {e}")
            return password, False
    return password, False


def configure_kingdee():
    """配置金蝶API"""
    print_section("金蝶云星空 API 配置")
    print()

    config = {}

    # API地址
    base_url = get_input("API 域名或IP", "http://192.168.1.100")
    base_url = base_url.rstrip('/')

    config['login_url'] = f"{base_url}/k3cloud/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc"
    config['query_url'] = f"{base_url}/k3cloud/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc"

    print(f"\n  登录地址: {config['login_url']}")
    print(f"  查询地址: {config['query_url']}")

    # 账户信息
    config['acct_id'] = get_input("账套ID (acctID)", "229026784932743936")
    config['username'] = get_input("用户名", "administrator")

    # 密码
    print()
    password, encrypted = get_password("密码")
    config['password'] = password
    config['password_encrypted'] = str(encrypted).lower()

    # 其他配置
    config['lcid'] = "2052"
    config['request_timeout'] = "0"
    config['request_connect_timeout'] = "15"
    config['request_read_timeout'] = "180"
    config['max_request_read_timeout'] = "600"
    config['page_size'] = "100000"
    config['rate_limit_qps'] = "20"
    config['keep_session_alive'] = "true"
    config['keep_alive_interval_secs'] = "600"

    return config


def configure_database():
    """配置数据库"""
    print_section("数据库配置")
    print()

    print("  数据库类型:")
    print("  1. SQL Server (推荐)")
    print("  2. MySQL")
    print()

    db_type = get_input("选择数据库类型", "1")

    if db_type == "1":
        return configure_sqlserver()
    return configure_mysql()


def configure_sqlserver():
    """配置 SQL Server"""
    print()
    config = {'type': 'sqlserver'}

    config['host'] = get_input("服务器地址", "127.0.0.1")
    config['port'] = get_input("端口", "1433")
    config['database'] = get_input("数据库名称", "Kingdee")
    config['user'] = get_input("用户名", "sa")

    # 密码
    print()
    password, encrypted = get_password("密码")
    config['password'] = password
    config['password_encrypted'] = str(encrypted).lower()

    # 驱动
    config['driver'] = get_input("ODBC 驱动", "ODBC Driver 18 for SQL Server")
    config['trust_server_certificate'] = "true"
    config['encrypt'] = "auto"
    config['login_timeout'] = "15"
    config['insert_threads'] = "8"
    config['batch_size'] = "100000"
    config['use_staging'] = "true"

    return config


def configure_mysql():
    """配置 MySQL"""
    print()
    config = {'type': 'mysql'}

    config['host'] = get_input("服务器地址", "127.0.0.1")
    config['port'] = get_input("端口", "3306")
    config['database'] = get_input("数据库名称", "kingdee")
    config['user'] = get_input("用户名", "root")

    # 密码
    print()
    password, encrypted = get_password("密码")
    config['password'] = password
    config['password_encrypted'] = str(encrypted).lower()

    config['charset'] = "utf8mb4"
    config['batch_size'] = "5000"

    return config


def configure_sync():
    """配置同步参数"""
    print_section("同步配置")
    print()

    config = {}
    config['auto_sync'] = "False"
    config['sync_interval'] = get_input("同步间隔（分钟）", "120")
    config['sync_type'] = "incremental"
    config['fetch_concurrency'] = "4"
    config['table_concurrency'] = "8"
    config['time_window_days'] = "30"

    return config


def save_config(kingdee_config, db_config, sync_config):
    """保存配置文件"""
    print_section("保存配置")
    print()

    config = configparser.ConfigParser()

    # 金蝶配置
    config['KINGDEE'] = kingdee_config

    # 数据库配置
    config['DATABASE'] = {'type': db_config['type']}

    if db_config['type'] == 'sqlserver':
        sqlserver_config = {k: v for k, v in db_config.items() if k not in ('type', 'password_encrypted')}
        config['SQLSERVER'] = sqlserver_config
        config['MYSQL'] = {
            'host': '127.0.0.1',
            'user': 'root',
            'password': '',
            'database': 'kingdee',
            'charset': 'utf8mb4',
            'port': '3306',
            'batch_size': '5000'
        }
    else:
        mysql_config = {k: v for k, v in db_config.items() if k not in ('type', 'password_encrypted')}
        config['MYSQL'] = mysql_config
        config['SQLSERVER'] = {
            'host': '127.0.0.1',
            'user': 'sa',
            'password': '',
            'database': 'kingdee',
            'port': '1433',
            'driver': 'ODBC Driver 18 for SQL Server',
            'trust_server_certificate': 'true',
            'encrypt': 'auto'
        }

    # 同步配置
    config['SYNC'] = sync_config

    # GUI配置
    config['GUI'] = {
        'theme': 'blue',
        'window_width': '1200',
        'window_height': '800'
    }

    # 保存文件
    config_path = Path(__file__).parent / 'config.local.ini'

    # 备份旧配置
    if config_path.exists():
        backup_path = config_path.with_suffix('.ini.backup')
        import shutil
        shutil.copy2(config_path, backup_path)
        print(f"  ✓ 已备份旧配置到: {backup_path.name}")

    # 写入新配置
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)

    print(f"  ✓ 配置已保存到: {config_path.name}")

    # 设置文件权限（仅限非Windows系统）
    if os.name != 'nt':
        os.chmod(config_path, 0o600)
        print("  ✓ 已设置配置文件权限为 600（仅所有者可读写）")

    return True


def main():
    """主函数"""
    print_header()

    print("此向导将帮助您配置金蝶数据同步工具。")
    print("配置文件将保存在程序目录下的 config.local.ini 文件中。")
    print()

    # 检查是否已有配置
    config_path = Path(__file__).parent / 'config.local.ini'
    if config_path.exists():
        print("⚠ 检测到已有配置文件，继续将覆盖现有配置。")
        confirm = input("是否继续？(y/n) [n]: ").strip().lower()
        if confirm != 'y':
            print("\n已取消配置。")
            return

    try:
        # 配置金蝶
        kingdee_config = configure_kingdee()

        # 配置数据库
        db_config = configure_database()

        # 配置同步
        sync_config = configure_sync()

        # 保存配置
        print()
        if save_config(kingdee_config, db_config, sync_config):
            print()
            print("=" * 60)
            print("  ✓ 配置完成！")
            print("=" * 60)
            print()
            print("  下一步:")
            print("  1. 确保 SQL Server/MySQL 数据库已创建")
            print("  2. 运行建表脚本（如需要）")
            print("  3. 启动程序: python main.py")
            print()

    except KeyboardInterrupt:
        print("\n\n已取消配置。")
    except Exception as e:
        print(f"\n配置过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
