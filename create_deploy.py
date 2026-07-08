"""创建服务器部署包。"""

import hashlib
import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

from src.version import APP_CHANNEL, APP_NAME, APP_VERSION

RELEASE_EXCLUDES = {"config.ini", "config.local.ini", "config.ini.backup", "logs"}
DEFAULT_RELEASE_BASE_URL = "https://intranet.example.com/kingdee-sync/updates/stable"


def should_exclude_from_release(path: Path) -> bool:
    """判断路径是否应从在线更新 release 包排除。"""
    return bool(path.parts) and path.parts[0].lower() in RELEASE_EXCLUDES


def create_update_release(deploy_dir: Path, version: str, base_url: str) -> None:
    """生成在线更新完整包、SHA256 和 latest.json。"""
    release_dir = deploy_dir.parent / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    zip_path = release_dir / f"{APP_NAME}-{version}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in deploy_dir.rglob("*"):
            if item.is_dir():
                continue
            relative = item.relative_to(deploy_dir)
            if should_exclude_from_release(relative):
                continue
            zf.write(item, relative.as_posix())

    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    latest = {
        "app": APP_NAME,
        "version": version,
        "channel": APP_CHANNEL,
        "release_date": date.today().isoformat(),
        "min_supported_version": "1.0.0",
        "package_url": f"{base_url.rstrip('/')}/{zip_path.name}",
        "sha256": sha256,
        "size": zip_path.stat().st_size,
        "force": False,
        "notes": [],
    }
    latest_path = release_dir / "latest.json"
    latest_path.write_text(
        json.dumps(latest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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

    create_update_release(deploy_dir, APP_VERSION, DEFAULT_RELEASE_BASE_URL)

    print()
    print("=" * 50)
    print("  部署包创建完成！")
    print("=" * 50)
    print()
    print(f"  部署目录: {deploy_dir}")
    print(f"  在线更新目录: {deploy_dir.parent / 'release'}")
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
