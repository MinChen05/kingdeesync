#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金蝶数据同步工具 EXE 打包脚本
使用 PyInstaller 将项目打包成可执行文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def clean_build_dirs():
    """清理之前的构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"正在清理目录: {dir_name}")
            shutil.rmtree(dir_name)
    
    # 清理.spec文件
    spec_files = list(Path('.').glob('*.spec'))
    for spec_file in spec_files:
        print(f"正在删除规格文件: {spec_file}")
        spec_file.unlink()

def create_build_script():
    """创建PyInstaller构建脚本"""
    build_cmd = [
        'pyinstaller',
        '--onedir',                    # 创建一个目录而不是单文件
        '--windowed',                  # Windows GUI应用（不显示控制台）
        '--noconfirm',                 # 覆盖输出目录而不询问
        '--clean',                     # 清理临时文件
        '--name=金蝶数据同步工具',        # 可执行文件名称
        '--icon=NONE',                 # 暂时不设置图标
        '--add-data=config.ini;.',     # 包含配置文件
        '--add-data=使用说明.md;.',     # 包含使用说明
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui', 
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=pymysql',
        '--hidden-import=requests',
        '--hidden-import=schedule',
        '--hidden-import=configparser',
        '--hidden-import=dateutil',
        '--collect-all=PySide6',       # 收集所有PySide6模块
        'kingdee_sync_tool.py'         # 主程序文件
    ]
    
    return build_cmd

def build_exe():
    """执行打包"""
    print("=" * 60)
    print("金蝶数据同步工具 EXE 打包程序")
    print("=" * 60)
    
    # 检查Python版本
    print(f"Python版本: {sys.version}")
    
    # 清理构建目录
    print("\n1. 清理构建目录...")
    clean_build_dirs()
    
    # 检查主文件是否存在
    if not os.path.exists('kingdee_sync_tool.py'):
        print("错误: 找不到主程序文件 kingdee_sync_tool.py")
        return False
    
    # 构建命令
    print("\n2. 开始打包...")
    build_cmd = create_build_script()
    print(f"执行命令: {' '.join(build_cmd)}")
    
    try:
        # 执行打包
        result = subprocess.run(build_cmd, check=True, capture_output=True, text=True)
        print("打包成功!")
        
        # 显示结果
        print(f"\n3. 打包完成!")
        if os.path.exists('dist/金蝶数据同步工具'):
            print("可执行文件位置: dist/金蝶数据同步工具/")
            print("主程序: dist/金蝶数据同步工具/金蝶数据同步工具.exe")
            
            # 创建快捷方式脚本
            create_shortcuts()
            
            return True
        else:
            print("警告: 未找到输出目录")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        print("错误输出:")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        return False

def create_shortcuts():
    """创建快捷方式和启动脚本"""
    dist_dir = Path('dist/金蝶数据同步工具')
    if not dist_dir.exists():
        return
    
    # 创建启动脚本
    launch_script = dist_dir / '启动金蝶数据同步工具.bat'
    with open(launch_script, 'w', encoding='utf-8') as f:
        f.write('@echo off\n')
        f.write('chcp 65001 >nul\n')
        f.write('title 金蝶数据同步工具\n')
        f.write('echo 正在启动金蝶数据同步工具...\n')
        f.write('start "" "金蝶数据同步工具.exe"\n')
    
    print(f"已创建启动脚本: {launch_script}")
    
    # 复制说明文件
    if os.path.exists('使用说明.md'):
        shutil.copy2('使用说明.md', dist_dir / '使用说明.md')
        print("已复制使用说明文档")

def main():
    """主函数"""
    if build_exe():
        print("\n" + "=" * 60)
        print("🎉 打包完成!")
        print("=" * 60)
        print("输出目录: dist/金蝶数据同步工具/")
        print("可执行文件: 金蝶数据同步工具.exe")
        print("启动脚本: 启动金蝶数据同步工具.bat")
        print("\n使用说明:")
        print("1. 将整个 'dist/金蝶数据同步工具' 目录复制到目标机器")
        print("2. 双击 '启动金蝶数据同步工具.bat' 或 '金蝶数据同步工具.exe' 启动程序")
        print("3. 首次运行会自动创建配置文件")
    else:
        print("\n❌ 打包失败，请查看错误信息")

if __name__ == '__main__':
    main()