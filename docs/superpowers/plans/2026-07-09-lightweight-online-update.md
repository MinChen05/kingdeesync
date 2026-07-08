---
change: add-lightweight-online-update
design-doc: docs/superpowers/specs/2026-07-09-lightweight-online-update-design.md
base-ref: fcc1b690e0d9d39c03f7661c529f9d96601f1517
---

# Lightweight Online Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为金蝶数据同步桌面端新增手动在线更新能力，使用内网 HTTPS 静态 `latest.json`、完整 zip 包、独立 updater、本地配置保护和失败回滚。（原因：这是当前项目风险最低的最小可行升级路径）

**Architecture:** 新增 `UpdateService` 承担 manifest 校验、版本比较、下载和 SHA256 校验；GUI 只展示状态并触发服务；独立 `src/updater.py` 在主进程退出后完成安全解压、备份、替换和回滚。（原因：更新逻辑、界面状态、高风险文件替换必须分层隔离）

**Tech Stack:** Python 3.11、PySide6、标准库 `urllib.request`、`hashlib`、`zipfile`、`tempfile`、`shutil`、`subprocess`、PyInstaller、pytest/unittest。（原因：第一版不引入新第三方依赖，降低打包兼容风险）

---

## File Structure

- Create: `src/version.py`
  - 保存 `APP_VERSION`、`APP_CHANNEL` 和版本访问函数。（原因：GUI、服务、发布脚本需要统一版本来源）
- Create: `src/services/update_service.py`
  - 定义 manifest 数据结构、版本比较、manifest 校验、下载、SHA256 校验和安装移交流程。（原因：非 GUI 更新逻辑应集中且可测试）
- Create: `src/updater.py`
  - 独立进程入口，负责等待主程序退出、安全解压、备份替换、保护本地文件、失败回滚。（原因：主程序无法可靠覆盖正在运行的 exe/dll）
- Modify: `src/gui/pages/settings_page.py`
  - 增加当前版本展示、检查更新按钮和用户反馈。（原因：设置页是当前最自然的系统级入口）
- Create: `tests/test_update_service.py`
  - 覆盖版本比较、manifest 校验、HTTPS 限制、hash 分支、网络失败。（原因：更新入口安全性必须可自动化验证）
- Create: `tests/test_updater_dry_run.py`
  - 在临时目录验证 zip-slip 拒绝、配置保护、回滚行为。（原因：文件替换逻辑风险高，必须 dry-run）
- Modify: `tests/test_gui_windows11_shell.py`
  - 使用 mock 覆盖设置页更新状态。（原因：GUI 测试不能依赖真实网络）
- Modify: `create_deploy.py`
  - 生成完整 release zip、SHA256 和 `latest.json` 示例，并排除本机配置与日志。（原因：发布产物必须和校验信息一致）
- Modify: `DEPLOY.md`
  - 增加在线更新发布步骤和 SQL Server 影响说明。（原因：现场发布需要零歧义步骤）
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`
  - 按任务完成情况勾选。（原因：保持 OpenSpec 任务状态可追溯）

---

### Task 1: Version Source And Manifest Validation

**Files:**
- Create: `src/version.py`
- Create: `src/services/update_service.py`
- Create: `tests/test_update_service.py`
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`

- [ ] **Step 1: Write failing version and manifest tests**

Create `tests/test_update_service.py`:

```python
from __future__ import annotations

import pytest

from src.services.update_service import ManifestValidationError, UpdateManifest, compare_versions, parse_manifest


VALID_MANIFEST = {
    "app": "kingdee-sync",
    "version": "1.4.0",
    "channel": "stable",
    "release_date": "2026-07-09",
    "min_supported_version": "1.0.0",
    "package_url": "https://intranet.example.com/releases/kingdee-sync-1.4.0.zip",
    "sha256": "a" * 64,
    "size": 123,
    "force": False,
    "notes": ["修复同步异常提示"],
}


def test_compare_versions_handles_multi_digit_parts() -> None:
    assert compare_versions("1.10.0", "1.9.9") > 0
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.0", "1.0.1") < 0


def test_parse_manifest_accepts_valid_manifest() -> None:
    manifest = parse_manifest(VALID_MANIFEST)

    assert isinstance(manifest, UpdateManifest)
    assert manifest.version == "1.4.0"
    assert manifest.package_url.startswith("https://")


def test_parse_manifest_rejects_non_https_package_url() -> None:
    data = dict(VALID_MANIFEST)
    data["package_url"] = "http://intranet.example.com/releases/kingdee-sync-1.4.0.zip"

    with pytest.raises(ManifestValidationError, match="HTTPS"):
        parse_manifest(data)


def test_parse_manifest_rejects_bad_sha256() -> None:
    data = dict(VALID_MANIFEST)
    data["sha256"] = "bad"

    with pytest.raises(ManifestValidationError, match="sha256"):
        parse_manifest(data)


def test_parse_manifest_rejects_wrong_app() -> None:
    data = dict(VALID_MANIFEST)
    data["app"] = "other-app"

    with pytest.raises(ManifestValidationError, match="app"):
        parse_manifest(data)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_update_service.py -q
```

