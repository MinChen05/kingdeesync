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
        channel=str(data.get("channel", "stable")),
        release_date=str(data.get("release_date", "")),
        min_supported_version=min_supported_version,
        package_url=package_url,
        sha256=sha256.lower(),
        size=size,
        force=bool(data.get("force", False)),
        notes=tuple(notes_raw),
    )
