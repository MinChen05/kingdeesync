from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from src.version import APP_NAME, get_app_version

SUPPORTED_CHANNEL = "stable"


class ManifestValidationError(ValueError):
    pass


class UpdateServiceError(RuntimeError):
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


@dataclass(frozen=True)
class UpdateCheckResult:
    update_available: bool
    manifest: UpdateManifest


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise ManifestValidationError(f"版本号格式无效: {value}")
    try:
        major, minor, patch = (int(part) for part in parts)
    except ValueError as exc:
        raise ManifestValidationError(f"版本号格式无效: {value}") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ManifestValidationError(f"版本号组件必须是非负整数: {value}")
    return major, minor, patch


def compare_versions(left: str, right: str) -> int:
    left_tuple = _version_tuple(left)
    right_tuple = _version_tuple(right)
    return (left_tuple > right_tuple) - (left_tuple < right_tuple)


def parse_manifest(data: dict[str, Any]) -> UpdateManifest:
    if data.get("app") != APP_NAME:
        raise ManifestValidationError("manifest app 不匹配")

    channel = str(data.get("channel", ""))
    if channel != SUPPORTED_CHANNEL:
        raise ManifestValidationError(f"manifest channel 必须为 {SUPPORTED_CHANNEL}")

    version = str(data.get("version", ""))
    min_supported_version = str(data.get("min_supported_version", ""))
    _version_tuple(version)
    _version_tuple(min_supported_version)

    package_url = str(data.get("package_url", ""))
    parsed = urlparse(package_url)
    if parsed.scheme.lower() != "https":
        raise ManifestValidationError("package_url 必须使用 HTTPS")
    if not parsed.netloc:
        raise ManifestValidationError("package_url 必须包含 host")

    sha256 = str(data.get("sha256", ""))
    hex_chars = "0123456789abcdefABCDEF"
    if len(sha256) != 64 or any(ch not in hex_chars for ch in sha256):
        raise ManifestValidationError("sha256 必须是 64 位十六进制字符串")

    size = data.get("size")
    if not isinstance(size, int) or size <= 0:
        raise ManifestValidationError("size 必须是正整数")

    notes_raw = data.get("notes")
    if not isinstance(notes_raw, list) or not all(isinstance(item, str) for item in notes_raw):
        raise ManifestValidationError("notes 必须是字符串数组")

    return UpdateManifest(
        app=APP_NAME,
        version=version,
        channel=channel,
        release_date=str(data.get("release_date", "")),
        min_supported_version=min_supported_version,
        package_url=package_url,
        sha256=sha256.lower(),
        size=size,
        force=bool(data.get("force", False)),
        notes=tuple(notes_raw),
    )


class UpdateService:
    def __init__(
        self,
        manifest_url: str,
        current_version: str | None = None,
        timeout_seconds: int = 5,
    ) -> None:
        parsed = urlparse(manifest_url)
        if parsed.scheme.lower() != "https":
            raise UpdateServiceError("manifest_url 必须使用 HTTPS")
        if not parsed.netloc:
            raise UpdateServiceError("manifest_url 必须包含 host")

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
            if not isinstance(data, dict):
                raise ManifestValidationError("manifest 必须是 JSON object")
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
        temp_path = target_dir / f".{package_path.name}.tmp"

        try:
            with urlopen(manifest.package_url, timeout=self.timeout_seconds) as response:
                package_bytes = response.read()
        except Exception as exc:
            raise UpdateServiceError(f"下载更新包失败: {exc}") from exc

        temp_path.write_bytes(package_bytes)
        try:
            actual_size = temp_path.stat().st_size
            if actual_size != manifest.size:
                raise UpdateServiceError(
                    f"更新包大小校验失败: 期望 {manifest.size} 字节，实际 {actual_size} 字节"
                )

            actual_hash = hashlib.sha256(temp_path.read_bytes()).hexdigest()
            if actual_hash.lower() != manifest.sha256.lower():
                raise UpdateServiceError("更新包 sha256 校验失败")
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        temp_path.replace(package_path)

        return package_path