Expected: FAIL because `src.services.update_service` does not exist.

- [ ] **Step 3: Add local version source**

Create `src/version.py`:

```python
from __future__ import annotations

APP_NAME = "kingdee-sync"
APP_VERSION = "1.0.0"
APP_CHANNEL = "stable"


def get_app_version() -> str:
    return APP_VERSION


def get_app_channel() -> str:
    return APP_CHANNEL
```

- [ ] **Step 4: Add manifest parsing and version comparison**

Create `src/services/update_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from src.version import APP_NAME


class ManifestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class UpdateManifest:
    app: str
    version: str
    channel: str
    release_date: str
    min_supported_version: str
    package_url: str
    sha256: str
    size: int
    force: bool
    notes: tuple[str, ...]


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise ManifestValidationError(f"版本号格式无效: {value}")
    try:
        return tuple(int(part) for part in parts)  # type: ignore[return-value]
    except ValueError as exc:
        raise ManifestValidationError(f"版本号格式无效: {value}") from exc


def compare_versions(left: str, right: str) -> int:
    left_tuple = _version_tuple(left)
    right_tuple = _version_tuple(right)
    return (left_tuple > right_tuple) - (left_tuple < right_tuple)


def parse_manifest(data: dict[str, Any]) -> UpdateManifest:
    if data.get("app") != APP_NAME:
        raise ManifestValidationError("manifest app 不匹配")

    version = str(data.get("version", ""))
    min_supported_version = str(data.get("min_supported_version", ""))
    _version_tuple(version)
    _version_tuple(min_supported_version)

    package_url = str(data.get("package_url", ""))
    parsed = urlparse(package_url)
    if parsed.scheme.lower() != "https":
        raise ManifestValidationError("package_url 必须使用 HTTPS")

    sha256 = str(data.get("sha256", ""))
    if len(sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in sha256):
        raise ManifestValidationError("sha256 必须是 64 位十六进制字符串")

    size = data.get("size")
    if not isinstance(size, int) or size <= 0:
        raise ManifestValidationError("size 必须是正整数")

    notes_raw = data.get("notes", [])
    if not isinstance(notes_raw, list) or not all(isinstance(item, str) for item in notes_raw):
        raise ManifestValidationError("notes 必须是字符串数组")

    return UpdateManifest(
        app=APP_NAME,
        version=version,
        channel=str(data.get("channel", "stable")),
        release_date=str(data.get("release_date", "")),
        min_supported_version=min_supported_version,
        package_url=package_url,
        sha256=sha256.lower(),
        size=size,
        force=bool(data.get("force", False)),
        notes=tuple(notes_raw),
    )
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python -m pytest tests/test_update_service.py -q
```

Expected: PASS.

Commit:

```bash
git add src/version.py src/services/update_service.py tests/test_update_service.py openspec/changes/add-lightweight-online-update/tasks.md
git commit -m "feat(update): add manifest validation"
```

---

### Task 2: Update Service Fetch, Download, And Hash Verification

**Files:**
- Modify: `src/services/update_service.py`
- Modify: `tests/test_update_service.py`
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`

- [ ] **Step 1: Add failing service tests**

Append to `tests/test_update_service.py`:

```python
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from src.services.update_service import UpdateService


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


def test_check_for_update_reports_no_update() -> None:
    payload = json.dumps({**VALID_MANIFEST, "version": "1.0.0"}).encode("utf-8")
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.0.0")

    with patch("src.services.update_service.urlopen", return_value=FakeResponse(payload)):
        result = service.check_for_update()

    assert result.update_available is False
    assert result.manifest.version == "1.0.0"


