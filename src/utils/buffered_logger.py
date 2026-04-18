"""
日志批量写入模块
实现日志缓冲和批量写入，提高I/O性能
"""

import logging
import threading
import os
from typing import List, Optional
from collections import deque
from datetime import datetime


class BufferedLogHandler(logging.Handler):
    """缓冲日志处理器"""

    def __init__(
        self,
        filename: str,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        encoding: str = "utf-8",
    ):
        """
        Args:
            filename: 日志文件名
            buffer_size: 缓冲区大小
            flush_interval: 刷新间隔(秒)
            max_file_size: 最大文件大小(字节)
            backup_count: 备份文件数量
            encoding: 文件编码
        """
        super().__init__()
        self.filename = filename
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.encoding = encoding

        self._buffer = deque()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flush_thread = None

        # 确保目录存在
        dir_name = os.path.dirname(filename)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
            except Exception:
                pass

        # 启动刷新线程
        self._start_flush_thread()

    def _start_flush_thread(self):
        """启动刷新线程"""
        self._flush_thread = threading.Thread(target=self._flush_loop, name="LogFlusher", daemon=True)
        self._flush_thread.start()

    def _flush_loop(self):
        """刷新循环"""
        while not self._stop_event.is_set():
            try:
                self._stop_event.wait(self.flush_interval)
                self.flush()
            except Exception:
                pass

    def emit(self, record):
        """添加日志记录"""
        try:
            msg = self.format(record)
            with self._lock:
                self._buffer.append(msg)

                # 检查是否需要刷新
                if len(self._buffer) >= self.buffer_size:
                    self._do_flush()
        except Exception:
            self.handleError(record)

    def flush(self):
        """刷新缓冲区"""
        with self._lock:
            self._do_flush()

    def _do_flush(self):
        """实际执行刷新"""
        if not self._buffer:
            return

        # 检查文件大小
        self._check_file_size()

        # 写入文件
        try:
            with open(self.filename, "a", encoding=self.encoding) as f:
                while self._buffer:
                    msg = self._buffer.popleft()
                    f.write(msg + "\n")
                f.flush()
        except Exception as e:
            # 写入失败，将消息放回缓冲区
            print(f"日志写入失败: {e}")

    def _check_file_size(self):
        """检查文件大小，必要时轮转"""
        try:
            if not os.path.exists(self.filename):
                return

            file_size = os.path.getsize(self.filename)
            if file_size < self.max_file_size:
                return

            # 轮转日志文件
            self._rotate_files()
        except Exception:
            pass

    def _rotate_files(self):
        """轮转日志文件"""
        try:
            # 删除最旧的备份
            oldest = f"{self.filename}.{self.backup_count}"
            if os.path.exists(oldest):
                os.remove(oldest)

            # 移动其他备份
            for i in range(self.backup_count - 1, 0, -1):
                src = f"{self.filename}.{i}"
                dst = f"{self.filename}.{i + 1}"
                if os.path.exists(src):
                    os.rename(src, dst)

            # 移动当前文件
            if os.path.exists(self.filename):
                os.rename(self.filename, f"{self.filename}.1")
        except Exception as e:
            print(f"日志轮转失败: {e}")

    def close(self):
        """关闭处理器"""
        self._stop_event.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        self.flush()
        super().close()


class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""

    def __init__(
        self,
        target_handler: logging.Handler,
        queue_size: int = 1000,
    ):
        """
        Args:
            target_handler: 目标处理器
            queue_size: 队列大小
        """
        super().__init__()
        self.target_handler = target_handler
        self._queue = deque(maxlen=queue_size)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._process_thread = None

        self._start_process_thread()

    def _start_process_thread(self):
        """启动处理线程"""
        self._process_thread = threading.Thread(target=self._process_loop, name="AsyncLogProcessor", daemon=True)
        self._process_thread.start()

    def _process_loop(self):
        """处理循环"""
        while not self._stop_event.is_set():
            try:
                self._process_queue()
                self._stop_event.wait(0.1)
            except Exception:
                pass

    def _process_queue(self):
        """处理队列"""
        while True:
            record = None
            with self._lock:
                if self._queue:
                    record = self._queue.popleft()

            if record is None:
                break

            try:
                self.target_handler.emit(record)
            except Exception:
                pass

    def emit(self, record):
        """添加日志记录"""
        with self._lock:
            self._queue.append(record)

    def flush(self):
        """刷新"""
        self._process_queue()
        self.target_handler.flush()

    def close(self):
        """关闭处理器"""
        self._stop_event.set()
        if self._process_thread:
            self._process_thread.join(timeout=5)
        self.flush()
        self.target_handler.close()
        super().close()


def setup_buffered_logging(
    log_file: str,
    level: int = logging.INFO,
    buffer_size: int = 100,
    flush_interval: float = 5.0,
    format_str: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> BufferedLogHandler:
    """
    设置缓冲日志

    Args:
        log_file: 日志文件路径
        level: 日志级别
        buffer_size: 缓冲区大小
        flush_interval: 刷新间隔
        format_str: 日志格式

    Returns:
        缓冲日志处理器
    """
    handler = BufferedLogHandler(
        filename=log_file,
        buffer_size=buffer_size,
        flush_interval=flush_interval,
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_str))

    # 添加到根日志记录器
    logging.getLogger().addHandler(handler)

    return handler
