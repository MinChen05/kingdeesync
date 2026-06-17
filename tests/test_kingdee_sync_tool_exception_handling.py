import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.utils import kingdee_sync_tool


class KingdeeSyncToolExceptionHandlingTests(unittest.TestCase):
    def test_connection_exception_is_reported_to_gui(self) -> None:
        exc = ConnectionError("database connection dropped")

        with (
            patch.object(kingdee_sync_tool, "_show_warning_async", create=True) as show_warning,
            self.assertLogs("src.utils.kingdee_sync_tool", level="WARNING") as captured,
        ):
            kingdee_sync_tool.handle_exception(ConnectionError, exc, None)

        show_warning.assert_called_once()
        title, message = show_warning.call_args.args
        self.assertIn("连接异常", title)
        self.assertIn("ConnectionError", message)
        self.assertNotIn("已忽略", "\n".join(captured.output))

    def test_handle_exception_does_not_sleep_when_sync_is_running(self) -> None:
        fake_sync_manager = SimpleNamespace(is_sync_running=lambda: True)

        with (
            patch("src.core.data_sync.sync_manager", fake_sync_manager),
            patch.object(kingdee_sync_tool.QApplication, "instance", return_value=None),
            patch("time.sleep") as sleep,
            self.assertLogs("src.utils.kingdee_sync_tool", level="WARNING"),
        ):
            kingdee_sync_tool.handle_exception(RuntimeError, RuntimeError("boom"), None)

        sleep.assert_not_called()

    def test_cleanup_and_exit_does_not_sleep_or_force_gc(self) -> None:
        fake_sync_manager = SimpleNamespace(
            request_shutdown=Mock(),
            is_sync_running=lambda: True,
        )
        fake_scheduler = SimpleNamespace(
            status=SimpleNamespace(value="stopped"),
            stop=Mock(),
        )
        fake_db_manager = SimpleNamespace(disconnect=Mock())
        fake_kingdee_client = SimpleNamespace(stop_keepalive=Mock(), logout=Mock())
        fake_config_manager = SimpleNamespace(get_kingdee_config=Mock(return_value={}))

        with (
            patch("src.core.data_sync.sync_manager", fake_sync_manager),
            patch("src.core.mysql_manager.mysql_manager", fake_db_manager),
            patch("src.core.kingdee_api.kingdee_client", fake_kingdee_client),
            patch.object(kingdee_sync_tool, "auto_scheduler", fake_scheduler),
            patch.object(kingdee_sync_tool, "config_manager", fake_config_manager),
            patch("time.sleep") as sleep,
            patch("gc.collect") as collect,
        ):
            kingdee_sync_tool.cleanup_and_exit()

        fake_sync_manager.request_shutdown.assert_called_once_with("application_exit")
        sleep.assert_not_called()
        collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
