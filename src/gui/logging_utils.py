import logging
from PySide6.QtCore import QObject, Signal

class LogSignal(QObject):
    text_written = Signal(str, str)

class GuiLogHandler(logging.Handler):
    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter

    def emit(self, record):
        msg = self.format(record)
        level = record.levelname
        emitter = self.signal_emitter
        signal = getattr(emitter, "text_written", None)
        if signal is None:
            return
        try:
            signal.emit(msg, level)
        except RuntimeError as exc:
            if "Signal source has been deleted" in str(exc):
                return
            raise
