@echo off
chcp 65001 >nul
echo ========================================
echo 金蝶数据同步工具 - 打包脚本
echo ========================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请确保已安装 Python 并添加到 PATH
    pause
    exit /b 1
)

REM 检查 PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [信息] 正在安装 PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [错误] 安装 PyInstaller 失败
        pause
        exit /b 1
    )
)

REM 清理旧的构建文件
echo [信息] 清理旧的构建文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM 执行打包
echo [信息] 开始打包...
echo.
pyinstaller kingdee_sync.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请检查错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo 打包完成！
echo 输出目录: dist\金蝶数据同步工具
echo ========================================
echo.

REM 只复制配置模板，禁止把本机配置打进发布包
if exist "config.example.ini" (
    echo [信息] 复制配置模板...
    copy "config.example.ini" "dist\金蝶数据同步工具\" >nul
)

REM 创建快捷方式说明
echo [信息] 如需创建桌面快捷方式，请运行:
echo   右键 dist\金蝶数据同步工具\金蝶数据同步工具.exe -^> 发送到 -^> 桌面快捷方式
echo.

pause
