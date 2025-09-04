"""
数据同步逻辑模块
实现增量、全量、完全同步功能
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum

from src.core.kingdee_api import kingdee_client
from src.core.mysql_manager import mysql_manager
from src.config.config_manager import config_manager

# 配置日志
logger = logging.getLogger(__name__)

class SyncType(Enum):
    """同步类型枚举"""
    INCREMENTAL = "incremental"  # 增量同步
    FULL = "full"              # 全量同步
    COMPLETE = "complete"       # 完全同步

class SyncStatus(Enum):
    """同步状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

class DataSyncManager:
    """数据同步管理器"""
    
    def __init__(self):
        self.table_mapping = {
            "销售订单": "saleorder",
            "销售出库单": "sal_outstock", 
            "预测订单": "pln_forecast",
            "生产订单": "prd_mo"
        }
        self.sync_callbacks = []  # 同步进度回调
    
    def add_sync_callback(self, callback):
        """添加同步进度回调函数"""
        self.sync_callbacks.append(callback)
    
    def _notify_progress(self, message: str, progress: int = 0):
        """通知同步进度"""
        for callback in self.sync_callbacks:
            try:
                callback(message, progress)
            except Exception as e:
                logger.error(f"回调函数执行失败: {str(e)}")
    
    def sync_data(self, form_names: List[str], sync_type: SyncType = SyncType.INCREMENTAL) -> Dict[str, Any]:
        """同步数据主方法"""
        start_time = datetime.now()
        self._notify_progress("开始数据同步...", 0)
        
        # 检查连接
        if not self._check_connections():
            return self._create_sync_result(SyncStatus.FAILED, "连接检查失败", start_time)
        
        # 初始化数据库表
        if not mysql_manager.create_tables():
            return self._create_sync_result(SyncStatus.FAILED, "数据库表初始化失败", start_time)
        
        self._notify_progress("连接检查完成，开始同步数据...", 10)
        
        results = {}
        total_records = 0
        failed_tables = []
        
        try:
            for i, form_name in enumerate(form_names):
                self._notify_progress(f"正在同步 {form_name}...", 20 + (i * 60 // len(form_names)))
                
                result = self._sync_single_form(form_name, sync_type)
                results[form_name] = result
                
                if result['status'] == SyncStatus.SUCCESS.value:
                    total_records += result['record_count']
                else:
                    failed_tables.append(form_name)
        
        except Exception as e:
            logger.error(f"数据同步过程发生错误: {str(e)}")
            return self._create_sync_result(SyncStatus.FAILED, f"同步过程发生错误: {str(e)}", start_time)
        
        end_time = datetime.now()
        
        # 更新最后同步时间
        config_manager.update_config('SYNC', 'last_sync_time', end_time.strftime('%Y-%m-%d %H:%M:%S'))
        
        # 确定整体同步状态
        if not failed_tables:
            status = SyncStatus.SUCCESS
            message = f"所有表同步成功，共同步 {total_records} 条记录"
            self._notify_progress("数据同步完成", 100)
        elif len(failed_tables) == len(form_names):
            status = SyncStatus.FAILED
            message = "所有表同步失败"
            self._notify_progress("数据同步失败", 100)
        else:
            status = SyncStatus.PARTIAL
            message = f"部分表同步成功，失败的表: {', '.join(failed_tables)}"
            self._notify_progress("数据同步部分完成", 100)
        
        return {
            'status': status.value,
            'message': message,
            'total_records': total_records,
            'start_time': start_time,
            'end_time': end_time,
            'duration': (end_time - start_time).total_seconds(),
            'details': results
        }
    
    def _sync_single_form(self, form_name: str, sync_type: SyncType) -> Dict[str, Any]:
        """同步单个表单"""
        start_time = datetime.now()
        table_name = self.table_mapping.get(form_name)
        
        if not table_name:
            logger.error(f"未找到表单 {form_name} 的映射表")
            return {
                'status': SyncStatus.FAILED.value,
                'message': f"未找到表单映射",
                'record_count': 0
            }
        
        try:
            # 构建查询条件
            self._notify_progress(f"[{form_name}] 正在构建查询条件...")
            filter_string = self._build_filter_string(form_name, sync_type, table_name)
            self._notify_progress(f"[{form_name}] 查询条件构建完成: {filter_string if filter_string else '无'}")
            
            # 查询金蝶数据
            self._notify_progress(f"[{form_name}] 正在查询金蝶数据...")
            logger.info(f"查询金蝶 {form_name} 数据...")
            data = self._query_kingdee_data(form_name, filter_string)
            
            if data is None:
                self._notify_progress(f"[{form_name}] 查询金蝶数据失败", 100)
                return {
                    'status': SyncStatus.FAILED.value,
                    'message': "查询金蝶数据失败",
                    'record_count': 0
                }
            
            self._notify_progress(f"[{form_name}] 查询到 {len(data)} 条数据，准备插入数据库...")
            
            # 插入数据库
            logger.info(f"插入 {len(data)} 条数据到数据库...")
            inserted_count = self._insert_database_data(form_name, data)
            self._notify_progress(f"[{form_name}] 成功插入 {inserted_count} 条数据到数据库")
            
            end_time = datetime.now()
            
            # 记录同步日志
            mysql_manager.log_sync_operation(
                sync_type.value, table_name, "sync", inserted_count,
                SyncStatus.SUCCESS.value, f"成功同步 {inserted_count} 条记录",
                start_time, end_time
            )
            
            return {
                'status': SyncStatus.SUCCESS.value,
                'message': f"成功同步 {inserted_count} 条记录",
                'record_count': inserted_count
            }
            
        except Exception as e:
            end_time = datetime.now()
            error_msg = f"同步失败: {str(e)}"
            logger.error(f"{form_name} {error_msg}")
            self._notify_progress(f"[{form_name}] {error_msg}", 100)
            
            # 记录错误日志
            mysql_manager.log_sync_operation(
                sync_type.value, table_name, "sync", 0,
                SyncStatus.FAILED.value, error_msg,
                start_time, end_time
            )
            
            return {
                'status': SyncStatus.FAILED.value,
                'message': error_msg,
                'record_count': 0
            }
    
    def _build_filter_string(self, form_name: str, sync_type: SyncType, table_name: str) -> Optional[str]:
        """构建查询过滤条件"""
        base_queries = config_manager.get_form_queries()
        base_filter = base_queries.get(form_name, {}).get('FilterString', '')
        
        if sync_type == SyncType.INCREMENTAL:
            # 增量同步：只查询修改时间大于上次同步时间的数据
            last_modify_time = mysql_manager.get_last_modify_time(table_name)
            if last_modify_time:
                # 添加时间过滤条件
                time_filter = f" and FModifyDate > '{last_modify_time.strftime('%Y-%m-%d %H:%M:%S')}'"
                return base_filter + time_filter
            else:
                # 如果没有历史数据，执行全量同步
                return base_filter
        
        elif sync_type == SyncType.FULL:
            # 全量同步：查询所有数据
            return base_filter
        
        elif sync_type == SyncType.COMPLETE:
            # 完全同步：先清空表，然后查询所有数据
            try:
                mysql_manager.cursor.execute(f"TRUNCATE TABLE {table_name}")
                logger.info(f"已清空表 {table_name}")
            except Exception as e:
                logger.error(f"清空表 {table_name} 失败: {str(e)}")
            return base_filter
        
        return base_filter
    
    def _query_kingdee_data(self, form_name: str, filter_string: str = None) -> Optional[List[Dict]]:
        """查询金蝶数据"""
        try:
            form_queries = config_manager.get_form_queries()
            query_params = form_queries.get(form_name, {}).copy()
            
            if filter_string:
                query_params['FilterString'] = filter_string
            
            return kingdee_client.query_data(form_name, query_params)
        
        except Exception as e:
            logger.error(f"查询金蝶 {form_name} 数据失败: {str(e)}")
            return None
    
    def _insert_database_data(self, form_name: str, data: List[Dict]) -> int:
        """插入数据到数据库"""
        if form_name == "销售订单":
            return mysql_manager.insert_sales_orders(data)
        elif form_name == "销售出库单":
            return mysql_manager.insert_sales_outstock(data)
        elif form_name == "预测订单":
            return mysql_manager.insert_forecast_orders(data)
        elif form_name == "生产订单":
            return mysql_manager.insert_production_orders(data)
        else:
            logger.error(f"未知的表单类型: {form_name}")
            return 0
    
    def _check_connections(self) -> bool:
        """检查金蝶和数据库连接"""
        # 检查金蝶连接
        if not kingdee_client.test_connection():
            logger.error("金蝶API连接失败")
            return False
        
        # 检查数据库连接
        if not mysql_manager.test_connection():
            logger.error("MySQL数据库连接失败")
            return False
        
        return True
    
    def _create_sync_result(self, status: SyncStatus, message: str, start_time: datetime) -> Dict[str, Any]:
        """创建同步结果"""
        end_time = datetime.now()
        return {
            'status': status.value,
            'message': message,
            'total_records': 0,
            'start_time': start_time,
            'end_time': end_time,
            'duration': (end_time - start_time).total_seconds(),
            'details': {}
        }
    
    def get_sync_history(self, limit: int = 50) -> List[Dict]:
        """获取同步历史记录"""
        try:
            sql = """
            SELECT sync_type, table_name, operation, record_count, status, message,
                   start_time, end_time, duration_seconds
            FROM sync_logs 
            ORDER BY start_time DESC 
            LIMIT %s
            """
            mysql_manager.cursor.execute(sql, (limit,))
            return mysql_manager.cursor.fetchall()
        except Exception as e:
            logger.error(f"获取同步历史失败: {str(e)}")
            return []
    
    def validate_data_integrity(self, form_names: List[str]) -> Dict[str, Any]:
        """验证数据完整性（用于完全同步后的验证）"""
        results = {}
        
        for form_name in form_names:
            try:
                # 查询金蝶数据总数
                kingdee_data = self._query_kingdee_data(form_name)
                kingdee_count = len(kingdee_data) if kingdee_data else 0
                
                # 查询数据库数据总数
                table_name = self.table_mapping.get(form_name)
                if table_name:
                    mysql_manager.cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                    db_result = mysql_manager.cursor.fetchone()
                    db_count = db_result['count'] if db_result else 0
                else:
                    db_count = 0
                
                results[form_name] = {
                    'kingdee_count': kingdee_count,
                    'database_count': db_count,
                    'match': kingdee_count == db_count,
                    'difference': abs(kingdee_count - db_count)
                }
                
            except Exception as e:
                logger.error(f"验证 {form_name} 数据完整性失败: {str(e)}")
                results[form_name] = {
                    'error': str(e)
                }
        
        return results


# 全局数据同步管理器实例
sync_manager = DataSyncManager()