@echo off
chcp 65001 >nul
title 金蝶数据同步工具

echo ====================================
echo    金蝶数据同步工具 v1.0
echo ====================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装Python 3.11或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [信息] Python版本检查通过

:: 检查是否存在虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo [信息] 检测到虚拟环境，正在激活...
    call venv\Scripts\activate.bat
) else (
    echo [信息] 未检测到虚拟环境，使用系统Python环境
)

:: 检查依赖是否安装
echo [信息] 检查依赖包...
python -c "import PySide6, pymysql, requests, schedule, dateutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 检测到缺少依赖包，正在自动安装...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 依赖包安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo [信息] 依赖包安装完成
) else (
    echo [信息] 依赖包检查通过
)

:: 创建日志目录
if not exist "logs" mkdir logs

echo [信息] 正在启动金蝶数据同步工具...
echo.

:: 启动主程序
python kingdee_sync_tool.py

:: 检查程序退出状态
if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出，退出码: %errorlevel%
    echo 请检查日志文件获取详细错误信息
) else (
    echo.
    echo [信息] 程序正常退出
)

echo.
echo 按任意键退出...
pause >nul