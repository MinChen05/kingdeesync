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
        self.signal_emitter.text_written.emit(msg, level)
