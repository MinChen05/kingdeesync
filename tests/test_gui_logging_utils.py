from __future__ import annotations

import logging
import unittest

from src.gui.logging_utils import GuiLogHandler


class BrokenSignalEmitter:
    class BrokenSignal:
        def emit(self, *_args, **_kwargs) -> None:
            raise RuntimeError("Signal source has been deleted")

    text_written = BrokenSignal()


class GuiLogHandlerTests(unittest.TestCase):
    def test_emit_swallows_deleted_signal_source_runtimeerror(self) -> None:
        handler = GuiLogHandler(BrokenSignalEmitter())
        handler.setFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)

        handler.emit(record)


if __name__ == "__main__":
    unittest.main()
