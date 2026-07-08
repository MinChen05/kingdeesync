from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.updater import (
    InstallPlan,
    install_package,
    main,
    safe_extract_zip,
    start_application,
    wait_for_process_exit,
    write_update_failure,
)


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_safe_extract_rejects_zip_slip(tmp_path: Path) -> None:
    package = tmp_path / "bad.zip"
    make_zip(package, {"../evil.txt": b"evil"})

    with pytest.raises(ValueError, match="unsafe"):
        safe_extract_zip(package, tmp_path / "extract")


def test_safe_extract_rejects_absolute_and_backslash_zip_slip(tmp_path: Path) -> None:
    absolute_package = tmp_path / "absolute.zip"
    make_zip(absolute_package, {"/evil.txt": b"evil"})

    with pytest.raises(ValueError, match="unsafe"):
        safe_extract_zip(absolute_package, tmp_path / "absolute_extract")

    backslash_package = tmp_path / "backslash.zip"
    make_zip(backslash_package, {"..\\evil.txt": b"evil"})

    with pytest.raises(ValueError, match="unsafe"):
        safe_extract_zip(backslash_package, tmp_path / "backslash_extract")


def test_install_preserves_local_config_logs_and_backups(tmp_path: Path) -> None:
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    (install_dir / "金蝶数据同步工具.exe").write_bytes(b"old")
    (install_dir / "config.local.ini").write_text("local", encoding="utf-8")
    (install_dir / "config.ini").write_text("config", encoding="utf-8")
    (install_dir / "config.ini.backup").write_text("backup config", encoding="utf-8")
    (install_dir / "logs").mkdir()
    (install_dir / "logs" / "app.log").write_text("log", encoding="utf-8")
    (install_dir / "backups").mkdir()
    (install_dir / "backups" / "keep.txt").write_text("keep", encoding="utf-8")

    package = tmp_path / "new.zip"
    make_zip(
        package,
        {
            "金蝶数据同步工具.exe": b"new",
            "config.local.ini": b"wrong",
            "config.ini": b"wrong",
            "config.ini.backup": b"wrong",
            "logs/app.log": b"wrong",
            "backups/keep.txt": b"wrong",
        },
    )

    plan = InstallPlan(package_path=package, install_dir=install_dir, app_exe_name="金蝶数据同步工具.exe")
    install_package(plan)

    assert (install_dir / "金蝶数据同步工具.exe").read_bytes() == b"new"
    assert (install_dir / "config.local.ini").read_text(encoding="utf-8") == "local"
    assert (install_dir / "config.ini").read_text(encoding="utf-8") == "config"
    assert (install_dir / "config.ini.backup").read_text(encoding="utf-8") == "backup config"
    assert (install_dir / "logs" / "app.log").read_text(encoding="utf-8") == "log"
    assert (install_dir / "backups" / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_install_preserves_protected_paths_case_insensitively(tmp_path: Path) -> None:
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    (install_dir / "金蝶数据同步工具.exe").write_bytes(b"old")
    (install_dir / "config.local.ini").write_text("local", encoding="utf-8")
    (install_dir / "config.ini").write_text("config", encoding="utf-8")
    (install_dir / "logs").mkdir()
    (install_dir / "logs" / "app.log").write_text("log", encoding="utf-8")
    (install_dir / "backups").mkdir()
    (install_dir / "backups" / "keep.txt").write_text("keep", encoding="utf-8")

    package = tmp_path / "new.zip"
    make_zip(
        package,
        {
            "金蝶数据同步工具.exe": b"new",
            "Config.Local.ini": b"wrong",
            "CONFIG.INI": b"wrong",
            "LOGS/app.log": b"wrong",
            "Backups/keep.txt": b"wrong",
        },
    )

    plan = InstallPlan(package_path=package, install_dir=install_dir, app_exe_name="金蝶数据同步工具.exe")
    install_package(plan)

    assert (install_dir / "金蝶数据同步工具.exe").read_bytes() == b"new"
    assert (install_dir / "config.local.ini").read_text(encoding="utf-8") == "local"
    assert (install_dir / "config.ini").read_text(encoding="utf-8") == "config"
    assert (install_dir / "logs" / "app.log").read_text(encoding="utf-8") == "log"
    assert (install_dir / "backups" / "keep.txt").read_text(encoding="utf-8") == "keep"
    actual_names = {item.name for item in install_dir.iterdir()}
    assert "Config.Local.ini" not in actual_names
    assert "CONFIG.INI" not in actual_names
    assert "LOGS" not in actual_names
    assert "Backups" not in actual_names


def test_install_removes_old_unprotected_files_missing_from_release(tmp_path: Path) -> None:
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    (install_dir / "金蝶数据同步工具.exe").write_bytes(b"old")
    (install_dir / "old.dll").write_bytes(b"old dll")
    (install_dir / "old_dir").mkdir()
    (install_dir / "old_dir" / "old.txt").write_text("old", encoding="utf-8")
    (install_dir / "config.ini").write_text("config", encoding="utf-8")

    package = tmp_path / "new.zip"
    make_zip(package, {"金蝶数据同步工具.exe": b"new", "new.dll": b"new dll"})

    plan = InstallPlan(package_path=package, install_dir=install_dir, app_exe_name="金蝶数据同步工具.exe")
    install_package(plan)

    assert (install_dir / "金蝶数据同步工具.exe").read_bytes() == b"new"
    assert (install_dir / "new.dll").read_bytes() == b"new dll"
    assert not (install_dir / "old.dll").exists()
    assert not (install_dir / "old_dir").exists()
    assert (install_dir / "config.ini").read_text(encoding="utf-8") == "config"


def test_install_rejects_package_missing_app_exe_before_removing_old_files(tmp_path: Path) -> None:
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    (install_dir / "金蝶数据同步工具.exe").write_bytes(b"old exe")
    (install_dir / "old.dll").write_bytes(b"old dll")

    package = tmp_path / "bad.zip"
    make_zip(package, {"new.dll": b"new dll"})
    plan = InstallPlan(package_path=package, install_dir=install_dir, app_exe_name="金蝶数据同步工具.exe")

    with pytest.raises(FileNotFoundError, match="更新包缺少主程序"):
        install_package(plan)

    assert (install_dir / "金蝶数据同步工具.exe").read_bytes() == b"old exe"
    assert (install_dir / "old.dll").read_bytes() == b"old dll"
    assert not (install_dir / "new.dll").exists()


def test_install_restores_backup_when_replacement_fails(tmp_path: Path) -> None:
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    (install_dir / "金蝶数据同步工具.exe").write_bytes(b"old exe")
    (install_dir / "lib.dll").write_bytes(b"old dll")

    package = tmp_path / "new.zip"
    make_zip(package, {"金蝶数据同步工具.exe": b"new exe", "lib.dll": b"new dll"})
    plan = InstallPlan(package_path=package, install_dir=install_dir, app_exe_name="金蝶数据同步工具.exe")

    original_copy2 = __import__("shutil").copy2

    def fail_on_lib(source: Path, target: Path) -> Path:
        if Path(target).name == "lib.dll":
            raise OSError("copy failed")
        return original_copy2(source, target)

    with patch("src.updater.shutil.copy2", side_effect=fail_on_lib):
        with pytest.raises(OSError, match="copy failed"):
            install_package(plan)

    assert (install_dir / "金蝶数据同步工具.exe").read_bytes() == b"old exe"
    assert (install_dir / "lib.dll").read_bytes() == b"old dll"


def test_wait_for_process_exit_uses_windows_wait_api_without_os_kill() -> None:
    fake_kernel32 = Mock()
    fake_kernel32.OpenProcess.return_value = 123
    fake_kernel32.WaitForSingleObject.return_value = 0

    with (
        patch("src.updater.os.name", "nt"),
        patch("src.updater.ctypes.windll.kernel32", fake_kernel32),
        patch("src.updater.os.kill") as os_kill,
    ):
        wait_for_process_exit(456, timeout_seconds=1)

    os_kill.assert_not_called()
    fake_kernel32.OpenProcess.assert_called_once()
    fake_kernel32.WaitForSingleObject.assert_called_once_with(123, 1000)
    fake_kernel32.CloseHandle.assert_called_once_with(123)


def test_write_update_failure_writes_diagnostic_payload(tmp_path: Path) -> None:
    failure_path = write_update_failure(
        install_dir=tmp_path,
        stage="install",
        message="copy failed",
        rollback_success=True,
    )

    payload = json.loads(failure_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "install"
    assert payload["message"] == "copy failed"
    assert payload["rollback_success"] is True
    assert "timestamp" in payload


def test_start_application_launches_app_without_waiting(tmp_path: Path) -> None:
    app = tmp_path / "金蝶数据同步工具.exe"
    app.write_bytes(b"exe")

    with patch("src.updater.subprocess.Popen") as popen:
        start_application(tmp_path, app.name)

    popen.assert_called_once_with([str(app)], cwd=str(tmp_path), close_fds=True)


def test_main_starts_application_after_successful_install(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    install_dir = tmp_path / "app"
    install_dir.mkdir()

    with (
        patch(
            "sys.argv",
            [
                "updater",
                "--package",
                str(package),
                "--install-dir",
                str(install_dir),
                "--app-exe",
                "app.exe",
            ],
        ),
        patch("src.updater.install_package") as install,
        patch("src.updater.start_application") as start,
    ):
        main()

    install.assert_called_once()
    start.assert_called_once_with(install_dir, "app.exe")


def test_main_writes_update_failed_json_when_install_fails(tmp_path: Path) -> None:
    package = tmp_path / "package.zip"
    install_dir = tmp_path / "app"
    install_dir.mkdir()

    with (
        patch(
            "sys.argv",
            [
                "updater",
                "--package",
                str(package),
                "--install-dir",
                str(install_dir),
                "--app-exe",
                "app.exe",
            ],
        ),
        patch("src.updater.install_package", side_effect=RuntimeError("install failed")),
        patch("src.updater.start_application") as start,
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 1
    start.assert_not_called()
    payload = json.loads((install_dir / "update-failed.json").read_text(encoding="utf-8"))
    assert payload["stage"] == "install"
    assert payload["message"] == "install failed"
    assert payload["rollback_success"] is False


def test_main_entrypoint_routes_updater_subcommand(tmp_path: Path) -> None:
    import main as app_main

    install_dir = tmp_path / "app"
    package = tmp_path / "package.zip"

    with (
        patch(
            "sys.argv",
            [
                "main.py",
                "updater",
                "--package",
                str(package),
                "--install-dir",
                str(install_dir),
                "--app-exe",
                "app.exe",
                "--pid",
                "123",
            ],
        ),
        patch("main.run_updater") as run_updater,
    ):
        app_main.main()

    run_updater.assert_called_once()
    args = run_updater.call_args.args[0]
    assert args.command == "updater"
    assert args.package == str(package)
    assert args.install_dir == str(install_dir)
    assert args.app_exe == "app.exe"
    assert args.pid == 123
