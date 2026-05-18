from __future__ import annotations

import io
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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


class DryRunCleanupTests(unittest.TestCase):
    def test_collect_cleanup_candidates_reports_existing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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
            app_log = logs_dir / "app.log"
            app_log.write_text("keep me", encoding="utf-8")
            (root / "tmp-dashboard.png").write_bytes(b"png")

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)
            candidate_by_path = {
                _candidate_path(candidate).resolve(): candidate for candidate in candidates
            }

            self.assertIn((root / ".worktrees").resolve(), candidate_by_path)
            self.assertIn((root / ".venv").resolve(), candidate_by_path)
            self.assertIn((root / "logs").resolve(), candidate_by_path)
            self.assertIn((root / ".mypy_cache").resolve(), candidate_by_path)
            self.assertIn((root / ".pytest_cache").resolve(), candidate_by_path)
            self.assertIn((root / ".ruff_cache").resolve(), candidate_by_path)
            self.assertIn((root / "checkpoints").resolve(), candidate_by_path)
            self.assertIn((root / "pkg" / "__pycache__").resolve(), candidate_by_path)
            self.assertIn((root / "tmp-dashboard.png").resolve(), candidate_by_path)

            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".worktrees").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".venv").resolve()]))
            self.assertEqual(app_log.stat().st_size, _candidate_size(candidate_by_path[(root / "logs").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".mypy_cache").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".pytest_cache").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / ".ruff_cache").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / "checkpoints").resolve()]))
            self.assertEqual(0, _candidate_size(candidate_by_path[(root / "pkg" / "__pycache__").resolve()]))
            self.assertEqual(3, _candidate_size(candidate_by_path[(root / "tmp-dashboard.png").resolve()]))

    def test_collect_cleanup_candidates_returns_empty_list_when_targets_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)

            self.assertEqual([], list(candidates))

    def test_main_is_read_only_and_reports_candidate_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
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
            dashboard_png = root / "tmp-dashboard.png"
            dashboard_png.write_bytes(b"png")
            app_log = logs_dir / "app.log"
            app_log.write_text("keep me", encoding="utf-8")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                try:
                    exit_code = dry_run_cleanup.main(["--root", str(root)])
                except SystemExit as exc:
                    exit_code = exc.code

            output = buffer.getvalue()
            self.assertIn("No files were deleted.", output)
            self.assertIn(".worktrees", output)
            self.assertIn(".venv", output)
            self.assertIn("logs", output)
            self.assertIn(".mypy_cache", output)
            self.assertIn(".pytest_cache", output)
            self.assertIn(".ruff_cache", output)
            self.assertIn("checkpoints", output)
            self.assertIn("__pycache__", output)
            self.assertIn("tmp-dashboard.png", output)
            self.assertRegex(output, r"(目录|directory)")
            self.assertRegex(output, r"(高收益|低风险|建议|high|low|risk)")
            self.assertRegex(
                output,
                re.compile(r"tmp-dashboard\.png.*(文件|file).*(3|3\s*(B|bytes))", re.S),
            )
            self.assertTrue((root / ".worktrees").exists())
            self.assertTrue((root / ".venv").exists())
            self.assertTrue(logs_dir.exists())
            self.assertTrue((root / ".mypy_cache").exists())
            self.assertTrue((root / ".pytest_cache").exists())
            self.assertTrue((root / ".ruff_cache").exists())
            self.assertTrue((root / "checkpoints").exists())
            self.assertTrue((root / "pkg" / "__pycache__").exists())
            self.assertTrue(dashboard_png.exists())
            self.assertTrue(app_log.exists())
            self.assertEqual("keep me", app_log.read_text(encoding="utf-8"))
            self.assertIn(exit_code, (None, 0))


if __name__ == "__main__":
    unittest.main()
