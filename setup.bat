@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   金蝶数据同步工具 - 服务器配置
echo ========================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请确保已安装 Python 3.11+ 并添加到 PATH
    pause
    exit /b 1
)

REM 运行配置脚本
python setup_server.py

pause
