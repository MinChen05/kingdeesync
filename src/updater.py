from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROTECTED_NAMES = {"config.local.ini", "config.ini", "config.ini.backup", "logs", "backups"}
PROTECTED_NAME_KEYS = {name.casefold() for name in PROTECTED_NAMES}
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102


@dataclass(frozen=True)
class InstallPlan:
    package_path: Path
    install_dir: Path
    app_exe_name: str


def _is_protected(relative_path: Path) -> bool:
    return bool(relative_path.parts) and relative_path.parts[0].casefold() in PROTECTED_NAME_KEYS


def safe_extract_zip(package_path: Path, extract_dir: Path) -> Path:
    extract_dir.mkdir(parents=True, exist_ok=True)
    extract_root = extract_dir.resolve()

    with zipfile.ZipFile(package_path) as zf:
        for member in zf.infolist():
            target = (extract_dir / member.filename).resolve()
            if target != extract_root and extract_root not in target.parents:
                raise ValueError(f"unsafe zip path: {member.filename}")
        zf.extractall(extract_dir)

    return extract_dir


def _copy_item(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _remove_unprotected_items(install_dir: Path) -> None:
    for item in install_dir.iterdir():
        if item.name.casefold() in PROTECTED_NAME_KEYS:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def _backup_install_dir(install_dir: Path) -> Path:
    backup_root = install_dir / "backups"
    backup_root.mkdir(exist_ok=True)
    backup_dir = backup_root / f"update-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    backup_dir.mkdir()

    for item in install_dir.iterdir():
        if item.name.casefold() in PROTECTED_NAME_KEYS:
            continue
        _copy_item(item, backup_dir / item.name)

    return backup_dir


def _restore_backup(backup_dir: Path, install_dir: Path) -> None:
    _remove_unprotected_items(install_dir)
    for item in backup_dir.iterdir():
        _copy_item(item, install_dir / item.name)


def install_package(plan: InstallPlan) -> None:
    install_dir = plan.install_dir.resolve()
    if not install_dir.exists():
        raise FileNotFoundError(f"安装目录不存在: {install_dir}")
    if not (install_dir / plan.app_exe_name).exists():
        raise FileNotFoundError(f"主程序不存在: {install_dir / plan.app_exe_name}")

    backup_dir = _backup_install_dir(install_dir)
    try:
        with tempfile.TemporaryDirectory(prefix="kingdee-update-") as temp_dir:
            extract_dir = Path(temp_dir) / "package"
            safe_extract_zip(plan.package_path, extract_dir)

            _remove_unprotected_items(install_dir)
            for source in sorted(extract_dir.rglob("*")):
                if source.is_dir():
                    continue
                relative = source.relative_to(extract_dir)
                if _is_protected(relative):
                    continue
                target = install_dir / relative
                if target.exists() and target.is_dir():
                    shutil.rmtree(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    except Exception:
        _restore_backup(backup_dir, install_dir)
        raise


def wait_for_process_exit(pid: int, timeout_seconds: int = 60) -> None:
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return
        try:
            wait_result = kernel32.WaitForSingleObject(handle, int(timeout_seconds * 1000))
        finally:
            kernel32.CloseHandle(handle)
        if wait_result == WAIT_OBJECT_0:
            return
        if wait_result == WAIT_TIMEOUT:
            raise TimeoutError(f"主进程未退出: {pid}")
        raise OSError(f"等待主进程退出失败: {pid}")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.5)
    raise TimeoutError(f"主进程未退出: {pid}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kingdee Sync updater")
    parser.add_argument("--package", required=True, help="已校验更新包 zip 路径")
    parser.add_argument("--install-dir", required=True, help="当前程序安装目录")
    parser.add_argument("--app-exe", default="金蝶数据同步工具.exe", help="主程序文件名")
    parser.add_argument("--pid", type=int, help="需要等待退出的主进程 PID")
    args = parser.parse_args()

    if args.pid:
        wait_for_process_exit(args.pid)

    install_package(
        InstallPlan(
            package_path=Path(args.package),
            install_dir=Path(args.install_dir),
            app_exe_name=args.app_exe,
        )
    )


if __name__ == "__main__":
    main()
