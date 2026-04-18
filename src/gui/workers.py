"""
GUI background workers for sync and connection testing.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from src.services.sync_service import sync_service

logger = logging.getLogger(__name__)


class SyncWorker(QThread):
    """Run a sync task in a background thread."""

    progress = Signal(str, int)
    finished = Signal(dict)

    def __init__(self, forms, sync_type, service=sync_service):
        super().__init__()
        self.forms = forms
        self.sync_type = sync_type
        self.service = service
        self._progress_callback = self._forward_progress

    def _forward_progress(self, message: str, progress: int) -> None:
        self.progress.emit(message, progress)

    def run(self) -> None:
        try:
            self.progress.emit("正在初始化同步任务...", 0)
            result = self.service.sync_data(
                self.forms,
                self.sync_type,
                progress_callback=self._progress_callback,
            )
            self.finished.emit(result)
        except Exception as exc:
            logger.error("同步任务执行失败: %s", exc)
            self.finished.emit(
                {
                    "status": "failed",
                    "message": str(exc),
                    "total_records": 0,
                    "start_time": datetime.now(),
                    "end_time": datetime.now(),
                    "duration": 0,
                    "details": {},
                }
            )


class TestWorker(QThread):
    """Run connection tests in a background thread."""

    finished = Signal(bool, bool, str)

    def __init__(self, service=sync_service):
        super().__init__()
        self.service = service

    def run(self) -> None:
        try:
            api_ok, db_ok, msg = self.service.test_connections()
        except Exception as exc:
            api_ok = False
            db_ok = False
            msg = f"测试过程异常: {exc}"

        self.finished.emit(api_ok, db_ok, msg)
