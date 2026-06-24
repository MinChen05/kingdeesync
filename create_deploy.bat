@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   金蝶数据同步工具 - 服务器部署包制作
echo ========================================
echo.

REM 设置变量
set DEPLOY_DIR=deploy\金蝶数据同步工具
set DIST_DIR=dist\金蝶数据同步工具

REM 清理旧的部署目录
if exist "deploy" rmdir /s /q "deploy"

REM 创建部署目录
echo [1/5] 创建部署目录...
mkdir "%DEPLOY_DIR%"

REM 复制程序文件
echo [2/5] 复制程序文件...
xcopy "%DIST_DIR%" "%DEPLOY_DIR%" /E /I /H /Y >nul

REM 复制配置脚本
echo [3/5] 复制配置脚本...
copy "setup_server.py" "%DEPLOY_DIR%\" >nul
copy "setup.bat" "%DEPLOY_DIR%\" >nul

REM 复制文档
echo [4/5] 复制部署文档...
copy "DEPLOY.md" "%DEPLOY_DIR%\" >nul

REM 复制配置模板，禁止复制本机 config.ini / config.local.ini
echo [5/5] 复制配置模板...
copy "config.example.ini" "%DEPLOY_DIR%\" >nul

echo.
echo ========================================
echo   部署包制作完成！
echo ========================================
echo.
echo   部署目录: %DEPLOY_DIR%
echo.
echo   目录内容:
dir /b "%DEPLOY_DIR%"
echo.
echo   使用方法:
echo   1. 将 %DEPLOY_DIR% 文件夹复制到目标服务器
echo   2. 运行 setup.bat 生成 config.local.ini
echo   3. 启动金蝶数据同步工具.exe
echo.
pause
