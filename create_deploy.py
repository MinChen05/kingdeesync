"""创建服务器部署包。"""

import shutil
from pathlib import Path


def create_deploy_package():
    """创建部署包"""
    print("=" * 50)
    print("  金蝶数据同步工具 - 创建部署包")
    print("=" * 50)
    print()

    # 设置目录
    base_dir = Path(__file__).parent
    deploy_dir = base_dir / "deploy" / "金蝶数据同步工具"
    dist_dir = base_dir / "dist" / "金蝶数据同步工具"

    # 清理旧的部署目录
    if deploy_dir.parent.exists():
        shutil.rmtree(deploy_dir.parent)

    # 创建部署目录
    deploy_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/5] 创建部署目录: {deploy_dir}")

    # 复制程序文件
    if dist_dir.exists():
        print("[2/5] 复制程序文件...")
        shutil.copytree(dist_dir, deploy_dir, dirs_exist_ok=True)
    else:
        print("[2/5] 警告: 未找到打包程序，请先运行 pyinstaller")
        return

    # 复制配置脚本
    print("[3/5] 复制配置脚本...")
    for file in ["setup_server.py", "setup.bat"]:
        src = base_dir / file
        if src.exists():
            shutil.copy2(src, deploy_dir)

    # 复制文档
    print("[4/5] 复制部署文档...")
    for file in ["DEPLOY.md"]:
        src = base_dir / file
        if src.exists():
            shutil.copy2(src, deploy_dir)

    # 复制配置模板，禁止复制本机 config.ini / config.local.ini
    print("[5/5] 复制配置模板...")
    template = base_dir / "config.example.ini"
    if template.exists():
        shutil.copy2(template, deploy_dir / "config.example.ini")
    else:
        print("[5/5] 警告: 未找到 config.example.ini")

    print()
    print("=" * 50)
    print("  部署包创建完成！")
    print("=" * 50)
    print()
    print(f"  部署目录: {deploy_dir}")
    print()
    print("  目录内容:")
    for item in sorted(deploy_dir.iterdir()):
        if item.is_file():
            print(f"    - {item.name}")

    print()
    print("  使用方法:")
    print("  1. 将 deploy/金蝶数据同步工具 文件夹复制到目标服务器")
    print("  2. 运行 setup.bat 生成 config.local.ini")
    print("  3. 启动金蝶数据同步工具.exe")
    print()


if __name__ == "__main__":
    create_deploy_package()
