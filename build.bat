@echo off
chcp 65001
cd /d "%~dp0"

echo ================================
echo  Kingdee Sync Tool - Build
echo ================================
echo.

pip show pyinstaller
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Building...
echo.

pyinstaller --name="金蝶数据同步工具" --windowed --onedir --add-data="config.ini;." --add-data="assets;assets" --hidden-import=dateutil --hidden-import=pymysql --hidden-import=pyodbc --hidden-import=requests --hidden-import=schedule --hidden-import=PySide6 --hidden-import=cryptography --hidden-import=DBUtils --hidden-import=python_json_logger main.py

echo.
echo Build complete!
echo Output: dist\金蝶数据同步工具
echo.
pause
