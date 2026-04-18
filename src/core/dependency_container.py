"""
依赖注入容器
实现轻量级依赖注入，解耦模块间依赖
"""

import logging
from typing import Dict, Any, Callable
from threading import Lock

logger = logging.getLogger(__name__)


class DependencyContainer:
    """依赖注入容器"""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._lock = Lock()

    def register(self, name: str, instance: Any = None, factory: Callable = None, singleton: bool = True):
        """
        注册服务

        Args:
            name: 服务名称
            instance: 服务实例
            factory: 工厂函数
            singleton: 是否单例
        """
        with self._lock:
            if instance is not None:
                self._services[name] = instance
                self._singletons[name] = instance
            elif factory is not None:
                self._factories[name] = factory
                if singleton:
                    # 立即创建单例
                    self._singletons[name] = factory()

    def resolve(self, name: str) -> Any:
        """
        解析服务

        Args:
            name: 服务名称

        Returns:
            服务实例
        """
        with self._lock:
            # 优先返回已注册的实例
            if name in self._services:
                return self._services[name]

            # 返回单例
            if name in self._singletons:
                return self._singletons[name]

            # 使用工厂创建
            if name in self._factories:
                return self._factories[name]()

            raise KeyError(f"服务未注册: {name}")

    def has(self, name: str) -> bool:
        """检查服务是否已注册"""
        with self._lock:
            return name in self._services or name in self._singletons or name in self._factories

    def unregister(self, name: str):
        """取消注册"""
        with self._lock:
            self._services.pop(name, None)
            self._factories.pop(name, None)
            self._singletons.pop(name, None)

    def clear(self):
        """清空容器"""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._singletons.clear()

    def get_registered(self) -> list:
        """获取所有已注册的服务名称"""
        with self._lock:
            all_names = set()
            all_names.update(self._services.keys())
            all_names.update(self._factories.keys())
            all_names.update(self._singletons.keys())
            return list(all_names)


# 服务名称常量
class ServiceNames:
    """服务名称常量"""

    CONFIG_MANAGER = "config_manager"
    DB_MANAGER = "db_manager"
    API_CLIENT = "api_client"
    SYNC_MANAGER = "sync_manager"
    SCHEDULER = "scheduler"
    HISTORY_MANAGER = "history_manager"
    METRICS_COLLECTOR = "metrics_collector"
    EVENT_BUS = "event_bus"
    POOL_OPTIMIZER = "pool_optimizer"
    TIMEOUT_GUARD = "timeout_guard"


# 全局依赖容器
container = DependencyContainer()


def setup_dependencies():
    """设置默认依赖"""
    from src.core.event_bus import event_bus
    from src.core.pool_optimizer import dynamic_pool_manager, pool_monitor

    # 注册事件总线
    container.register(ServiceNames.EVENT_BUS, instance=event_bus)

    # 注册连接池优化器
    container.register(ServiceNames.POOL_OPTIMIZER, instance=dynamic_pool_manager)

    # 延迟加载其他服务
    def create_config_manager():
        from src.config.config_manager import config_manager

        return config_manager

    def create_db_manager():
        from src.core.mysql_manager import mysql_manager

        return mysql_manager

    def create_api_client():
        from src.core.kingdee_api import kingdee_client

        return kingdee_client

    def create_sync_manager():
        from src.core.data_sync import sync_manager

        return sync_manager

    def create_scheduler():
        from src.core.scheduler import auto_scheduler

        return auto_scheduler

    def create_history_manager():
        from src.core.history_manager import history_manager

        return history_manager

    def create_metrics_collector():
        from src.core.metrics import metrics_collector

        return metrics_collector

    # 注册工厂函数
    container.register(ServiceNames.CONFIG_MANAGER, factory=create_config_manager)
    container.register(ServiceNames.DB_MANAGER, factory=create_db_manager)
    container.register(ServiceNames.API_CLIENT, factory=create_api_client)
    container.register(ServiceNames.SYNC_MANAGER, factory=create_sync_manager)
    container.register(ServiceNames.SCHEDULER, factory=create_scheduler)
    container.register(ServiceNames.HISTORY_MANAGER, factory=create_history_manager)
    container.register(ServiceNames.METRICS_COLLECTOR, factory=create_metrics_collector)


# 便捷函数
def get_service(name: str) -> Any:
    """获取服务"""
    return container.resolve(name)


def get_config_manager():
    """获取配置管理器"""
    return get_service(ServiceNames.CONFIG_MANAGER)


def get_db_manager():
    """获取数据库管理器"""
    return get_service(ServiceNames.DB_MANAGER)


def get_api_client():
    """获取API客户端"""
    return get_service(ServiceNames.API_CLIENT)


def get_sync_manager():
    """获取同步管理器"""
    return get_service(ServiceNames.SYNC_MANAGER)


def get_scheduler():
    """获取调度器"""
    return get_service(ServiceNames.SCHEDULER)


def get_history_manager():
    """获取历史管理器"""
    return get_service(ServiceNames.HISTORY_MANAGER)


def get_event_bus():
    """获取事件总线"""
    return get_service(ServiceNames.EVENT_BUS)


# 装饰器：自动注入依赖
def inject(*service_names: str):
    """
    依赖注入装饰器

    使用示例:
        @inject(ServiceNames.DB_MANAGER, ServiceNames.API_CLIENT)
        def my_function(db, api):
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # 解析依赖
            services = [get_service(name) for name in service_names]
            # 调用函数
            return func(*services, *args, **kwargs)

        return wrapper

    return decorator


# 初始化依赖
setup_dependencies()
