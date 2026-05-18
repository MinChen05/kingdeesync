"""
异步数据加载器模块
用于GUI异步加载数据，避免界面卡顿
"""

import logging
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class AsyncDataLoader(QThread):
    """异步数据加载器"""

    # 信号
    data_loaded = Signal(object)  # 数据加载完成
    error_occurred = Signal(str)  # 发生错误
    progress_updated = Signal(int, int)  # 进度更新 (当前, 总数)

    def __init__(self, load_func: Callable, *args, parent=None, **kwargs):
        """
        Args:
            load_func: 数据加载函数
            *args: 位置参数
            parent: 父对象
            **kwargs: 关键字参数
        """
        super().__init__(parent)
        self.load_func = load_func
        self.args = args
        self.kwargs = kwargs
        self._result = None
        self._error = None
        self._is_cancelled = False

    def run(self):
        """执行加载"""
        try:
            self._result = self.load_func(*self.args, **self.kwargs)
            if not self._is_cancelled:
                self.data_loaded.emit(self._result)
        except Exception as e:
            self._error = e
            logger.error(f"异步加载失败: {e}")
            if not self._is_cancelled:
                self.error_occurred.emit(str(e))

    def cancel(self):
        """取消加载"""
        self._is_cancelled = True

    @property
    def result(self):
        """获取结果"""
        return self._result

    @property
    def error(self):
        """获取错误"""
        return self._error


class AsyncBatchLoader(QThread):
    """异步批量加载器"""

    # 信号
    item_loaded = Signal(int, object)  # 单项加载完成 (索引, 数据)
    batch_loaded = Signal(list)  # 批量加载完成
    all_completed = Signal(list)  # 全部完成
    error_occurred = Signal(int, str)  # 发生错误 (索引, 错误信息)
    progress_updated = Signal(int, int)  # 进度更新

    def __init__(
        self,
        load_func: Callable,
        items: list,
        batch_size: int = 10,
        parent=None,
    ):
        """
        Args:
            load_func: 单项加载函数
            items: 待加载项列表
            batch_size: 批量大小
            parent: 父对象
        """
        super().__init__(parent)
        self.load_func = load_func
        self.items = items
        self.batch_size = batch_size
        self._results = []
        self._errors = []
        self._is_cancelled = False

    def run(self):
        """执行批量加载"""
        total = len(self.items)

        for i in range(0, total, self.batch_size):
            if self._is_cancelled:
                break

            batch = self.items[i : i + self.batch_size]
            batch_results = []

            for j, item in enumerate(batch):
                if self._is_cancelled:
                    break

                try:
                    result = self.load_func(item)
                    batch_results.append(result)
                    self.item_loaded.emit(i + j, result)
                except Exception as e:
                    logger.error(f"加载项 {i + j} 失败: {e}")
                    self._errors.append((i + j, e))
                    self.error_occurred.emit(i + j, str(e))
                    batch_results.append(None)

            self._results.extend(batch_results)
            self.batch_loaded.emit(batch_results)
            self.progress_updated.emit(min(i + self.batch_size, total), total)

        if not self._is_cancelled:
            self.all_completed.emit(self._results)

    def cancel(self):
        """取消加载"""
        self._is_cancelled = True

    @property
    def results(self):
        """获取结果"""
        return self._results

    @property
    def errors(self):
        """获取错误列表"""
        return self._errors


class AsyncManager:
    """异步管理器"""

    def __init__(self):
        self._loaders = {}

    def start_load(
        self,
        name: str,
        load_func: Callable,
        *args,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        **kwargs,
    ) -> AsyncDataLoader:
        """
        启动异步加载

        Args:
            name: 任务名称
            load_func: 加载函数
            on_success: 成功回调
            on_error: 失败回调

        Returns:
            异步加载器
        """
        # 取消同名任务
        if name in self._loaders:
            self._loaders[name].cancel()

        loader = AsyncDataLoader(load_func, *args, **kwargs)

        if on_success:
            loader.data_loaded.connect(on_success)
        if on_error:
            loader.error_occurred.connect(on_error)

        # 清理完成的任务
        loader.finished.connect(lambda: self._cleanup(name))

        self._loaders[name] = loader
        loader.start()

        return loader

    def _cleanup(self, name: str):
        """清理任务"""
        if name in self._loaders:
            del self._loaders[name]

    def cancel_all(self):
        """取消所有任务"""
        for loader in self._loaders.values():
            loader.cancel()
        self._loaders.clear()

    def cancel(self, name: str):
        """取消指定任务"""
        if name in self._loaders:
            self._loaders[name].cancel()
            del self._loaders[name]


# 全局异步管理器
async_manager = AsyncManager()
