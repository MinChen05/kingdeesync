from __future__ import annotations

import io
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import scripts.dry_run_cleanup as dry_run_cleanup


def _candidate_path(candidate: object) -> Path:
    raw_path = getattr(candidate, "path", candidate)
    return Path(raw_path)


def _candidate_size(candidate: object) -> int:
    if isinstance(candidate, dict):
        raw_size = candidate.get("size")
    elif isinstance(candidate, (tuple, list)) and len(candidate) > 1:
        raw_size = candidate[1]
    else:
        raw_size = getattr(candidate, "size", None)

    if raw_size is None:
        raise AssertionError(f"candidate does not expose size: {candidate!r}")

    return int(raw_size)


def _candidate_reason(candidate: object) -> str:
    raw_reason = getattr(candidate, "reason", None)
    if raw_reason is None:
        raise AssertionError(f"candidate does not expose reason: {candidate!r}")
    return str(raw_reason)


class DryRunCleanupTests(unittest.TestCase):
    def test_collect_cleanup_candidates_reports_existing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".idea").mkdir()
            (root / ".claude").mkdir()
            (root / ".install_salt").write_text("salt", encoding="utf-8")
            (root / "config.local.ini").write_text("[local]\n", encoding="utf-8")
            (root / "config.ini.backup").write_text("[backup]\n", encoding="utf-8")
            (root / "log").mkdir()
            (root / "log" / "app.log").write_text("keep me", encoding="utf-8")
            (root / ".worktrees").mkdir()
            (root / ".venv").mkdir()
            logs_dir = root / "logs"
            logs_dir.mkdir()
            (root / ".mypy_cache").mkdir()
            (root / ".pytest_cache").mkdir()
            (root / ".ruff_cache").mkdir()
            (root / "checkpoints").mkdir()
            (root / "pkg").mkdir()
            (root / "pkg" / "__pycache__").mkdir()
            (root / "nested").mkdir()
            nested_ds_store = root / "nested" / ".DS_Store"
            nested_ds_store.write_bytes(b"ds")
            app_log = logs_dir / "app.log"
            app_log.write_text("keep me", encoding="utf-8")
            (root / "tmp-dashboard.png").write_bytes(b"png")

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)
            candidate_by_path = {
                _candidate_path(candidate).resolve(): candidate for candidate in candidates
            }

            self.assertIn((root / ".idea").resolve(), candidate_by_path)
            self.assertIn((root / ".claude").resolve(), candidate_by_path)
            self.assertIn((root / ".install_salt").resolve(), candidate_by_path)
            self.assertIn((root / "config.local.ini").resolve(), candidate_by_path)
            self.assertIn((root / "config.ini.backup").resolve(), candidate_by_path)
            self.assertIn((root / "log").resolve(), candidate_by_path)
            self.assertIn((root / ".worktrees").resolve(), candidate_by_path)
            self.assertIn((root / ".venv").resolve(), candidate_by_path)
            self.assertIn((root / "logs").resolve(), candidate_by_path)
            self.assertIn((root / ".mypy_cache").resolve(), candidate_by_path)
            self.assertIn((root / ".pytest_cache").resolve(), candidate_by_path)
            self.assertIn((root / ".ruff_cache").resolve(), candidate_by_path)
            self.assertIn((root / "checkpoints").resolve(), candidate_by_path)
            self.assertIn((root / "pkg" / "__pycache__").resolve(), candidate_by_path)
            self.assertIn(nested_ds_store.resolve(), candidate_by_path)
            self.assertIn((root / "tmp-dashboard.png").resolve(), candidate_by_path)

            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".idea").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".claude").resolve()]))
            self.assertEqual(
                (root / ".install_salt").stat().st_size,
                _candidate_size(candidate_by_path[(root / ".install_salt").resolve()]),
            )
            self.assertEqual(
                (root / "config.local.ini").stat().st_size,
                _candidate_size(candidate_by_path[(root / "config.local.ini").resolve()]),
            )
            self.assertEqual(
                (root / "config.ini.backup").stat().st_size,
                _candidate_size(candidate_by_path[(root / "config.ini.backup").resolve()]),
            )
            self.assertEqual(app_log.stat().st_size, _candidate_size(candidate_by_path[(root / "log").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".worktrees").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".venv").resolve()]))
            self.assertEqual(app_log.stat().st_size, _candidate_size(candidate_by_path[(root / "logs").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".mypy_cache").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".pytest_cache").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".ruff_cache").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / "checkpoints").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / "pkg" / "__pycache__").resolve()]))
            self.assertEqual(2, _candidate_size(candidate_by_path[nested_ds_store.resolve()]))
            self.assertEqual(3, _candidate_size(candidate_by_path[(root / "tmp-dashboard.png").resolve()]))
            self.assertIn("git worktree list", _candidate_reason(candidate_by_path[(root / ".worktrees").resolve()]))
            self.assertIn("git worktree remove", _candidate_reason(candidate_by_path[(root / ".worktrees").resolve()]))
            self.assertIn("git worktree prune", _candidate_reason(candidate_by_path[(root / ".worktrees").resolve()]))

    def test_collect_cleanup_candidates_returns_empty_list_when_targets_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)

            self.assertEqual([], list(candidates))

    def test_render_report_includes_summary_even_when_no_candidates_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            output = dry_run_cleanup._render_report([], root)

            self.assertIn("Summary: 0 candidate(s), total size: 0 B", output)
            self.assertIn("No cleanup candidates found.", output)
            self.assertIn("No files were deleted.", output)

    def test_collect_cleanup_candidates_skips_nested_pycache_inside_aggregated_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nested_pycache = root / ".venv" / "Lib" / "__pycache__"
            nested_pycache.mkdir(parents=True)
            pkg_pycache = root / "pkg" / "__pycache__"
            pkg_pycache.mkdir(parents=True)

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)
            candidate_paths = {_candidate_path(candidate).resolve() for candidate in candidates}

            self.assertIn((root / ".venv").resolve(), candidate_paths)
            self.assertIn(pkg_pycache.resolve(), candidate_paths)
            self.assertNotIn(nested_pycache.resolve(), candidate_paths)

    def test_collect_cleanup_candidates_tolerates_unreadable_or_missing_files_during_size_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            logs_dir = root / "logs"
            logs_dir.mkdir()
            stable_file = logs_dir / "stable.log"
            stable_file.write_text("ok", encoding="utf-8")
            flaky_file = logs_dir / "flaky.log"
            flaky_file.write_text("gone", encoding="utf-8")

            path_type = type(flaky_file)
            original_stat = path_type.stat

            def flaky_stat(path_self: Path, *args: object, **kwargs: object) -> object:
                if path_self == flaky_file:
                    raise FileNotFoundError("simulated concurrent deletion")
                return original_stat(path_self, *args, **kwargs)

            with mock.patch.object(path_type, "stat", autospec=True, side_effect=flaky_stat):
                candidates = dry_run_cleanup.collect_cleanup_candidates(root)

            candidate_by_path = {
                _candidate_path(candidate).resolve(): candidate for candidate in candidates
            }
            self.assertIn(logs_dir.resolve(), candidate_by_path)
            self.assertEqual(2, _candidate_size(candidate_by_path[logs_dir.resolve()]))

    def test_main_is_read_only_and_reports_candidate_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".idea").mkdir()
            (root / ".claude").mkdir()
            (root / ".install_salt").write_text("salt", encoding="utf-8")
            (root / "config.local.ini").write_text("[local]\n", encoding="utf-8")
            (root / "config.ini.backup").write_text("[backup]\n", encoding="utf-8")
            (root / "log").mkdir()
            (root / "log" / "app.log").write_text("keep me", encoding="utf-8")
            (root / ".worktrees").mkdir()
            (root / ".venv").mkdir()
            logs_dir = root / "logs"
            logs_dir.mkdir()
            (root / ".mypy_cache").mkdir()
            (root / ".pytest_cache").mkdir()
            (root / ".ruff_cache").mkdir()
            (root / "checkpoints").mkdir()
            (root / "pkg").mkdir()
            (root / "pkg" / "__pycache__").mkdir()
            (root / "nested").mkdir()
            (root / "nested" / ".DS_Store").write_bytes(b"ds")
            dashboard_png = root / "tmp-dashboard.png"
            dashboard_png.write_bytes(b"png")
            app_log = logs_dir / "app.log"
            app_log.write_text("keep me", encoding="utf-8")
            expected_candidates = dry_run_cleanup.collect_cleanup_candidates(root)
            expected_count = len(expected_candidates)
            expected_total_size = sum(_candidate_size(candidate) for candidate in expected_candidates)

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                try:
                    exit_code = dry_run_cleanup.main(["--root", str(root)])
                except SystemExit as exc:
                    exit_code = exc.code

            output = buffer.getvalue()
            self.assertIn(f"Summary: {expected_count} candidate(s), total size:", output)
            self.assertIn(f"total size: {expected_total_size} B", output)
            self.assertIn("No files were deleted.", output)
            self.assertIn("High-risk Git worktree storage.", output)
            self.assertIn("git worktree list", output)
            self.assertIn("git worktree remove", output)
            self.assertIn("git worktree prune", output)
            self.assertIn(".worktrees", output)
            self.assertIn(".venv", output)
            self.assertIn(".idea", output)
            self.assertIn(".claude", output)
            self.assertIn(".install_salt", output)
            self.assertIn("config.local.ini", output)
            self.assertIn("config.ini.backup", output)
            self.assertIn("log", output)
            self.assertIn("logs", output)
            self.assertIn(".mypy_cache", output)
            self.assertIn(".pytest_cache", output)
            self.assertIn(".ruff_cache", output)
            self.assertIn("checkpoints", output)
            self.assertIn("__pycache__", output)
            self.assertIn(".DS_Store", output)
            self.assertIn("tmp-dashboard.png", output)
            self.assertRegex(output, r"(目录|directory)")
            self.assertRegex(output, r"(高收益|低风险|建议|high|low|risk)")
            self.assertRegex(
                output,
                re.compile(
                    r"tmp-dashboard\.png.*(文件|file).*(3|3\s*(B|bytes)).*(说明|备注|note|reason|because)",
                    re.S,
                ),
            )
            self.assertTrue((root / ".worktrees").exists())
            self.assertTrue((root / ".venv").exists())
            self.assertTrue(logs_dir.exists())
            self.assertTrue((root / ".mypy_cache").exists())
            self.assertTrue((root / ".pytest_cache").exists())
            self.assertTrue((root / ".ruff_cache").exists())
            self.assertTrue((root / "checkpoints").exists())
            self.assertTrue((root / "pkg" / "__pycache__").exists())
            self.assertTrue((root / ".idea").exists())
            self.assertTrue((root / ".claude").exists())
            self.assertTrue((root / ".install_salt").exists())
            self.assertTrue((root / "config.local.ini").exists())
            self.assertTrue((root / "config.ini.backup").exists())
            self.assertTrue((root / "log").exists())
            self.assertTrue((root / "nested" / ".DS_Store").exists())
            self.assertTrue(dashboard_png.exists())
            self.assertTrue(app_log.exists())
            self.assertEqual("keep me", app_log.read_text(encoding="utf-8"))
            self.assertIn(exit_code, (None, 0))

    def test_main_returns_error_when_root_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "does-not-exist"

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            with redirect_stdout(stdout_buffer), mock.patch("sys.stderr", stderr_buffer):
                with self.assertRaises(SystemExit) as raised:
                    dry_run_cleanup.main(["--root", str(root)])

            self.assertNotEqual(0, raised.exception.code)
            self.assertEqual("", stdout_buffer.getvalue())
            self.assertIn("Root path does not exist or is not a directory", stderr_buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
