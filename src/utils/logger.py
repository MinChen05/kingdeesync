import logging
import os
import sys
from logging.handlers import RotatingFileHandler

try:
    from pythonjsonlogger import jsonlogger
except Exception:
    jsonlogger = None


def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_log_dir() -> str:
    log_dir = os.path.join(get_base_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_debug_log_path(filename: str) -> str:
    return os.path.join(get_log_dir(), filename)


def setup_logging():
    log_dir = get_log_dir()
    log_file = os.path.join(log_dir, "app.log")
    log_file_json = os.path.join(log_dir, "app.jsonl")

    handlers = [
        RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    ]

    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))

    if jsonlogger is not None:
        json_handler = RotatingFileHandler(log_file_json, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        json_formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        json_handler.setFormatter(json_formatter)
        handlers.append(json_handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pymysql").setLevel(logging.WARNING)


def add_log_handler(handler):
    """Add an extra root log handler, for example a GUI handler."""
    logging.getLogger().addHandler(handler)


def get_logger(name=None):
    """Return a logger by name."""
    return logging.getLogger(name)
