import hashlib
import json
import zipfile
from pathlib import Path

from create_deploy import create_update_release, resolve_release_base_url, should_exclude_from_release


def test_release_package_excludes_local_config_and_logs() -> None:
    excluded = [
        Path("config.ini"),
        Path("config.local.ini"),
        Path("config.ini.backup"),
        Path("logs/app.log"),
        Path("Config.ini"),
        Path("CONFIG.LOCAL.INI"),
        Path("CONFIG.INI.BACKUP"),
        Path("Logs/app.log"),
    ]
    included = [
        Path("金蝶数据同步工具.exe"),
        Path("config.example.ini"),
        Path("DEPLOY.md"),
    ]

    assert all(should_exclude_from_release(path) for path in excluded)
    assert not any(should_exclude_from_release(path) for path in included)


def test_create_update_release_generates_zip_hash_and_manifest(tmp_path: Path) -> None:
    deploy_dir = tmp_path / "deploy" / "金蝶数据同步工具"
    deploy_dir.mkdir(parents=True)
    (deploy_dir / "金蝶数据同步工具.exe").write_bytes(b"exe")
    (deploy_dir / "config.example.ini").write_text("template", encoding="utf-8")
    (deploy_dir / "config.ini").write_text("local", encoding="utf-8")
    (deploy_dir / "config.local.ini").write_text("local", encoding="utf-8")
    (deploy_dir / "config.ini.backup").write_text("backup", encoding="utf-8")
    (deploy_dir / "Config.ini").write_text("local", encoding="utf-8")
    (deploy_dir / "CONFIG.LOCAL.INI").write_text("local", encoding="utf-8")
    (deploy_dir / "CONFIG.INI.BACKUP").write_text("backup", encoding="utf-8")
    (deploy_dir / "Logs").mkdir()
    (deploy_dir / "Logs" / "app.log").write_text("log", encoding="utf-8")

    create_update_release(deploy_dir, "1.2.3", "https://intranet.example.com/releases")

    release_dir = tmp_path / "deploy" / "release"
    zip_path = release_dir / "kingdee-sync-1.2.3.zip"
    latest_path = release_dir / "latest.json"

    assert zip_path.exists()
    assert latest_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    assert "金蝶数据同步工具.exe" in names
    assert "config.example.ini" in names
    assert "config.ini" not in names
    assert "config.local.ini" not in names
    assert "config.ini.backup" not in names
    assert "logs/app.log" not in names
    assert "Config.ini" not in names
    assert "CONFIG.LOCAL.INI" not in names
    assert "CONFIG.INI.BACKUP" not in names
    assert "Logs/app.log" not in names

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert list(latest) == [
        "app",
        "version",
        "channel",
        "release_date",
        "min_supported_version",
        "package_url",
        "sha256",
        "size",
        "force",
        "notes",
    ]
    assert latest["app"] == "kingdee-sync"
    assert latest["version"] == "1.2.3"
    assert latest["channel"] == "stable"
    assert latest["package_url"] == "https://intranet.example.com/releases/kingdee-sync-1.2.3.zip"
    assert latest["sha256"] == hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert latest["size"] == zip_path.stat().st_size
    assert latest["force"] is False
    assert latest["notes"] == []


def test_release_base_url_prefers_cli_then_environment(monkeypatch) -> None:
    monkeypatch.setenv("KINGDEE_SYNC_RELEASE_BASE_URL", "https://env.example.com/releases")

    assert (
        resolve_release_base_url("https://cli.example.com/releases")
        == "https://cli.example.com/releases"
    )
    assert resolve_release_base_url(None) == "https://env.example.com/releases"
