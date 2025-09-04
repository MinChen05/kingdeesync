#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金蝶数据同步工具主程序
Kingdee Data Sync Tool Main Application

作者: AI Assistant
版本: 1.0
创建时间: 2025-08-30
描述: 金蝶系统与MySQL数据库数据同步工具，支持销售订单、销售出库单、预测订单的同步
"""

import sys
import os
import logging
from datetime import datetime

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 导入PySide6模块
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt, QLocale
    from PySide6.QtGui import QFont
except ImportError as e:
    print(f"导入PySide6失败: {e}")
    print("请运行以下命令安装依赖:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# 导入应用模块
try:
    from src.gui.kingdee_sync_gui import KingdeeSyncGUI
    from src.config.config_manager import config_manager
    from src.core.scheduler import auto_scheduler
except ImportError as e:
    print(f"导入应用模块失败: {e}")
    print("请确保所有模块文件都在同一目录下")
    sys.exit(1)

def setup_logging():
    """设置日志系统"""
    log_dir = os.path.join(current_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"sync_tool_{datetime.now().strftime('%Y%m%d')}.log")
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            # 文件处理器
            logging.FileHandler(log_file, encoding='utf-8'),
            # 控制台处理器
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 设置第三方库的日志级别
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('pymysql').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("日志系统初始化完成")
    return logger

def check_dependencies():
    """检查依赖项"""
    logger = logging.getLogger(__name__)
    
    # 检查必需的Python模块
    required_modules = [
        'PySide6',
        'pymysql',
        'requests',
        'schedule',
        'dateutil'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        error_msg = f"缺少必需的Python模块: {', '.join(missing_modules)}"
        logger.error(error_msg)
        print(error_msg)
        print("请运行以下命令安装依赖:")
        print("pip install -r requirements.txt")
        return False
    
    logger.info("所有依赖项检查通过")
    return True

def initialize_application():
    """初始化应用程序"""
    logger = logging.getLogger(__name__)
    
    try:
        # 创建配置文件（如果不存在）
        config_manager.load_config()
        logger.info("配置文件加载完成")
        
        # 初始化数据库表
        from src.core.mysql_manager import mysql_manager
        if mysql_manager.connect():
            if mysql_manager.create_tables(create_tables=False):
                logger.info("跳过数据库表创建，使用现有数据库表")
            else:
                logger.warning("数据库连接检查失败，但程序将继续运行")
        else:
            logger.warning("数据库连接失败，程序将在GUI中提供连接测试功能")
        
        return True
        
    except Exception as e:
        logger.error(f"应用程序初始化失败: {str(e)}")
        return False

def setup_application_style(app):
    """设置应用程序样式"""
    logger = logging.getLogger(__name__)
    
    try:
        # 设置应用程序属性
        app.setApplicationName("金蝶数据同步工具")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("数据同步工具开发团队")
        
        # 设置默认字体
        font = QFont("Microsoft YaHei UI", 9)
        app.setFont(font)
        
        # 启用高DPI支持
        app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # 设置语言环境为中文
        QLocale.setDefault(QLocale.Chinese)
        
        logger.info("应用程序样式设置完成")
        
    except Exception as e:
        logger.warning(f"应用程序样式设置失败: {str(e)}")

def handle_exception(exc_type, exc_value, exc_traceback):
    """全局异常处理器"""
    logger = logging.getLogger(__name__)
    
    if issubclass(exc_type, KeyboardInterrupt):
        # 处理Ctrl+C中断
        logger.info("程序被用户中断")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # 记录异常信息
    logger.error("未捕获的异常", exc_info=(exc_type, exc_value, exc_traceback))
    
    # 显示错误对话框（如果GUI可用）
    try:
        app = QApplication.instance()
        if app:
            error_msg = f"程序发生错误:\n{exc_type.__name__}: {str(exc_value)}"
            QMessageBox.critical(None, "程序错误", error_msg)
    except:
        pass

def cleanup_and_exit():
    """清理资源并退出"""
    logger = logging.getLogger(__name__)
    
    try:
        # 停止调度器
        if auto_scheduler.status.value != "stopped":
            auto_scheduler.stop()
            logger.info("自动同步调度器已停止")
        
        # 关闭数据库连接
        from src.core.mysql_manager import mysql_manager
        mysql_manager.disconnect()
        logger.info("数据库连接已关闭")
        
        # 关闭金蝶API连接
        from src.core.kingdee_api import kingdee_client
        kingdee_client.logout()
        logger.info("金蝶API连接已关闭")
        
        logger.info("程序清理完成")
        
    except Exception as e:
        logger.error(f"程序清理时发生错误: {str(e)}")

def main():
    """主函数"""
    # 设置异常处理器
    sys.excepthook = handle_exception
    
    # 初始化日志系统
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("金蝶数据同步工具启动")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"工作目录: {current_dir}")
    logger.info("=" * 60)
    
    # 检查依赖项
    if not check_dependencies():
        return 1
    
    # 创建QApplication实例
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    setup_application_style(app)
    
    # 初始化应用程序
    if not initialize_application():
        QMessageBox.critical(None, "初始化失败", "应用程序初始化失败，请检查日志文件获取详细信息。")
        return 1
    
    try:
        # 创建主窗口
        main_window = KingdeeSyncGUI()
        
        # 显示主窗口
        main_window.show()
        
        # 加载初始状态
        main_window.load_initial_status()
        
        logger.info("主窗口已显示")
        
        # 进入事件循环
        exit_code = app.exec()
        
        logger.info(f"应用程序退出，退出码: {exit_code}")
        
        return exit_code
        
    except Exception as e:
        logger.error(f"运行主程序时发生错误: {str(e)}")
        QMessageBox.critical(None, "运行错误", f"运行主程序时发生错误:\n{str(e)}")
        return 1
    
    finally:
        # 清理资源
        cleanup_and_exit()

if __name__ == "__main__":
    # 确保在Windows下正确显示中文
    if sys.platform.startswith('win'):
        import locale
        try:
            locale.setlocale(locale.LC_ALL, 'Chinese_China.utf8')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'zh_CN.utf8')
            except:
                pass
    
    # 运行主程序
    exit_code = main()
    sys.exit(exit_code)