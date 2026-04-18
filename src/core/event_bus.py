"""
事件总线模块
实现发布-订阅模式，解耦模块间通信
"""

import logging
import threading
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型枚举"""

    # 同步相关事件
    SYNC_STARTED = auto()
    SYNC_PROGRESS = auto()
    SYNC_COMPLETED = auto()
    SYNC_FAILED = auto()
    SYNC_CANCELLED = auto()

    # 连接相关事件
    CONNECTION_ESTABLISHED = auto()
    CONNECTION_LOST = auto()
    CONNECTION_RESTORED = auto()

    # 配置相关事件
    CONFIG_CHANGED = auto()
    CONFIG_SAVED = auto()
    CONFIG_RELOADED = auto()

    # 调度相关事件
    SCHEDULER_STARTED = auto()
    SCHEDULER_STOPPED = auto()
    SCHEDULER_TICK = auto()

    # 数据相关事件
    DATA_FETCHED = auto()
    DATA_INSERTED = auto()
    DATA_UPDATED = auto()

    # 错误相关事件
    ERROR_OCCURRED = auto()
    WARNING_OCCURRED = auto()

    # 自定义事件
    CUSTOM = auto()


@dataclass
class Event:
    """事件数据类"""

    event_type: EventType
    data: Any = None
    source: str = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.name,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


class EventHandler:
    """事件处理器包装类"""

    def __init__(
        self,
        callback: Callable[[Event], None],
        priority: int = 0,
        once: bool = False,
        filter_func: Optional[Callable[[Event], bool]] = None,
    ):
        self.callback = callback
        self.priority = priority
        self.once = once
        self.filter_func = filter_func
        self._called = False

    def handle(self, event: Event) -> bool:
        """
        处理事件

        Returns:
            是否应该移除此处理器
        """
        # 检查过滤条件
        if self.filter_func and not self.filter_func(event):
            return False

        try:
            self.callback(event)
            self._called = True
            return self.once  # 如果是一次性处理器，返回True表示需要移除
        except Exception as e:
            logger.error(f"事件处理失败: {e}")
            return False


class EventBus:
    """事件总线"""

    def __init__(self, max_history: int = 1000):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._lock = threading.RLock()
        self._history: List[Event] = []
        self._max_history = max_history

    def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[Event], None],
        priority: int = 0,
        once: bool = False,
        filter_func: Optional[Callable[[Event], bool]] = None,
    ) -> Callable:
        """
        订阅事件

        Args:
            event_type: 事件类型
            callback: 回调函数
            priority: 优先级（数值越大优先级越高）
            once: 是否只执行一次
            filter_func: 过滤函数

        Returns:
            取消订阅的函数
        """
        handler = EventHandler(callback, priority, once, filter_func)

        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            # 按优先级排序
            self._handlers[event_type].sort(key=lambda h: h.priority, reverse=True)

        def unsubscribe():
            self.unsubscribe(event_type, callback)

        return unsubscribe

    def unsubscribe(self, event_type: EventType, callback: Callable) -> bool:
        """
        取消订阅

        Returns:
            是否成功取消
        """
        with self._lock:
            if event_type not in self._handlers:
                return False

            handlers = self._handlers[event_type]
            for i, handler in enumerate(handlers):
                if handler.callback == callback:
                    handlers.pop(i)
                    return True
            return False

    def publish(self, event: Event) -> int:
        """
        发布事件

        Args:
            event: 事件对象

        Returns:
            处理的处理器数量
        """
        with self._lock:
            # 记录历史
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

            # 获取处理器
            handlers = self._handlers.get(event.event_type, [])
            if not handlers:
                return 0

            # 复制列表避免修改时迭代
            handlers = handlers[:]

        # 处理事件
        handled_count = 0
        to_remove = []

        for handler in handlers:
            try:
                should_remove = handler.handle(event)
                handled_count += 1
                if should_remove:
                    to_remove.append((event.event_type, handler))
            except Exception as e:
                logger.error(f"事件处理异常: {e}")

        # 移除一次性处理器
        with self._lock:
            for evt_type, handler in to_remove:
                if evt_type in self._handlers and handler in self._handlers[evt_type]:
                    self._handlers[evt_type].remove(handler)

        return handled_count

    def publish_simple(self, event_type: EventType, data: Any = None, source: str = None) -> int:
        """
        简化发布方法
        """
        event = Event(event_type=event_type, data=data, source=source)
        return self.publish(event)

    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """
        获取事件历史
        """
        with self._lock:
            if event_type:
                filtered = [e for e in self._history if e.event_type == event_type]
            else:
                filtered = self._history
            return filtered[-limit:]

    def clear_history(self):
        """清空历史"""
        with self._lock:
            self._history.clear()

    def clear_handlers(self, event_type: Optional[EventType] = None):
        """
        清空处理器
        """
        with self._lock:
            if event_type:
                self._handlers.pop(event_type, None)
            else:
                self._handlers.clear()

    def get_handler_count(self, event_type: Optional[EventType] = None) -> int:
        """获取处理器数量"""
        with self._lock:
            if event_type:
                return len(self._handlers.get(event_type, []))
            return sum(len(handlers) for handlers in self._handlers.values())

    def has_subscribers(self, event_type: EventType) -> bool:
        """检查是否有订阅者"""
        with self._lock:
            return len(self._handlers.get(event_type, [])) > 0


# 全局事件总线实例
event_bus = EventBus(max_history=1000)


# 便捷装饰器
def event_handler(event_type: EventType, priority: int = 0, once: bool = False):
    """
    事件处理装饰器

    使用示例:
        @event_handler(EventType.SYNC_COMPLETED)
        def on_sync_completed(event):
            print(f"同步完成: {event.data}")
    """

    def decorator(func):
        event_bus.subscribe(event_type, func, priority=priority, once=once)
        return func

    return decorator


# 事件数据辅助类
class EventData:
    """事件数据辅助类"""

    @staticmethod
    def sync_started(form_names: List[str], sync_type: str) -> Dict:
        return {
            "form_names": form_names,
            "sync_type": sync_type,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def sync_progress(form_name: str, progress: int, message: str) -> Dict:
        return {
            "form_name": form_name,
            "progress": progress,
            "message": message,
        }

    @staticmethod
    def sync_completed(results: Dict[str, Any]) -> Dict:
        return {
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def error_occurred(error: Exception, context: str = None) -> Dict:
        return {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
        }

    @staticmethod
    def config_changed(section: str, key: str, old_value: Any, new_value: Any) -> Dict:
        return {
            "section": section,
            "key": key,
            "old_value": old_value,
            "new_value": new_value,
        }
