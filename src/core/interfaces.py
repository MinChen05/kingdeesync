"""
接口定义层
定义核心模块的抽象接口，规范模块交互
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Callable
from enum import Enum


class SyncStatus(Enum):
    """同步状态枚举"""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    RUNNING = "running"
    CANCELLED = "cancelled"


class SyncType(Enum):
    """同步类型枚举"""

    INCREMENTAL = "incremental"
    FULL = "full"
    COMPLETE = "complete"
    RESET = "reset"


class IDataStore(ABC):
    """数据存储接口"""

    @abstractmethod
    def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接"""
        pass

    @abstractmethod
    def execute_query(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行查询"""
        pass

    @abstractmethod
    def execute_update(self, sql: str, params: tuple = None) -> int:
        """执行更新"""
        pass

    @abstractmethod
    def insert_batch(self, table: str, data: List[Dict[str, Any]]) -> int:
        """批量插入"""
        pass

    @abstractmethod
    def get_last_modify_time(self, table: str) -> Optional[str]:
        """获取最后修改时间"""
        pass


class IApiClient(ABC):
    """API客户端接口"""

    @abstractmethod
    def login(self) -> bool:
        """登录"""
        pass

    @abstractmethod
    def logout(self, force: bool = False) -> None:
        """登出"""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接"""
        pass

    @abstractmethod
    def query_data(
        self, form_id: str, query_params: Dict[str, Any], page_callback: Optional[Callable] = None
    ) -> Optional[List[Dict]]:
        """查询数据"""
        pass

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """是否已认证"""
        pass


class ISyncManager(ABC):
    """同步管理器接口"""

    @abstractmethod
    def sync_data(
        self,
        form_names: Optional[List[str]] = None,
        sync_type: SyncType = SyncType.INCREMENTAL,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """同步数据"""
        pass

    @abstractmethod
    def sync_single_form(self, form_name: str, sync_type: SyncType) -> Dict[str, Any]:
        """同步单个表单"""
        pass

    @abstractmethod
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        pass

    @abstractmethod
    def cancel_sync(self) -> None:
        """取消同步"""
        pass


class IScheduler(ABC):
    """调度器接口"""

    @abstractmethod
    def start(self) -> bool:
        """启动调度"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """停止调度"""
        pass

    @abstractmethod
    def configure_sync(self, sync_forms: List[str], interval_minutes: int = 60) -> None:
        """配置同步任务"""
        pass

    @abstractmethod
    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """是否运行中"""
        pass


class IConfigProvider(ABC):
    """配置提供者接口"""

    @abstractmethod
    def get_config(self, section: str, key: str = None) -> Any:
        """获取配置"""
        pass

    @abstractmethod
    def set_config(self, section: str, key: str, value: Any) -> None:
        """设置配置"""
        pass

    @abstractmethod
    def get_kingdee_config(self) -> Dict[str, Any]:
        """获取金蝶配置"""
        pass

    @abstractmethod
    def get_db_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        pass

    @abstractmethod
    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置"""
        pass

    @abstractmethod
    def save_config(self) -> None:
        """保存配置"""
        pass


class IHistoryManager(ABC):
    """历史记录管理器接口"""

    @abstractmethod
    def get_history(
        self,
        page: int = 1,
        page_size: int = 20,
        start_date: str = None,
        end_date: str = None,
        status: str = None,
        sync_type: str = None,
        form_name: str = None,
    ) -> Tuple[List[Dict], int]:
        """获取历史记录"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass

    @abstractmethod
    def record_sync(
        self, sync_type: str, form_name: str, status: str, record_count: int, duration: float, message: str = None
    ) -> None:
        """记录同步操作"""
        pass


class IMetricsCollector(ABC):
    """性能指标收集器接口"""

    @abstractmethod
    def start_sync(self, form_name: str) -> Any:
        """开始记录同步指标"""
        pass

    @abstractmethod
    def end_sync(self, form_name: str, success: bool = True) -> Any:
        """结束记录同步指标"""
        pass

    @abstractmethod
    def record_api_call(self, form_name: str, latency: float) -> None:
        """记录API调用"""
        pass

    @abstractmethod
    def record_insert(self, form_name: str, inserted: int, failed: int, duration: float) -> None:
        """记录插入操作"""
        pass

    @abstractmethod
    def get_global_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        pass

    @abstractmethod
    def export_summary(self) -> str:
        """导出摘要报告"""
        pass
