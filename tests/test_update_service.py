from __future__ import annotations

import pytest

from src.services.update_service import (
    ManifestValidationError,
    UpdateManifest,
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