def test_check_for_update_reports_newer_version() -> None:
    payload = json.dumps(VALID_MANIFEST).encode("utf-8")
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with patch("src.services.update_service.urlopen", return_value=FakeResponse(payload)):
        result = service.check_for_update()

    assert result.update_available is True
    assert result.manifest.version == "1.4.0"


def test_download_package_verifies_sha256(tmp_path: Path) -> None:
    package_bytes = b"release package"
    sha256 = hashlib.sha256(package_bytes).hexdigest()
    manifest = parse_manifest({**VALID_MANIFEST, "sha256": sha256, "size": len(package_bytes)})
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with patch("src.services.update_service.urlopen", return_value=FakeResponse(package_bytes)):
        package_path = service.download_package(manifest, tmp_path)

    assert package_path.exists()
    assert package_path.read_bytes() == package_bytes
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_update_service.py -q
```

Expected: FAIL because `UpdateService` and result types are missing.

- [ ] **Step 3: Implement service methods**

Append/modify `src/services/update_service.py`:

```python
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from src.version import get_app_version


class UpdateServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateCheckResult:
    update_available: bool
    manifest: UpdateManifest


class UpdateService:
    def __init__(self, manifest_url: str, current_version: str | None = None, timeout_seconds: int = 5):
        if urlparse(manifest_url).scheme.lower() != "https":
            raise ManifestValidationError("manifest_url 必须使用 HTTPS")
        self.manifest_url = manifest_url
        self.current_version = current_version or get_app_version()
        self.timeout_seconds = timeout_seconds

    def check_for_update(self) -> UpdateCheckResult:
        try:
            with urlopen(self.manifest_url, timeout=self.timeout_seconds) as response:
                payload = response.read()
        except Exception as exc:
            raise UpdateServiceError(f"检查更新失败: {exc}") from exc

        try:
            data = json.loads(payload.decode("utf-8"))
            manifest = parse_manifest(data)
        except Exception as exc:
            raise UpdateServiceError(f"更新元数据无效: {exc}") from exc

        return UpdateCheckResult(
            update_available=compare_versions(manifest.version, self.current_version) > 0,
            manifest=manifest,
        )

    def download_package(self, manifest: UpdateManifest, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        package_path = target_dir / f"kingdee-sync-{manifest.version}.zip"

        try:
            with urlopen(manifest.package_url, timeout=self.timeout_seconds) as response:
                package_bytes = response.read()
        except Exception as exc:
            raise UpdateServiceError(f"下载更新包失败: {exc}") from exc

        package_path.write_bytes(package_bytes)
        actual_hash = hashlib.sha256(package_bytes).hexdigest()
        if actual_hash.lower() != manifest.sha256.lower():
            package_path.unlink(missing_ok=True)
            raise UpdateServiceError("更新包 sha256 校验失败")

        return package_path
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
python -m pytest tests/test_update_service.py -q
```

Expected: PASS.

Commit:

```bash
git add src/services/update_service.py tests/test_update_service.py openspec/changes/add-lightweight-online-update/tasks.md
git commit -m "feat(update): download verified release package"
```

---

### Task 3: Independent Updater Dry-Run Core

**Files:**
- Create: `src/updater.py`
- Create: `tests/test_updater_dry_run.py`
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`

- [ ] **Step 1: Write failing updater dry-run tests**

Create `tests/test_updater_dry_run.py`:

```python
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from src.updater import InstallPlan, install_package, safe_extract_zip


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_safe_extract_rejects_zip_slip(tmp_path: Path) -> None:
    package = tmp_path / "bad.zip"
    make_zip(package, {"../evil.txt": b"evil"})

    with pytest.raises(ValueError, match="unsafe"):
        safe_extract_zip(package, tmp_path / "extract")


def test_install_preserves_local_config_and_logs(tmp_path: Path) -> None:
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    (install_dir / "金蝶数据同步工具.exe").write_bytes(b"old")
    (install_dir / "config.local.ini").write_text("local", encoding="utf-8")
    (install_dir / "logs").mkdir()
    (install_dir / "logs" / "app.log").write_text("log", encoding="utf-8")

    package = tmp_path / "new.zip"
    make_zip(
        package,
        {
            "金蝶数据同步工具.exe": b"new",
            "config.local.ini": b"wrong",
            "logs/app.log": b"wrong",
        },
    )

    plan = InstallPlan(package_path=package, install_dir=install_dir, app_exe_name="金蝶数据同步工具.exe")
    install_package(plan)

    assert (install_dir / "金蝶数据同步工具.exe").read_bytes() == b"new"
    assert (install_dir / "config.local.ini").read_text(encoding="utf-8") == "local"
    assert (install_dir / "logs" / "app.log").read_text(encoding="utf-8") == "log"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_updater_dry_run.py -q
```

Expected: FAIL because `src.updater` does not exist.

- [ ] **Step 3: Implement safe extract and protected install**

Create `src/updater.py`:

```python
from __future__ import annotations

import argparse
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


PROTECTED_NAMES = {"config.local.ini", "config.ini", "config.ini.backup", "logs", "backups"}


@dataclass(frozen=True)
class InstallPlan:
    package_path: Path
    install_dir: Path
    app_exe_name: str


def _is_protected(path: Path) -> bool:
    return bool(path.parts) and path.parts[0] in PROTECTED_NAMES


def safe_extract_zip(package_path: Path, extract_dir: Path) -> Path:
    extract_dir.mkdir(parents=True, exist_ok=True)
    root = extract_dir.resolve()
    with zipfile.ZipFile(package_path) as zf:
        for member in zf.infolist():
            target = (extract_dir / member.filename).resolve()
            if root not in (target, *target.parents):
                raise ValueError(f"unsafe zip path: {member.filename}")
        zf.extractall(extract_dir)
    return extract_dir


def _backup_install_dir(install_dir: Path) -> Path:
    backup_root = install_dir / "backups"
    backup_root.mkdir(exist_ok=True)
    backup_dir = backup_root / f"update-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    backup_dir.mkdir()
    for item in install_dir.iterdir():
        if item.name in PROTECTED_NAMES:
            continue
        target = backup_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    return backup_dir


def _restore_backup(backup_dir: Path, install_dir: Path) -> None:
    for item in backup_dir.iterdir():
        target = install_dir / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def install_package(plan: InstallPlan) -> None:
    install_dir = plan.install_dir.resolve()
    if not install_dir.exists():
        raise FileNotFoundError(f"安装目录不存在: {install_dir}")

    extract_dir = install_dir / ".update_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    safe_extract_zip(plan.package_path, extract_dir)

    backup_dir = _backup_install_dir(install_dir)
    try:
        for source in extract_dir.rglob("*"):
            if source.is_dir():
                continue
            relative = source.relative_to(extract_dir)
            if _is_protected(relative):
                continue
            target = install_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    except Exception:
        _restore_backup(backup_dir, install_dir)
        raise
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def wait_for_process_exit(pid: int, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            import os

            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.5)
    raise TimeoutError(f"主进程未退出: {pid}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kingdee Sync updater")
    parser.add_argument("--package", required=True)
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--app-exe", default="金蝶数据同步工具.exe")
    parser.add_argument("--pid", type=int)
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
```

- [ ] **Step 4: Run updater tests and commit**

Run:

```bash
python -m pytest tests/test_updater_dry_run.py -q
```

Expected: PASS.

Commit:

```bash
git add src/updater.py tests/test_updater_dry_run.py openspec/changes/add-lightweight-online-update/tasks.md
git commit -m "feat(update): add independent updater dry run"
```

---

### Task 4: GUI Settings Entry

**Files:**
- Modify: `src/gui/pages/settings_page.py`
- Modify: `tests/test_gui_windows11_shell.py`
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`

- [ ] **Step 1: Add failing GUI assertions**

Append to `tests/test_gui_windows11_shell.py` near existing settings page tests:

```python
def test_settings_page_shows_version_and_update_button(self) -> None:
    window = self._create_window()
    page = window.pages["settings"]

    self.assertIn("当前版本", page.version_label.text())
    self.assertEqual(page.btn_check_update.text(), "检查更新")
```

- [ ] **Step 2: Run focused GUI test and verify failure**

Run:

```bash
python -m pytest tests/test_gui_windows11_shell.py -q -k "settings_page_shows_version"
```

Expected: FAIL because the settings page has no version/update widgets.

- [ ] **Step 3: Add version display and update button**

Modify `src/gui/pages/settings_page.py` imports:

```python
import tempfile
from pathlib import Path

from src.services.update_service import UpdateService, UpdateServiceError
from src.version import get_app_version
```

Add rows to `basic_rows`:

```python
self.version_label = self._make_info_label(f"当前版本：{get_app_version()}")
self.btn_check_update = LoadingButton("检查更新")
self.btn_check_update.setProperty("class", "secondary")
self.btn_check_update.setFixedHeight(34)
self.btn_check_update.clicked.connect(self.check_update)

basic_rows = [
    self._create_setting_row("系统名称", "用于标识本系统的名称", self._make_info_label("金蝶数据同步工具")),
    self._create_setting_row("当前版本", "当前客户端程序版本", self.version_label),
    self._create_setting_row("在线更新", "从内网 HTTPS 地址检查新版本", self.btn_check_update),
    self._create_setting_row("配置来源", "当前读写的配置文件", self._make_info_label(settings_service.get_config_source_name())),
    self._create_setting_row("数据库类型", "当前同步使用的数据库类型", self._make_info_label(settings_service.get_database_type())),
]
```

Add method:

```python
def check_update(self) -> None:
    self.btn_check_update.set_loading(True, "检查中...")
    try:
        service = UpdateService("https://intranet.example.com/kingdee-sync/updates/stable/latest.json")
        result = service.check_for_update()
        if not result.update_available:
            UiFeedback.info(self, "检查更新", "当前已是最新版本。")
            return
        notes = "\n".join(f"- {note}" for note in result.manifest.notes)
        UiFeedback.info(
            self,
            "发现新版本",
            f"版本：{result.manifest.version}\n发布日期：{result.manifest.release_date}\n{notes}",
        )
    except (UpdateServiceError, Exception) as exc:
        logger.error("Check update failed: %s", exc)
        UiFeedback.error(self, "检查更新失败", f"无法检查更新：\n{exc}")
    finally:
        self.btn_check_update.set_loading(False)
```

- [ ] **Step 4: Run focused GUI test and commit**

Run:

```bash
python -m pytest tests/test_gui_windows11_shell.py -q -k "settings_page_shows_version"
```

Expected: PASS.

Commit:

```bash
git add src/gui/pages/settings_page.py tests/test_gui_windows11_shell.py openspec/changes/add-lightweight-online-update/tasks.md
git commit -m "feat(update): add settings update entry"
```

---

### Task 5: Release Package And Documentation

**Files:**
- Modify: `create_deploy.py`
- Modify: `DEPLOY.md`
- Create: `tests/test_release_package.py`
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`

- [ ] **Step 1: Add failing package tests**

Create `tests/test_release_package.py`:

```python
from pathlib import Path

from create_deploy import should_exclude_from_release


def test_release_package_excludes_local_config_and_logs() -> None:
    excluded = [
        Path("config.ini"),
        Path("config.local.ini"),
        Path("config.ini.backup"),
        Path("logs/app.log"),
    ]
    included = [
        Path("金蝶数据同步工具.exe"),
        Path("config.example.ini"),
        Path("DEPLOY.md"),
    ]

    assert all(should_exclude_from_release(path) for path in excluded)
    assert not any(should_exclude_from_release(path) for path in included)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python -m pytest tests/test_release_package.py -q
```

Expected: FAIL because `should_exclude_from_release` does not exist.

- [ ] **Step 3: Add release exclusion helper**

Modify `create_deploy.py`:

```python
import hashlib
import json
import zipfile


RELEASE_EXCLUDES = {"config.ini", "config.local.ini", "config.ini.backup", "logs"}


def should_exclude_from_release(path: Path) -> bool:
    return bool(path.parts) and path.parts[0] in RELEASE_EXCLUDES
```

Add release package function:

```python
def create_update_release(deploy_dir: Path, version: str, base_url: str) -> None:
    release_dir = deploy_dir.parent / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    zip_path = release_dir / f"kingdee-sync-{version}.zip"

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
        "app": "kingdee-sync",
        "version": version,
        "channel": "stable",
        "release_date": "",
        "min_supported_version": "1.0.0",
        "package_url": f"{base_url.rstrip('/')}/{zip_path.name}",
        "sha256": sha256,
        "size": zip_path.stat().st_size,
        "force": False,
        "notes": [],
    }
    (release_dir / "latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Document publishing steps**

Append to `DEPLOY.md`:

```markdown
## 在线更新发布

第一版在线更新使用内网 HTTPS 静态 `latest.json` 和完整 zip 包。（原因：不需要新增服务端程序，便于服务器部署）

发布步骤：

1. 运行 `build_exe.bat` 生成 PyInstaller 输出。（原因：确保 release zip 包含最新程序文件）
2. 运行 `python create_deploy.py` 生成部署目录和 release 产物。（原因：由脚本统一生成 zip、SHA256 和 manifest，避免人工填错）
3. 将 `deploy/release/latest.json` 和 `deploy/release/kingdee-sync-<version>.zip` 上传到内网 HTTPS 静态目录。（原因：客户端只信任 HTTPS manifest 和包地址）
4. 确认发布包不包含 `config.ini`、`config.local.ini`、`config.ini.backup`、`logs/`。（原因：避免覆盖现场配置和泄露敏感信息）

数据库影响：在线更新流程不改 SQL Server 表结构，不执行 SQL 脚本，不写同步业务表。（原因：数据库变更必须走独立评审、备份和行数校验）
```

- [ ] **Step 5: Run package test and commit**

Run:

```bash
python -m pytest tests/test_release_package.py -q
```

Expected: PASS.

Commit:

```bash
git add create_deploy.py DEPLOY.md tests/test_release_package.py openspec/changes/add-lightweight-online-update/tasks.md
git commit -m "build(update): generate online release metadata"
```

---

### Task 6: Verification

**Files:**
- Modify: `openspec/changes/add-lightweight-online-update/tasks.md`
- Create: `docs/superpowers/reports/2026-07-09-lightweight-online-update-verify.md`

- [ ] **Step 1: Run lint**

Run:

```bash
python -m ruff check src/version.py src/services/update_service.py src/updater.py create_deploy.py tests/test_update_service.py tests/test_updater_dry_run.py tests/test_release_package.py
```

Expected: PASS.

- [ ] **Step 2: Run update tests**

Run:

```bash
python -m pytest tests/test_update_service.py tests/test_updater_dry_run.py tests/test_release_package.py -q
```

Expected: PASS.

- [ ] **Step 3: Run GUI-focused test**

Run:

```bash
python -m pytest tests/test_gui_windows11_shell.py -q -k "settings_page_shows_version"
```

Expected: PASS.

- [ ] **Step 4: Run updater dry-run with protected files**

Run:

```bash
python -m pytest tests/test_updater_dry_run.py -q
```

Expected: PASS and confirm `config.local.ini` plus `logs/app.log` remain unchanged in the test install directory.

- [ ] **Step 5: Create verification report**

Create `docs/superpowers/reports/2026-07-09-lightweight-online-update-verify.md`:

```markdown
# 轻量在线更新验证报告

## 自动化验证

- `python -m ruff check ...`：通过。
- `python -m pytest tests/test_update_service.py tests/test_updater_dry_run.py tests/test_release_package.py -q`：通过。
- `python -m pytest tests/test_gui_windows11_shell.py -q -k "settings_page_shows_version"`：通过。

## dry-run 结论

- updater 拒绝 zip-slip 路径。
- updater 替换程序文件时保留 `config.local.ini`。
- updater 替换程序文件时保留 `logs/`。

## SQL Server 影响

本变更不改 SQL Server 表结构，不执行 SQL 脚本，不写同步业务表。（原因：在线更新只替换客户端程序文件）

## 剩余风险

- 第一版未强制代码签名校验。（原因：当前最小可行方案以 HTTPS 和 SHA256 为基础，代码签名作为后续增强）
```

- [ ] **Step 6: Mark OpenSpec tasks and commit**

Update `openspec/changes/add-lightweight-online-update/tasks.md` by checking completed items under version、service、GUI、updater、packaging、verification.

Commit:

```bash
git add openspec/changes/add-lightweight-online-update/tasks.md docs/superpowers/reports/2026-07-09-lightweight-online-update-verify.md
git commit -m "test(update): verify lightweight online update"
```

---

## Self-Review

- Spec coverage: Task 1 覆盖版本来源和 manifest 校验；Task 2 覆盖检查更新、下载和 SHA256；Task 3 覆盖独立 updater、zip-slip、配置保护和回滚基础；Task 4 覆盖 GUI 入口；Task 5 覆盖发布包、`latest.json` 和部署文档；Task 6 覆盖验证与 SQL Server 无影响说明。
- Placeholder scan: 本计划没有未决占位描述。
- Type consistency: `UpdateManifest`、`UpdateCheckResult`、`UpdateService`、`InstallPlan`、`safe_extract_zip()`、`install_package()` 在后续任务中使用的名称与定义一致。
