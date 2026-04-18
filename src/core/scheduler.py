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
        self._last_exec_time = None  # 上次执行时间
        
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
        # 直接输出消息，不带进度前缀，保持与数据同步页一致
        logger.info(message)
    
    def configure_sync(self, forms: List[str], sync_type: SyncType = SyncType.INCREMENTAL, 
                      interval_minutes: int = 60):
        """配置同步参数"""
        # 处理特殊表单值 "同步所有表单"
        if forms and len(forms) == 1 and forms[0] == "同步所有表单":
            # 如果是"同步所有表单"，我们传递 None 给 sync_manager，它会处理为所有表单
            # 但在这里我们需要记录实际要同步的表单吗？
            # sync_manager.sync_data 接受 None 为所有表单。
            # 但 self.sync_forms 如果是 None，_execute_sync 里的日志可能需要调整。
            # 或者我们在这里将其展开为所有表单？
            # 更好的是，如果 forms 是 None 或空列表，sync_manager 默认同步所有。
            # 但这里 forms 是 ["同步所有表单"]，这是 UI 传来的显示值。
            # 我们将其置为 None，表示所有。
            self.sync_forms = None 
        else:
            self.sync_forms = forms
            
        self.sync_type = sync_type
        
        # 清除现有的定时任务
        schedule.clear()
        
        # 设置新的定时任务
        schedule.every(interval_minutes).minutes.do(self._execute_sync)
        
        # 更新配置
        # 注意：保存配置时，如果 forms 是 None，我们可能需要保存一个特殊标记或空列表
        # 这里为了简单，如果 self.sync_forms 是 None，我们不更新 default_forms 或者保存为 'all'？
        # config_manager 的 default_forms 通常是一个列表。
        # 如果是 None，我们就不更新 default_forms 里的具体表单名，或者保存为空？
        # 让我们看看 start_sync 是怎么保存的。
        # start_sync 保存的是选中的表单。
        # 这里 configure_sync 主要是运行时配置。
        
        config_manager.update_config('SYNC', 'sync_interval', str(interval_minutes))
        config_manager.update_config('SYNC', 'sync_type', sync_type.value)
        
        forms_log = "同步所有表单" if not self.sync_forms else str(self.sync_forms)
        logger.info(f"已配置定时同步: 表单={forms_log}, 类型={sync_type.value}, 间隔={interval_minutes}分钟")
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.status == SchedulerStatus.RUNNING

    def start(self, interval_minutes: Optional[int] = None):
        """启动定时同步"""
        if self.status == SchedulerStatus.RUNNING:
            logger.warning("定时同步已在运行中")
            return

        # 兼容界面层直接传入 interval_minutes 启动的场景：
        # 1. 传入了新的间隔时，先重建调度任务
        # 2. 当前还没有任何 schedule job 时，也从现有配置补齐一次
        if interval_minutes is not None or not schedule.jobs:
            sync_config = config_manager.get_sync_config()

            forms = self.sync_forms
            if forms == []:
                forms = sync_config.get('default_forms', [])
                if not forms:
                    forms = None

            sync_type = self.sync_type
            try:
                sync_type = SyncType(sync_config.get('sync_type', sync_type.value))
            except Exception:
                pass

            if interval_minutes is None:
                interval_minutes = sync_config.get('sync_interval', 60)

            self.configure_sync(forms, sync_type, interval_minutes)
        
        # if not self.sync_forms:
        #    logger.error("未配置同步表单，无法启动定时同步")
        #    return
        # 改为: 如果 sync_forms 是 None，表示同步所有，是合法的。
        # 只有当它是空列表时才可能是有问题，但空列表在 sync_manager 中可能也意味着默认？
        # sync_manager.sync_data 文档说 form_names: List[str]。如果为空列表，可能什么都不做？
        # 让我们假设 None 是所有，空列表是不做。
        # 但我们刚才把 "同步所有表单" 设为了 None。
        
        if self.sync_forms == []:
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
        
        # 启动时立即执行一次同步
        logger.info("检测到自动同步已启用，立即执行首次同步...")
        self._execute_sync()
        
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
        
        # 构建头部日志
        forms_text = "同步所有表单"
        if self.sync_forms:
            forms_text = f"同步 {len(self.sync_forms)} 个表单: {', '.join(self.sync_forms)}"
            
        mode_text = "增量同步 (推荐)"
        if self.sync_type == SyncType.FULL:
            mode_text = "全量同步"
        elif self.sync_type == SyncType.COMPLETE:
            mode_text = "完全重置"

        self._last_exec_time = datetime.now()
        logger.info("🚀 开始同步任务")
        logger.info(f"📋 表单: {forms_text}")
        logger.info(f"⚙️ 模式: {mode_text}")
        logger.info("-" * 40)
        
        try:
            # 执行同步
            result = sync_manager.sync_data(self.sync_forms, self.sync_type)
            
            # 通知同步完成
            self._notify_sync_complete(result)
            
            # 记录同步结果和统计
            logger.info("-" * 40)
            if result['status'] == 'success':
                logger.info("✅ 同步任务成功完成")
            elif result['status'] == 'partial':
                 logger.info("⚠️ 同步任务部分完成")
            else:
                logger.info("❌ 同步任务失败")
                
            logger.info("📊 任务统计:")
            if 'details' in result:
                # 先计算总数
                total_inserted = 0
                total_updated = 0
                for table, res in result['details'].items():
                    total_inserted += res.get('inserted', 0)
                    total_updated += res.get('updated', 0)
                
                # 输出汇总
                logger.info(f"• 总计: 新增 {total_inserted}, 更新 {total_updated}")
                
                # 按表名排序输出详情
                for table in sorted(result['details'].keys()):
                    res = result['details'][table]
                    inserted = res.get('inserted', 0)
                    updated = res.get('updated', 0)
                    logger.info(f"   • {table}: 新增 {inserted}, 更新 {updated}")
                
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
        if self.sync_forms == []:
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
    
    def get_last_exec_time(self) -> Optional[datetime]:
        """获取上次执行时间"""
        return self._last_exec_time

    def get_next_exec_time(self) -> Optional[datetime]:
        """获取下次执行时间"""
        return self.get_next_sync_time()

    def get_status_info(self) -> dict:
        """获取状态信息"""
        next_sync = self.get_next_sync_time()
        
        return {
            'status': self.status.value,
            'is_running': self.status == SchedulerStatus.RUNNING,
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
                forms = sync_config.get('default_forms', [])
                if not forms:
                    forms = None
                interval = sync_config.get('sync_interval', 60)
                
                self.configure_sync(forms, self.sync_type, interval)
                self.start()
                
                logger.info("已从配置文件恢复自动同步设置")
            
        except Exception as e:
            logger.error(f"加载配置并启动失败: {str(e)}")


# 全局自动同步调度器实例
auto_scheduler = AutoSyncScheduler()
