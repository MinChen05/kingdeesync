"""
流式数据处理模块
实现高效的数据流式处理，支持批量处理和内存控制
"""

import logging
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamingConfig:
    """流式处理配置"""

    batch_size: int = 1000  # 批处理大小
    max_queue_size: int = 5  # 最大队列大小
    memory_limit_mb: int = 500  # 内存限制(MB)
    flush_interval: float = 5.0  # 刷新间隔(秒)
    enable_compression: bool = False  # 启用压缩


class MemoryMonitor:
    """内存监控器"""

    def __init__(self, limit_mb: int = 500):
        self.limit_bytes = limit_mb * 1024 * 1024
        self._current_bytes = 0
        self._lock = threading.Lock()

    def add(self, size_bytes: int):
        """添加内存使用量"""
        with self._lock:
            self._current_bytes += size_bytes

    def release(self, size_bytes: int):
        """释放内存使用量"""
        with self._lock:
            self._current_bytes = max(0, self._current_bytes - size_bytes)

    def is_limit_exceeded(self) -> bool:
        """检查是否超过限制"""
        with self._lock:
            return self._current_bytes > self.limit_bytes

    def get_usage(self) -> float:
        """获取使用率"""
        with self._lock:
            return self._current_bytes / self.limit_bytes if self.limit_bytes > 0 else 0

    def reset(self):
        """重置"""
        with self._lock:
            self._current_bytes = 0


class StreamingProcessor:
    """流式处理器"""

    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
        self._queue = queue.Queue(maxsize=self.config.max_queue_size)
        self._memory_monitor = MemoryMonitor(self.config.memory_limit_mb)
        self._errors = []
        self._is_running = False
        self._worker_thread = None
        self._stats = {
            "total_fetched": 0,
            "total_processed": 0,
            "total_errors": 0,
            "start_time": 0,
            "end_time": 0,
        }

    def process_stream(
        self,
        data_source: Generator[List[Any], None, None],
        processor: Callable[[List[Any]], int],
        error_handler: Optional[Callable[[Exception, List[Any]], None]] = None,
    ) -> dict:
        """
        处理数据流

        Args:
            data_source: 数据源生成器
            processor: 数据处理器函数，返回处理成功的数量
            error_handler: 错误处理器

        Returns:
            处理统计信息
        """
        self._is_running = True
        self._errors = []
        self._stats = {
            "total_fetched": 0,
            "total_processed": 0,
            "total_errors": 0,
            "start_time": time.time(),
            "end_time": 0,
        }

        def worker():
            """工作线程"""
            while self._is_running:
                try:
                    # 从队列获取数据
                    item = self._queue.get(timeout=1.0)
                    if item is None:  # 结束信号
                        self._queue.task_done()
                        break

                    batch, batch_size_bytes = item
                    try:
                        # 处理数据
                        count = processor(batch)
                        self._stats["total_processed"] += count

                        # 释放内存
                        self._memory_monitor.release(batch_size_bytes)

                    except Exception as e:
                        self._stats["total_errors"] += 1
                        self._errors.append(e)
                        logger.error(f"处理批次数据失败: {e}")

                        if error_handler:
                            try:
                                error_handler(e, batch)
                            except Exception:
                                pass

                        # 即使失败也要释放内存
                        self._memory_monitor.release(batch_size_bytes)

                    finally:
                        self._queue.task_done()

                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"工作线程异常: {e}")
                    break

        # 启动工作线程
        self._worker_thread = threading.Thread(target=worker, name="StreamingWorker")
        self._worker_thread.start()

        try:
            # 从数据源读取并放入队列
            batch = []
            batch_size_bytes = 0

            for item in data_source:
                if not self._is_running:
                    break

                self._stats["total_fetched"] += 1

                # 估算数据大小
                item_size = self._estimate_size(item)
                batch.append(item)
                batch_size_bytes += item_size

                # 检查是否需要刷新批次
                should_flush = len(batch) >= self.config.batch_size or self._memory_monitor.is_limit_exceeded()

                if should_flush and batch:
                    # 等待内存释放
                    while self._memory_monitor.is_limit_exceeded() and self._is_running:
                        time.sleep(0.1)

                    self._memory_monitor.add(batch_size_bytes)
                    self._queue.put((batch, batch_size_bytes))
                    batch = []
                    batch_size_bytes = 0

            # 处理剩余数据
            if batch:
                self._memory_monitor.add(batch_size_bytes)
                self._queue.put((batch, batch_size_bytes))

            # 等待所有任务完成
            self._queue.join()

            # 发送结束信号
            self._queue.put(None)
            self._worker_thread.join(timeout=10)

        except Exception as e:
            logger.error(f"数据流处理失败: {e}")
            self._errors.append(e)
            raise
        finally:
            self._is_running = False
            self._stats["end_time"] = time.time()

        return self.get_stats()

    def _estimate_size(self, obj: Any) -> int:
        """估算对象大小"""
        import sys

        try:
            return sys.getsizeof(obj)
        except Exception:
            return 1024  # 默认1KB

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats["start_time"] > 0 and stats["end_time"] > 0:
            stats["duration"] = stats["end_time"] - stats["start_time"]
            if stats["duration"] > 0:
                stats["throughput"] = stats["total_processed"] / stats["duration"]
        else:
            stats["duration"] = 0
            stats["throughput"] = 0

        stats["errors"] = len(self._errors)
        stats["memory_usage"] = self._memory_monitor.get_usage()

        return stats

    def stop(self):
        """停止处理"""
        self._is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)


@contextmanager
def streaming_processor(config: Optional[StreamingConfig] = None):
    """流式处理器上下文管理器"""
    processor = StreamingProcessor(config)
    try:
        yield processor
    finally:
        processor.stop()


class BatchProcessor:
    """批量处理器"""

    def __init__(
        self,
        batch_size: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def process_batches(
        self,
        items: List[Any],
        processor: Callable[[List[Any]], int],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        """
        批量处理数据

        Args:
            items: 数据列表
            processor: 处理函数
            progress_callback: 进度回调

        Returns:
            处理统计信息
        """
        total = len(items)
        processed = 0
        failed = 0
        errors = []

        for i in range(0, total, self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_num = i // self.batch_size + 1

            # 重试逻辑
            for attempt in range(self.max_retries):
                try:
                    count = processor(batch)
                    processed += count
                    break
                except Exception as e:
                    logger.warning(f"批次 {batch_num} 处理失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        failed += len(batch)
                        errors.append(e)

            # 进度回调
            if progress_callback:
                progress_callback(min(i + self.batch_size, total), total)

        return {
            "total": total,
            "processed": processed,
            "failed": failed,
            "errors": len(errors),
        }
