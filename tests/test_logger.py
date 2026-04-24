from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.utils.logger import SafeRotatingFileHandler


class SafeRotatingFileHandlerTests(unittest.TestCase):
    def test_emit_continues_when_rollover_hits_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "app.jsonl"
            handler = SafeRotatingFileHandler(
                str(log_path),
                maxBytes=1,
                backupCount=1,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))

            logger = logging.getLogger("test.safe_rotating_handler.permission")
            logger.setLevel(logging.INFO)
            logger.handlers = []
            logger.propagate = False
            logger.addHandler(handler)

            with patch.object(handler, "shouldRollover", return_value=True), patch.object(
                handler,
                "doRollover",
                side_effect=PermissionError(32, "另一个程序正在使用此文件，进程无法访问。"),
            ):
                logger.info("cleanup complete")

            handler.flush()
            handler.close()
            content = log_path.read_text(encoding="utf-8")
            self.assertIn("cleanup complete", content)


if __name__ == "__main__":
    unittest.main()
