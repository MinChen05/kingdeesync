from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.services.update_service import (
    ManifestValidationError,
    UpdateManifest,
    UpdateService,
    UpdateServiceError,
    compare_versions,
    parse_manifest,
)
from src.version import (
    APP_CHANNEL,
    APP_NAME,
    APP_VERSION,
    get_app_channel,
    get_app_name,
    get_app_version,
)

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


def test_local_version_source_exposes_app_metadata() -> None:
    assert APP_NAME == "kingdee-sync"
    assert APP_VERSION == "1.0.0"
    assert APP_CHANNEL == "stable"
    assert get_app_name() == APP_NAME
    assert get_app_version() == APP_VERSION
    assert get_app_channel() == APP_CHANNEL


def test_compare_versions_handles_multi_digit_parts() -> None:
    assert compare_versions("1.10.0", "1.9.9") > 0
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.0", "1.0.1") < 0


def test_compare_versions_rejects_negative_parts() -> None:
    with pytest.raises(ManifestValidationError, match="非负整数"):
        compare_versions("1.-1.0", "1.0.0")


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


def test_parse_manifest_rejects_https_url_without_host() -> None:
    data = dict(VALID_MANIFEST)
    data["package_url"] = "https:///release.zip"

    with pytest.raises(ManifestValidationError, match="host"):
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


def test_parse_manifest_rejects_bad_version_fields() -> None:
    for field in ("version", "min_supported_version"):
        data = dict(VALID_MANIFEST)
        data[field] = "1.x.0"

        with pytest.raises(ManifestValidationError, match="版本号"):
            parse_manifest(data)


def test_parse_manifest_rejects_non_positive_size() -> None:
    data = dict(VALID_MANIFEST)
    data["size"] = 0

    with pytest.raises(ManifestValidationError, match="size"):
        parse_manifest(data)


def test_parse_manifest_requires_notes_as_string_array() -> None:
    data = dict(VALID_MANIFEST)
    data["notes"] = ["ok", 1]

    with pytest.raises(ManifestValidationError, match="notes"):
        parse_manifest(data)

    data = dict(VALID_MANIFEST)
    del data["notes"]

    with pytest.raises(ManifestValidationError, match="notes"):
        parse_manifest(data)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


def test_update_service_rejects_non_https_manifest_url() -> None:
    with pytest.raises(UpdateServiceError, match="HTTPS"):
        UpdateService("http://intranet.example.com/latest.json")


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


def test_check_for_update_converts_network_failure() -> None:
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with (
        patch("src.services.update_service.urlopen", side_effect=OSError("network down")),
        pytest.raises(UpdateServiceError, match="检查更新失败"),
    ):
        service.check_for_update()


def test_check_for_update_converts_invalid_manifest() -> None:
    payload = json.dumps({**VALID_MANIFEST, "sha256": "bad"}).encode("utf-8")
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with (
        patch("src.services.update_service.urlopen", return_value=FakeResponse(payload)),
        pytest.raises(UpdateServiceError, match="更新元数据无效"),
    ):
        service.check_for_update()


def test_download_package_verifies_sha256(tmp_path: Path) -> None:
    package_bytes = b"release package"
    sha256 = hashlib.sha256(package_bytes).hexdigest()
    manifest = parse_manifest({**VALID_MANIFEST, "sha256": sha256, "size": len(package_bytes)})
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with patch("src.services.update_service.urlopen", return_value=FakeResponse(package_bytes)):
        package_path = service.download_package(manifest, tmp_path)

    assert package_path.exists()
    assert package_path.read_bytes() == package_bytes


def test_download_package_deletes_file_when_sha256_mismatch(tmp_path: Path) -> None:
    package_bytes = b"tampered package"
    manifest = parse_manifest({**VALID_MANIFEST, "sha256": "0" * 64, "size": len(package_bytes)})
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with (
        patch("src.services.update_service.urlopen", return_value=FakeResponse(package_bytes)),
        pytest.raises(UpdateServiceError, match="sha256"),
    ):
        service.download_package(manifest, tmp_path)

    assert not list(tmp_path.glob("*.zip"))


def test_download_package_keeps_existing_file_when_sha256_mismatch(tmp_path: Path) -> None:
    existing_package = tmp_path / "kingdee-sync-1.4.0.zip"
    existing_bytes = b"existing valid package"
    existing_package.write_bytes(existing_bytes)

    downloaded_bytes = b"tampered package"
    manifest = parse_manifest(
        {**VALID_MANIFEST, "sha256": "0" * 64, "size": len(downloaded_bytes)}
    )
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with (
        patch("src.services.update_service.urlopen", return_value=FakeResponse(downloaded_bytes)),
        pytest.raises(UpdateServiceError, match="sha256"),
    ):
        service.download_package(manifest, tmp_path)

    assert existing_package.exists()
    assert existing_package.read_bytes() == existing_bytes
    assert not list(tmp_path.glob("*.tmp"))


def test_download_package_rejects_size_mismatch_and_removes_temp_file(tmp_path: Path) -> None:
    package_bytes = b"short package"
    sha256 = hashlib.sha256(package_bytes).hexdigest()
    manifest = parse_manifest({**VALID_MANIFEST, "sha256": sha256, "size": len(package_bytes) + 1})
    service = UpdateService("https://intranet.example.com/latest.json", current_version="1.3.0")

    with (
        patch("src.services.update_service.urlopen", return_value=FakeResponse(package_bytes)),
        pytest.raises(UpdateServiceError, match="大小"),
    ):
        service.download_package(manifest, tmp_path)

    assert not list(tmp_path.glob("*.zip"))
    assert not list(tmp_path.glob("*.tmp"))
