"""
重试管理器模块
提供指数退避、断点续传等增强错误恢复机制
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """重试策略"""

    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"  # 线性退避
    FIXED = "fixed"  # 固定间隔


@dataclass
class RetryConfig:
    """重试配置"""

    max_retries: int = 5
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True  # 添加随机抖动
    retry_on_timeout: bool = True
    retry_on_connection_error: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """计算延迟时间"""
        if self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (2 ** (attempt - 1))
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * attempt
        else:
            delay = self.base_delay

        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random())

        return delay


@dataclass
class SyncCheckpoint:
    """同步断点信息"""

    form_name: str
    table_name: str
    sync_type: str
    start_row: int = 0
    total_fetched: int = 0
    total_inserted: int = 0
    last_page: int = 0
    filter_string: str = ""
    timestamp: str = ""
    status: str = "pending"
    next_start_row: int = 0
    last_written_record_keys: list[str] = field(default_factory=list)
    last_error_category: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def checkpoint_id(self) -> str:
        """生成断点ID"""
        key = f"{self.form_name}_{self.table_name}_{self.sync_type}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncCheckpoint":
        return cls(**data)


class CheckpointManager:
    """断点管理器"""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self._ensure_dir()

    def _ensure_dir(self):
        """确保断点目录存在"""
        if not os.path.exists(self.checkpoint_dir):
            try:
                os.makedirs(self.checkpoint_dir)
            except Exception as e:
                logger.warning(f"创建断点目录失败: {e}")

    def _get_checkpoint_path(self, checkpoint_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

    def save_checkpoint(self, checkpoint: SyncCheckpoint):
        """保存断点"""
        try:
            path = self._get_checkpoint_path(checkpoint.checkpoint_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"保存断点: {checkpoint.form_name} (行{checkpoint.start_row})")
        except Exception as e:
            logger.warning(f"保存断点失败: {e}")

    def load_checkpoint(self, form_name: str, table_name: str, sync_type: str) -> SyncCheckpoint | None:
        """加载断点"""
        try:
            key = f"{form_name}_{table_name}_{sync_type}"
            checkpoint_id = hashlib.md5(key.encode()).hexdigest()[:16]
            path = self._get_checkpoint_path(checkpoint_id)

            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                checkpoint = SyncCheckpoint.from_dict(data)
                logger.info(f"加载断点: {form_name} (行{checkpoint.start_row}, 已插入{checkpoint.total_inserted})")
                return checkpoint
        except Exception as e:
            logger.warning(f"加载断点失败: {e}")
        return None

    def clear_checkpoint(self, form_name: str, table_name: str, sync_type: str):
        """清除断点"""
        try:
            key = f"{form_name}_{table_name}_{sync_type}"
            checkpoint_id = hashlib.md5(key.encode()).hexdigest()[:16]
            path = self._get_checkpoint_path(checkpoint_id)

            if os.path.exists(path):
                os.remove(path)
                logger.info(f"清除断点: {form_name}")
        except Exception as e:
            logger.warning(f"清除断点失败: {e}")

    def clear_all_checkpoints(self):
        """清除所有断点"""
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.checkpoint_dir, filename))
            logger.info("已清除所有断点")
        except Exception as e:
            logger.warning(f"清除断点失败: {e}")

    def list_checkpoints(self) -> list:
        """列出所有断点"""
        checkpoints = []
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.endswith(".json"):
                    path = os.path.join(self.checkpoint_dir, filename)
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    checkpoints.append(data)
        except Exception as e:
            logger.warning(f"列出断点失败: {e}")
        return checkpoints


class RetryManager:
    """重试管理器"""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()
        self.checkpoint_manager = CheckpointManager()

    def execute_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        form_name: str = "",
        on_retry: Callable | None = None,
        on_checkpoint: Callable | None = None,
    ) -> tuple[Any, int]:
        """
        执行操作并自动重试

        Args:
            operation: 要执行的操作
            operation_name: 操作名称（用于日志）
            form_name: 表单名称
            on_retry: 重试时的回调
            on_checkpoint: 保存断点的回调

        Returns:
            (结果, 重试次数)
        """
        last_exception: Exception = Exception("No exception captured")

        for attempt in range(1, self.config.max_retries + 1):
            try:
                result = operation()
                return result, attempt - 1

            except Exception as e:
                last_exception = e
                error_msg = str(e)

                # 判断是否应该重试
                should_retry = self._should_retry(e, attempt)

                if not should_retry:
                    logger.error(f"[{form_name}] {operation_name} 失败，不重试: {error_msg}")
                    raise

                # 计算延迟
                delay = self.config.calculate_delay(attempt)

                logger.warning(
                    f"[{form_name}] {operation_name} 失败 (尝试 {attempt}/{self.config.max_retries}): {error_msg}"
                )
                logger.info(f"[{form_name}] 将在 {delay:.1f}秒 后重试...")

                # 调用重试回调
                if on_retry:
                    try:
                        on_retry(attempt, e)
                    except Exception:
                        pass

                # 保存断点
                if on_checkpoint:
                    try:
                        on_checkpoint(attempt)
                    except Exception:
                        pass

                # 等待
                time.sleep(delay)

        # 所有重试都失败
        logger.error(f"[{form_name}] {operation_name} 在 {self.config.max_retries} 次重试后仍然失败")
        raise last_exception

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.config.max_retries:
            return False

        error_msg = str(exception).lower()
        error_type = type(exception).__name__

        # 连接错误
        if self.config.retry_on_connection_error:
            connection_errors = ["connection", "timeout", "network", "socket", "refused", "reset", "broken pipe", "ssl"]
            if any(err in error_msg for err in connection_errors):
                return True

        # 超时错误
        if self.config.retry_on_timeout:
            if "timeout" in error_msg or "Timeout" in error_type:
                return True

        # HTTP 5xx 错误
        if isinstance(exception, requests.exceptions.HTTPError):
            response = getattr(exception, 'response', None)
            if response is not None and response.status_code >= 500:
                return True

        # 临时性数据库错误
        db_retry_errors = ["deadlock", "lock", "busy", "retry"]
        if any(err in error_msg for err in db_retry_errors):
            return True

        # 默认不重试
        return False


# 全局重试管理器实例
default_retry_config = RetryConfig(
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=True,
)

retry_manager = RetryManager(default_retry_config)
