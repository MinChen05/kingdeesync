"""
连接池优化模块
实现动态连接池调优功能
"""

import logging
import threading
import time
from typing import Dict, Any
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """连接池性能指标"""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    wait_queue_size: int = 0
    avg_wait_time: float = 0.0
    max_wait_time: float = 0.0
    connection_errors: int = 0
    total_requests: int = 0
    last_adjustment_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "总连接数": self.total_connections,
            "活跃连接": self.active_connections,
            "空闲连接": self.idle_connections,
            "等待队列": self.wait_queue_size,
            "平均等待时间": f"{self.avg_wait_time:.3f}秒",
            "最大等待时间": f"{self.max_wait_time:.3f}秒",
            "连接错误": self.connection_errors,
            "总请求数": self.total_requests,
        }


class DynamicConnectionPool:
    """动态连接池管理器"""

    def __init__(
        self,
        base_max_connections: int = 10,
        min_connections: int = 2,
        max_connections_limit: int = 50,
        adjustment_interval: float = 30.0,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.3,
    ):
        """
        Args:
            base_max_connections: 基础最大连接数
            min_connections: 最小连接数
            max_connections_limit: 最大连接数上限
            adjustment_interval: 调整间隔(秒)
            scale_up_threshold: 扩容阈值(使用率)
            scale_down_threshold: 缩容阈值(使用率)
        """
        self.base_max = base_max_connections
        self.min_connections = min_connections
        self.max_limit = max_connections_limit
        self.adjustment_interval = adjustment_interval
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold

        # 当前配置
        self.current_max = base_max_connections
        self.current_mincached = min(2, base_max_connections)
        self.current_maxcached = min(5, base_max_connections)

        # 性能指标
        self.metrics = PoolMetrics()
        self._wait_times = deque(maxlen=100)  # 最近100次等待时间
        self._lock = threading.Lock()
        self._last_adjustment = time.time()

        # 回调函数
        self._on_config_changed = None

    def set_config_changed_callback(self, callback):
        """设置配置变更回调"""
        self._on_config_changed = callback

    def record_request(self, wait_time: float, success: bool = True):
        """记录请求"""
        with self._lock:
            self.metrics.total_requests += 1

            if success:
                self._wait_times.append(wait_time)

                # 更新平均等待时间
                if self._wait_times:
                    self.metrics.avg_wait_time = sum(self._wait_times) / len(self._wait_times)
                    self.metrics.max_wait_time = max(self._wait_times)
            else:
                self.metrics.connection_errors += 1

    def record_connection_state(self, active: int, idle: int, waiting: int = 0):
        """记录连接状态"""
        with self._lock:
            self.metrics.active_connections = active
            self.metrics.idle_connections = idle
            self.metrics.wait_queue_size = waiting
            self.metrics.total_connections = active + idle

    def should_adjust(self) -> bool:
        """检查是否应该调整配置"""
        current_time = time.time()
        return (current_time - self._last_adjustment) >= self.adjustment_interval

    def calculate_optimal_config(self) -> Dict[str, Any]:
        """计算最优配置"""
        with self._lock:
            if not self.should_adjust():
                return self._get_current_config()

            # 计算当前使用率
            if self.metrics.total_connections > 0:
                usage_rate = self.metrics.active_connections / self.current_max
            else:
                usage_rate = 0.0

            # 判断是否需要调整
            new_max = self.current_max

            if usage_rate >= self.scale_up_threshold:
                # 需要扩容
                new_max = min(self.max_limit, int(self.current_max * 1.5))
                if new_max != self.current_max:
                    logger.info(f"连接池扩容: {self.current_max} -> {new_max} (使用率: {usage_rate:.1%})")

            elif usage_rate <= self.scale_down_threshold and self.metrics.wait_queue_size == 0:
                # 需要缩容
                new_max = max(self.min_connections, int(self.current_max * 0.7))
                if new_max != self.current_max:
                    logger.info(f"连接池缩容: {self.current_max} -> {new_max} (使用率: {usage_rate:.1%})")

            # 检查等待队列
            if self.metrics.wait_queue_size > 0 and usage_rate > 0.5:
                # 有等待且使用率较高，扩容
                new_max = min(self.max_limit, self.current_max + self.metrics.wait_queue_size)
                if new_max != self.current_max:
                    logger.info(f"连接池扩容(队列等待): {self.current_max} -> {new_max}")

            # 更新配置
            if new_max != self.current_max:
                self.current_max = new_max
                self.current_mincached = min(max(2, new_max // 5), new_max)
                self.current_maxcached = min(max(5, new_max // 2), new_max)
                self._last_adjustment = time.time()
                self.metrics.last_adjustment_time = time.time()

                # 触发回调
                if self._on_config_changed:
                    self._on_config_changed(self._get_current_config())

            return self._get_current_config()

    def _get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            "maxconnections": self.current_max,
            "mincached": self.current_mincached,
            "maxcached": self.current_maxcached,
            "maxshared": max(3, self.current_max // 3),
        }

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置(公开方法)"""
        return self._get_current_config()

    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return self.metrics.to_dict()

    def reset(self):
        """重置为初始配置"""
        with self._lock:
            self.current_max = self.base_max
            self.current_mincached = min(2, self.base_max)
            self.current_maxcached = min(5, self.base_max)
            self.metrics = PoolMetrics()
            self._wait_times.clear()
            self._last_adjustment = time.time()


class PoolMonitor:
    """连接池监控器"""

    def __init__(self, pool_manager: DynamicConnectionPool):
        self.pool_manager = pool_manager
        self._monitor_thread = None
        self._stop_event = threading.Event()

    def start(self, interval: float = 60.0):
        """启动监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval,), name="PoolMonitor", daemon=True
        )
        self._monitor_thread.start()
        logger.info("连接池监控已启动")

    def stop(self):
        """停止监控"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("连接池监控已停止")

    def _monitor_loop(self, interval: float):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 计算最优配置（自动调整连接池大小）
                self.pool_manager.calculate_optimal_config()

                # 记录指标
                metrics = self.pool_manager.get_metrics()
                logger.debug(f"连接池指标: {metrics}")

            except Exception as e:
                logger.error(f"连接池监控异常: {e}")

            # 等待下次检查
            self._stop_event.wait(interval)


# 全局实例
dynamic_pool_manager = DynamicConnectionPool(
    base_max_connections=10,
    min_connections=2,
    max_connections_limit=50,
    adjustment_interval=30.0,
    scale_up_threshold=0.8,
    scale_down_threshold=0.3,
)

pool_monitor = PoolMonitor(dynamic_pool_manager)
