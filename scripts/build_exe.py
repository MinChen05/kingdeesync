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
        '--onefile',                   # 创建单个可执行文件（更好的兼容性）
        '--windowed',                  # Windows GUI应用（不显示控制台）
        '--noconfirm',                 # 覆盖输出目录而不询问
        '--clean',                     # 清理临时文件
        '--name=金蝶数据同步工具',        # 可执行文件名称
        '--icon=NONE',                 # 暂时不设置图标
        '--add-data=src;src',          # 包含源代码目录
        '--add-data=assets;assets',    # 包含资源文件目录
        '--add-data=config.ini;.',     # 包含根目录配置文件
        '--add-data=docs;docs',        # 包含文档目录
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui', 
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=PySide6.QtSvg',
        '--hidden-import=PySide6.QtPrintSupport',
        '--hidden-import=pymysql',
        '--hidden-import=requests',
        '--hidden-import=schedule',
        '--hidden-import=configparser',
        '--hidden-import=dateutil',
        '--hidden-import=shiboken6',
        '--collect-all=PySide6',       # 收集所有PySide6模块
        '--collect-all=shiboken6',     # 收集所有shiboken6模块
        '--collect-binaries=PySide6',  # 收集PySide6的二进制文件
        '--noupx',                     # 禁用UPX压缩（避免兼容性问题）
        'main.py'                     # 新的主程序入口文件
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
    if not os.path.exists('main.py'):
        print("错误: 找不到主程序文件 main.py")
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
        if os.path.exists('dist/金蝶数据同步工具.exe'):
            print("可执行文件位置: dist/")
            print("主程序: dist/金蝶数据同步工具.exe")
            
            # 创建快捷方式脚本和说明文件
            create_shortcuts()
            
            return True
        else:
            print("警告: 未找到输出文件")
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
    dist_dir = Path('dist')
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
    
    # 创建部署说明文档
    create_deployment_guide(dist_dir)
    print("已创建部署说明文档")

def create_deployment_guide(dist_dir):
    """创建部署说明文档"""
    guide_content = """# 金蝶数据同步工具 - 单文件版部署说明

## 📋 系统要求

### 最低系统要求
- **操作系统**: Windows 7 SP1 / Windows 8.1 / Windows 10 / Windows 11 (64位)
- **内存**: 至少 2GB RAM
- **硬盘空间**: 至少 200MB 可用空间
- **运行库**: Microsoft Visual C++ Redistributable 2015-2022 (x64)
- **网络**: 能够访问金蝶云星空服务器和MySQL数据库的网络连接

## 🚀 部署步骤

### 1. 安装运行库（重要！）
如果目标电脑出现"DLL load failed"错误，请先安装Visual C++ Redistributable：

**下载地址**: https://aka.ms/vs/17/release/vc_redist.x64.exe

或者从Microsoft官网下载：
- 搜索"Microsoft Visual C++ Redistributable"
- 下载最新的x64版本
- 以管理员身份运行安装

### 2. 复制程序文件
将 `金蝶数据同步工具.exe` 复制到目标电脑的任意位置

### 3. 启动程序
有两种启动方式：
- 双击 `启动金蝶数据同步工具.bat`（推荐）
- 直接双击 `金蝶数据同步工具.exe`

### 4. 首次配置
程序首次启动时会自动创建配置文件，请按照界面提示进行配置

## 🔧 故障排除

### 常见问题及解决方案

#### 1. "DLL load failed while importing QtWidgets"
**原因**: 缺少Visual C++ Redistributable运行库
**解决方案**: 
1. 下载并安装 Microsoft Visual C++ Redistributable 2015-2022 (x64)
2. 重启电脑后再次尝试运行程序

#### 2. 程序启动缓慢
**原因**: 单文件程序需要解压到临时目录
**说明**: 这是正常现象，首次启动会较慢，后续启动会快一些

#### 3. 杀毒软件误报
**解决方案**: 将程序添加到杀毒软件的白名单中

## ⚠️ 重要提醒

1. **运行库必装**: 如果目标电脑没有安装Visual C++ Redistributable，程序无法运行
2. **管理员权限**: 首次运行可能需要管理员权限
3. **网络连接**: 确保能访问MySQL数据库和金蝶服务器
4. **防火墙设置**: 确保防火墙允许程序访问网络

---
**版本**: 单文件版 1.0  
**更新日期**: 2025年1月  
**适用系统**: Windows 7/8.1/10/11 (64位)
"""
    
    guide_file = dist_dir / '部署说明.md'
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    # 创建简化版说明
    simple_guide = """===============================================
        金蝶数据同步工具 - 快速部署指南
===============================================

⚠️  重要：如果出现DLL错误，请先安装运行库！

📥 下载运行库：
   https://aka.ms/vs/17/release/vc_redist.x64.exe
   （Microsoft Visual C++ Redistributable 2015-2022 x64）

🚀 部署步骤：
   1. 安装上述运行库
   2. 复制"金蝶数据同步工具.exe"到目标电脑
   3. 双击运行程序
   4. 按提示配置数据库连接

💡 提示：
   ✓ 支持 Windows 7/8.1/10/11 (64位)
   ✓ 首次启动可能较慢（正常现象）
   ✓ 需要管理员权限和网络连接

===============================================
版本：单文件版 1.0 | 更新：2025年1月
==============================================="""
    
    simple_file = dist_dir / '快速部署指南.txt'
    with open(simple_file, 'w', encoding='utf-8') as f:
        f.write(simple_guide)

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