from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import scripts.dry_run_cleanup as dry_run_cleanup


def _candidate_path(candidate: object) -> Path:
    raw_path = getattr(candidate, "path", candidate)
    return Path(raw_path)


class DryRunCleanupTests(unittest.TestCase):
    def test_collect_cleanup_candidates_reports_existing_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".venv").mkdir()
            (root / "logs").mkdir()
            (root / "pkg").mkdir()
            (root / "pkg" / "__pycache__").mkdir()
            (root / "tmp-dashboard.png").write_bytes(b"png")

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)
            candidate_paths = {_candidate_path(candidate).resolve() for candidate in candidates}

            self.assertIn((root / ".venv").resolve(), candidate_paths)
            self.assertIn((root / "logs").resolve(), candidate_paths)
            self.assertIn((root / "pkg" / "__pycache__").resolve(), candidate_paths)
            self.assertIn((root / "tmp-dashboard.png").resolve(), candidate_paths)

    def test_collect_cleanup_candidates_returns_empty_list_when_targets_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            candidates = dry_run_cleanup.collect_cleanup_candidates(root)

            self.assertEqual([], list(candidates))

    def test_main_is_read_only_and_keeps_logs_app_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            logs_dir = root / "logs"
            logs_dir.mkdir()
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
            self.assertTrue(app_log.exists())
            self.assertEqual("keep me", app_log.read_text(encoding="utf-8"))
            self.assertIn(exit_code, (None, 0))


if __name__ == "__main__":
    unittest.main()
