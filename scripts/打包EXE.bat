@echo off
chcp 65001 >nul
title 金蝶数据同步工具 - EXE打包程序

echo.
echo ====================================
echo    金蝶数据同步工具 EXE 打包
echo ====================================
echo.

:: 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请确保Python已正确安装
    pause
    exit /b 1
)

echo [信息] 开始打包程序...

:: 执行打包脚本
python build_exe.py

echo.
echo 打包完成！按任意键查看输出目录...
pause >nul

:: 打开输出目录
if exist "dist\金蝶数据同步工具" (
    start "" "dist\金蝶数据同步工具"
) else (
    echo 未找到输出目录，请检查打包日志
    pause
)