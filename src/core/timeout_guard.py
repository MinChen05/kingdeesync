"""
查询超时保护模块
实现分层超时策略，避免程序卡死
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TimeoutStrategy(Enum):
    """超时策略"""

    STRICT = "strict"  # 严格模式：严格执行超时
    FLEXIBLE = "flexible"  # 灵活模式：允许延长但有总限制
    UNLIMITED = "unlimited"  # 无限制模式：仅用于特殊情况


@dataclass
class TimeoutConfig:
    """超时配置"""

    page_timeout: int = 120  # 单页查询超时(秒)
    total_timeout: int = 3600  # 总查询超时(秒)
    heartbeat_timeout: int = 30  # 心跳超时(秒)
    retry_timeout_multiplier: float = 1.5  # 重试超时倍数
    max_page_timeout: int = 600  # 最大单页超时(秒)
    strategy: TimeoutStrategy = TimeoutStrategy.FLEXIBLE

    @classmethod
    def for_large_table(cls) -> "TimeoutConfig":
        """大表专用配置"""
        return cls(
            page_timeout=300,
            total_timeout=7200,
            max_page_timeout=900,
            strategy=TimeoutStrategy.FLEXIBLE,
        )

    @classmethod
    def for_normal_table(cls) -> "TimeoutConfig":
        """普通表配置"""
        return cls(
            page_timeout=60,
            total_timeout=1800,
            max_page_timeout=300,
            strategy=TimeoutStrategy.STRICT,
        )


class QueryTimeoutGuard:
    """查询超时守护器"""

    def __init__(self, config: Optional[TimeoutConfig] = None):
        self.config = config or TimeoutConfig()
        self._start_time: float = 0
        self._page_start_time: float = 0
        self._page_count: int = 0
        self._is_cancelled: bool = False
        self._lock = threading.Lock()

    def start(self):
        """开始计时"""
        self._start_time = time.time()
        self._page_start_time = time.time()
        self._page_count = 0
        self._is_cancelled = False

    def start_page(self):
        """开始新页"""
        with self._lock:
            self._page_start_time = time.time()
            self._page_count += 1

    def check_timeout(self, page_index: int = None) -> Optional[str]:
        """
        检查是否超时

        Returns:
            None: 未超时
            str: 超时原因
        """
        current_time = time.time()

        # 检查总超时
        total_elapsed = current_time - self._start_time
        if total_elapsed > self.config.total_timeout:
            return f"总查询超时: {total_elapsed:.0f}秒 > {self.config.total_timeout}秒"

        # 检查单页超时
        page_elapsed = current_time - self._page_start_time
        if page_elapsed > self.config.page_timeout:
            if self.config.strategy == TimeoutStrategy.STRICT:
                return f"第{page_index or self._page_count}页查询超时: {page_elapsed:.0f}秒"
            elif self.config.strategy == TimeoutStrategy.FLEXIBLE:
                # 灵活模式：记录警告但继续
                logger.warning(f"第{page_index or self._page_count}页查询超时({page_elapsed:.0f}秒)，继续等待...")
                return None

        return None

    def get_page_timeout(self, attempt: int = 1) -> int:
        """获取当前页超时时间"""
        base = self.config.page_timeout

        # 根据重试次数增加超时
        timeout = base * (self.config.retry_timeout_multiplier ** (attempt - 1))

        # 限制最大超时
        timeout = min(timeout, self.config.max_page_timeout)

        # 检查剩余总时间
        elapsed = time.time() - self._start_time
        remaining = self.config.total_timeout - elapsed
        if remaining < timeout:
            timeout = max(10, int(remaining))  # 至少保留10秒

        return int(timeout)

    def get_remaining_time(self) -> float:
        """获取剩余总时间"""
        elapsed = time.time() - self._start_time
        return max(0, self.config.total_timeout - elapsed)

    def get_elapsed_time(self) -> float:
        """获取已用时间"""
        return time.time() - self._start_time

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        current_time = time.time()
        return {
            "total_elapsed": round(current_time - self._start_time, 2),
            "page_count": self._page_count,
            "page_elapsed": round(current_time - self._page_start_time, 2),
            "remaining_time": round(self.get_remaining_time(), 2),
            "is_cancelled": self._is_cancelled,
        }

    def cancel(self):
        """取消查询"""
        with self._lock:
            self._is_cancelled = True
            logger.info("查询已被取消")

    @property
    def is_cancelled(self) -> bool:
        """是否已取消"""
        return self._is_cancelled


class TimeoutDecorator:
    """超时装饰器"""

    @staticmethod
    def with_timeout(
        timeout_config: Optional[TimeoutConfig] = None,
        on_timeout: Optional[Callable] = None,
    ):
        """为函数添加超时保护"""

        def decorator(func):
            def wrapper(*args, **kwargs):
                guard = QueryTimeoutGuard(timeout_config)
                guard.start()

                try:
                    # 将guard传递给被装饰的函数
                    kwargs["_timeout_guard"] = guard
                    return func(*args, **kwargs)
                except TimeoutError as e:
                    logger.error(f"函数 {func.__name__} 执行超时: {e}")
                    if on_timeout:
                        on_timeout(guard.get_stats())
                    raise
                finally:
                    stats = guard.get_stats()
                    logger.debug(f"函数 {func.__name__} 执行完成: {stats}")

            return wrapper

        return decorator


# 全局超时配置
default_timeout_config = TimeoutConfig.for_normal_table()
large_table_timeout_config = TimeoutConfig.for_large_table()

# 大表列表
LARGE_TABLES = frozenset(
    [
        "生产订单明细",
        "生产订单主表",
        "生产用料清单",
        "生产用料清单主表",
        "生产用料清单明细表",
        "预测订单",
        "科目余额表",
    ]
)


def get_timeout_config(form_id: str) -> TimeoutConfig:
    """根据表单ID获取超时配置"""
    if form_id in LARGE_TABLES:
        return TimeoutConfig.for_large_table()
    return TimeoutConfig.for_normal_table()
