"""
定时同步功能模块
负责管理自动定时同步任务
"""
import schedule
import time
import threading
import logging
from datetime import datetime
from typing import List, Callable, Optional
from enum import Enum

from src.core.data_sync import sync_manager, SyncType
from src.config.config_manager import config_manager

# 配置日志
logger = logging.getLogger(__name__)

class SchedulerStatus(Enum):
    """调度器状态枚举"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"

class AutoSyncScheduler:
    """自动同步调度器"""
    
    def __init__(self):
        self.status = SchedulerStatus.STOPPED
        self.scheduler_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.sync_forms = []  # 要同步的表单列表
        self.sync_type = SyncType.INCREMENTAL
        self.status_callbacks = []  # 状态变化回调
        self.sync_callbacks = []   # 同步完成回调
        
        # 设置同步管理器的回调
        sync_manager.add_sync_callback(self._on_sync_progress)
    
    def add_status_callback(self, callback: Callable):
        """添加状态变化回调"""
        self.status_callbacks.append(callback)
    
    def add_sync_callback(self, callback: Callable):
        """添加同步完成回调"""
        self.sync_callbacks.append(callback)
    
    def _notify_status_change(self, status: SchedulerStatus, message: str = ""):
        """通知状态变化"""
        for callback in self.status_callbacks:
            try:
                callback(status, message)
            except Exception as e:
                logger.error(f"状态变化回调执行失败: {str(e)}")
    
    def _notify_sync_complete(self, result: dict):
        """通知同步完成"""
        for callback in self.sync_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"同步完成回调执行失败: {str(e)}")
    
    def _on_sync_progress(self, message: str, progress: int):
        """同步进度回调"""
        logger.info(f"同步进度: {message} ({progress}%)")
    
    def configure_sync(self, forms: List[str], sync_type: SyncType = SyncType.INCREMENTAL, 
                      interval_minutes: int = 60):
        """配置同步参数"""
        self.sync_forms = forms
        self.sync_type = sync_type
        
        # 清除现有的定时任务
        schedule.clear()
        
        # 设置新的定时任务
        schedule.every(interval_minutes).minutes.do(self._execute_sync)
        
        # 更新配置
        config_manager.update_config('SYNC', 'sync_interval', str(interval_minutes))
        config_manager.update_config('SYNC', 'sync_type', sync_type.value)
        
        logger.info(f"已配置定时同步: 表单={forms}, 类型={sync_type.value}, 间隔={interval_minutes}分钟")
    
    def start(self):
        """启动定时同步"""
        if self.status == SchedulerStatus.RUNNING:
            logger.warning("定时同步已在运行中")
            return
        
        if not self.sync_forms:
            logger.error("未配置同步表单，无法启动定时同步")
            return
        
        self.status = SchedulerStatus.RUNNING
        self.stop_event.clear()
        self.pause_event.clear()
        
        # 启动调度器线程
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        # 更新配置
        config_manager.update_config('SYNC', 'auto_sync', 'True')
        
        self._notify_status_change(SchedulerStatus.RUNNING, "定时同步已启动")
        logger.info("定时同步已启动")
    
    def pause(self):
        """暂停定时同步"""
        if self.status != SchedulerStatus.RUNNING:
            logger.warning("定时同步未在运行中，无法暂停")
            return
        
        self.status = SchedulerStatus.PAUSED
        self.pause_event.set()
        
        self._notify_status_change(SchedulerStatus.PAUSED, "定时同步已暂停")
        logger.info("定时同步已暂停")
    
    def resume(self):
        """恢复定时同步"""
        if self.status != SchedulerStatus.PAUSED:
            logger.warning("定时同步未暂停，无法恢复")
            return
        
        self.status = SchedulerStatus.RUNNING
        self.pause_event.clear()
        
        self._notify_status_change(SchedulerStatus.RUNNING, "定时同步已恢复")
        logger.info("定时同步已恢复")
    
    def stop(self):
        """停止定时同步"""
        if self.status == SchedulerStatus.STOPPED:
            logger.warning("定时同步已停止")
            return
        
        self.status = SchedulerStatus.STOPPED
        self.stop_event.set()
        self.pause_event.clear()
        
        # 等待调度器线程结束
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        # 清除所有定时任务
        schedule.clear()
        
        # 更新配置
        config_manager.update_config('SYNC', 'auto_sync', 'False')
        
        self._notify_status_change(SchedulerStatus.STOPPED, "定时同步已停止")
        logger.info("定时同步已停止")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        logger.info("定时同步调度器开始运行")
        
        while not self.stop_event.is_set():
            try:
                # 检查是否暂停
                if self.pause_event.is_set():
                    time.sleep(1)
                    continue
                
                # 运行定时任务
                schedule.run_pending()
                
                # 休眠1秒
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"调度器运行异常: {str(e)}")
                time.sleep(5)  # 异常时等待5秒再继续
        
        logger.info("定时同步调度器已停止")
    
    def _execute_sync(self):
        """执行同步任务"""
        if self.status != SchedulerStatus.RUNNING:
            return
        
        logger.info(f"开始执行定时同步任务: {self.sync_forms}")
        
        try:
            # 执行同步
            result = sync_manager.sync_data(self.sync_forms, self.sync_type)
            
            # 通知同步完成
            self._notify_sync_complete(result)
            
            # 记录同步结果
            if result['status'] == 'success':
                logger.info(f"定时同步成功: {result['message']}")
            else:
                logger.warning(f"定时同步失败: {result['message']}")
                
        except Exception as e:
            error_msg = f"定时同步执行异常: {str(e)}"
            logger.error(error_msg)
            
            # 创建错误结果
            error_result = {
                'status': 'failed',
                'message': error_msg,
                'total_records': 0,
                'start_time': datetime.now(),
                'end_time': datetime.now(),
                'duration': 0,
                'details': {}
            }
            self._notify_sync_complete(error_result)
    
    def execute_manual_sync(self) -> dict:
        """执行手动同步"""
        if not self.sync_forms:
            return {
                'status': 'failed',
                'message': '未配置同步表单',
                'total_records': 0,
                'details': {}
            }
        
        logger.info(f"开始执行手动同步: {self.sync_forms}")
        
        try:
            result = sync_manager.sync_data(self.sync_forms, self.sync_type)
            self._notify_sync_complete(result)
            return result
        except Exception as e:
            error_msg = f"手动同步执行异常: {str(e)}"
            logger.error(error_msg)
            return {
                'status': 'failed',
                'message': error_msg,
                'total_records': 0,
                'details': {}
            }
    
    def get_next_sync_time(self) -> Optional[datetime]:
        """获取下次同步时间"""
        if not schedule.jobs:
            return None
        
        try:
            next_run = schedule.next_run()
            return next_run
        except Exception:
            return None
    
    def get_status_info(self) -> dict:
        """获取状态信息"""
        next_sync = self.get_next_sync_time()
        
        return {
            'status': self.status.value,
            'sync_forms': self.sync_forms,
            'sync_type': self.sync_type.value if self.sync_type else None,
            'next_sync_time': next_sync.strftime('%Y-%m-%d %H:%M:%S') if next_sync else None,
            'jobs_count': len(schedule.jobs)
        }
    
    def update_interval(self, interval_minutes: int):
        """更新同步间隔"""
        if interval_minutes <= 0:
            logger.error("同步间隔必须大于0")
            return False
        
        # 重新配置同步
        self.configure_sync(self.sync_forms, self.sync_type, interval_minutes)
        
        logger.info(f"同步间隔已更新为 {interval_minutes} 分钟")
        return True
    
    def update_sync_type(self, sync_type: SyncType):
        """更新同步类型"""
        self.sync_type = sync_type
        config_manager.update_config('SYNC', 'sync_type', sync_type.value)
        logger.info(f"同步类型已更新为 {sync_type.value}")
    
    def load_config_and_start(self):
        """从配置文件加载设置并启动（如果需要）"""
        try:
            sync_config = config_manager.get_sync_config()
            
            # 设置同步类型
            sync_type_str = sync_config.get('sync_type', 'incremental')
            self.sync_type = SyncType(sync_type_str)
            
            # 如果配置了自动同步，则启动
            if sync_config.get('auto_sync', False):
                # 默认同步所有表单
                forms = ["销售订单", "销售出库单", "预测订单"]
                interval = sync_config.get('sync_interval', 60)
                
                self.configure_sync(forms, self.sync_type, interval)
                self.start()
                
                logger.info("已从配置文件恢复自动同步设置")
            
        except Exception as e:
            logger.error(f"加载配置并启动失败: {str(e)}")


# 全局自动同步调度器实例
auto_scheduler = AutoSyncScheduler()