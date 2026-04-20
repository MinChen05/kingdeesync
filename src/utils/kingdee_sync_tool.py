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
if getattr(sys, 'frozen', False):
    current_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
sys.path.insert(0, current_dir)

# 导入PySide6模块
try:
    from PySide6.QtWidgets import QApplication
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
    from src.gui.feedback import UiFeedback
    from src.config.config_manager import config_manager
    from src.core.scheduler import auto_scheduler
    from src.services.sync_service import sync_service
    from src.utils import logger as app_logger
except ImportError as e:
    print(f"导入应用模块失败: {e}")
    print("请确保所有模块文件都在同一目录下")
    sys.exit(1)

def setup_logging():
    """设置日志系统"""
    app_logger.setup_logging()
    
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
        except ImportError as e:
            missing_modules.append(f"{module} ({e})")
            # 调试：写入 debug 文件
            try:
                debug_path = app_logger.get_debug_log_path("debug_startup.txt")
                with open(debug_path, "a") as f:
                    f.write(f"Failed to import {module}: {e}\n")
            except:
                pass
    
    if missing_modules:
        error_msg = f"缺少必需的Python模块: {', '.join(missing_modules)}"
        logger.error(error_msg)
        # 调试：写入 debug 文件
        try:
            debug_path = app_logger.get_debug_log_path("debug_startup.txt")
            with open(debug_path, "a") as f:
                f.write(f"Missing modules: {missing_modules}\n")
        except:
            pass
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
        try:
            repaired = sync_service.repair_stale_sync_runs()
            if repaired:
                logger.warning("Recovered %s stale running sync run(s) during startup", repaired)
        except Exception as repair_exc:
            logger.warning("Failed to repair stale running sync runs during startup: %s", repair_exc)
        logger.info("配置文件加载完成")
        
        # 删除自动建表与字段检查，仅加载配置并由GUI提供连接测试/报错提示
        
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
        app.setStyle("Fusion")
        
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
            error_msg = UiFeedback.build_error_message("程序运行出现异常，请查看日志后重试。", f"{exc_type.__name__}: {exc_value}")
            UiFeedback.error(None, "程序错误", error_msg)
    except:
        pass

def cleanup_and_exit():
    """清理资源并退出"""
    logger = logging.getLogger(__name__)

    from src.core.data_sync import sync_manager

    sync_manager.request_shutdown("application_exit")

    try:
        # 停止调度器
        if auto_scheduler.status.value != "stopped":
            auto_scheduler.stop()
            logger.info("自动同步调度器已停止")
        
        # 关闭数据库连接
        from src.core.mysql_manager import mysql_manager
        mysql_manager.disconnect()
        logger.info("数据库连接已关闭")
        
        # 关闭金蝶API连接（遵循配置：不自动登出，仅停止心跳）
        from src.core.kingdee_api import kingdee_client
        # 先停止心跳线程
        try:
            kingdee_client.stop_keepalive()
        except Exception:
            pass
        kd_cfg = config_manager.get_kingdee_config()
        if kd_cfg.get('auto_logout_on_exit', False):
            kingdee_client.logout()
            logger.info("金蝶API连接已登出并关闭")
        else:
            logger.info("根据配置已跳过自动登出，仅停止心跳")
        
        logger.info("程序清理完成")
        
    except Exception as e:
        logger.error(f"程序清理时发生错误: {str(e)}")

def main():
    """主函数"""
    # 调试路径
    try:
        debug_path = app_logger.get_debug_log_path("debug_startup.txt")
        with open(debug_path, "a") as f:
            f.write("Entered gui_main\n")
    except:
        pass

    # 设置异常处理器
    sys.excepthook = handle_exception
    
    # 初始化日志系统
    logger = setup_logging()
    
    try:
        with open(debug_path, "a") as f:
            f.write("Logging setup complete\n")
    except:
        pass

    logger.info("=" * 60)
    logger.info("=== 启动金蝶数据同步工具 (代码版本: v20260120_Fix_Login_Loop) ===")
    
    # 检查依赖项
    if not check_dependencies():
        try:
            with open(debug_path, "a") as f:
                f.write("Dependencies check failed\n")
        except:
            pass
        return 1
    
    try:
        with open(debug_path, "a") as f:
            f.write("Dependencies check passed\n")
            f.write("Creating QApplication\n")
    except:
        pass

    # 创建QApplication实例
    app = QApplication(sys.argv)
    
    try:
        with open(debug_path, "a") as f:
            f.write("QApplication created\n")
    except:
        pass
        
    # 设置应用程序样式
    setup_application_style(app)
    
    # 初始化应用程序
    if not initialize_application():
        UiFeedback.error(None, "初始化失败", "应用程序初始化失败，请检查日志获取详细信息。")
        return 1
    
    try:
        # 创建主窗口
        main_window = KingdeeSyncGUI()
        
        # 显示主窗口
        main_window.show()
        main_window.raise_()
        main_window.activateWindow()
        
        logger.info(f"主窗口已显示: isVisible={main_window.isVisible()}, geometry={main_window.geometry()}")
        
        try:
            with open(debug_path, "a") as f:
                f.write(f"MainWindow shown, isVisible={main_window.isVisible()}, geometry={main_window.geometry()}\n")
                f.write("Entering exec()\n")
        except:
            pass
            
        # 进入事件循环
        exit_code = app.exec()
        
        try:
            with open(debug_path, "a") as f:
                f.write(f"App exited with code {exit_code}\n")
        except:
            pass
        
        logger.info(f"应用程序退出，退出码: {exit_code}")
        
        return exit_code
        
    except Exception as e:
        logger.error(f"运行主程序时发生错误: {str(e)}")
        UiFeedback.error(None, "运行失败", UiFeedback.build_error_message("主程序启动失败，请检查环境或配置后重试。", e))
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
