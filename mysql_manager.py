"""
MySQL数据库连接和操作模块
负责与MySQL数据库进行数据交互
"""
import pymysql
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from config_manager import config_manager

# 配置日志
logger = logging.getLogger(__name__)

class MySQLManager:
    """MySQL数据库管理器"""
    
    def __init__(self):
        self.config = config_manager.get_mysql_config()
        self.connection = None
        self.cursor = None
    
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.connection = pymysql.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=self.config['charset'],
                port=int(self.config.get('port', 3306)),
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            logger.info("MySQL数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"MySQL数据库连接失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
            logger.info("MySQL数据库连接已关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接时发生错误: {str(e)}")
    
    def create_tables(self) -> bool:
        """创建数据表"""
        if not self.connection:
            if not self.connect():
                return False
        
        try:
            # 创建销售订单表
            sales_order_sql = """
            CREATE TABLE IF NOT EXISTS sales_orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entry_id VARCHAR(100),
                seq_no INT,
                bill_type VARCHAR(100),
                bill_no VARCHAR(100),
                bill_date DATE,
                customer_name VARCHAR(200),
                sale_org_name VARCHAR(200),
                customer_group VARCHAR(200),
                material_name VARCHAR(200),
                material_number VARCHAR(100),
                material_text VARCHAR(200),
                material_barcode VARCHAR(100),
                qty DECIMAL(18,6),
                close_status VARCHAR(50),
                delivery_date DATE,
                modify_date DATETIME,
                sync_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_entry (entry_id, seq_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            
            # 创建销售出库单表
            sales_outstock_sql = """
            CREATE TABLE IF NOT EXISTS sales_outstock (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entry_id VARCHAR(100),
                bill_type VARCHAR(100),
                bill_no VARCHAR(100),
                bill_date DATE,
                customer_name VARCHAR(200),
                sale_org_name VARCHAR(200),
                customer_group VARCHAR(200),
                real_qty DECIMAL(18,6),
                material_name VARCHAR(200),
                material_number VARCHAR(100),
                material_text VARCHAR(200),
                material_barcode VARCHAR(100),
                modify_date DATETIME,
                sync_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_entry (entry_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            
            # 创建预测订单表
            forecast_order_sql = """
            CREATE TABLE IF NOT EXISTS forecast_orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entry_id VARCHAR(100),
                bill_no VARCHAR(100),
                forecast_org_name VARCHAR(200),
                customer_name VARCHAR(200),
                material_name VARCHAR(200),
                material_number VARCHAR(100),
                qty DECIMAL(18,6),
                base_name VARCHAR(200),
                base_property_ca9 VARCHAR(200),
                base_property_uky VARCHAR(200),
                forecast_date DATE,
                modify_date DATETIME,
                sync_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_entry (entry_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            
            # 创建同步日志表
            sync_log_sql = """
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sync_type VARCHAR(50),
                table_name VARCHAR(100),
                operation VARCHAR(50),
                record_count INT,
                status VARCHAR(50),
                message TEXT,
                start_time DATETIME,
                end_time DATETIME,
                duration_seconds INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            
            # 创建生产订单表
            production_order_sql = """
            CREATE TABLE IF NOT EXISTS production_orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fid VARCHAR(100) UNIQUE,
                bill_no VARCHAR(100),
                bill_type_name VARCHAR(100),
                bill_date DATE,
                modify_date DATETIME,
                cancel_status VARCHAR(50),
                sync_time DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """

            tables = [
                ("sales_orders", sales_order_sql),
                ("sales_outstock", sales_outstock_sql),
                ("forecast_orders", forecast_order_sql),
                ("sync_logs", sync_log_sql),
                ("production_orders", production_order_sql)
            ]
            
            for table_name, sql in tables:
                self.cursor.execute(sql)
                logger.info(f"数据表 {table_name} 创建/检查完成")
            
            return True
            
        except Exception as e:
            logger.error(f"创建数据表失败: {str(e)}")
            return False
    
    def insert_sales_orders(self, data: List[Dict]) -> int:
        """插入销售订单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO sales_orders (
            entry_id, seq_no, bill_type, bill_no, bill_date, customer_name,
            sale_org_name, customer_group, material_name, material_number,
            material_text, material_barcode, qty, close_status, delivery_date, modify_date
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            bill_type=VALUES(bill_type), bill_no=VALUES(bill_no), bill_date=VALUES(bill_date),
            customer_name=VALUES(customer_name), sale_org_name=VALUES(sale_org_name),
            customer_group=VALUES(customer_group), material_name=VALUES(material_name),
            material_number=VALUES(material_number), material_text=VALUES(material_text),
            material_barcode=VALUES(material_barcode), qty=VALUES(qty),
            close_status=VALUES(close_status), delivery_date=VALUES(delivery_date),
            modify_date=VALUES(modify_date), sync_time=CURRENT_TIMESTAMP
        """
        
        return self._batch_insert(sql, data, self._prepare_sales_order_data)
    
    def insert_sales_outstock(self, data: List[Dict]) -> int:
        """插入销售出库单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO sales_outstock (
            entry_id, bill_type, bill_no, bill_date, customer_name,
            sale_org_name, customer_group, real_qty, material_name,
            material_number, material_text, material_barcode, modify_date
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            bill_type=VALUES(bill_type), bill_no=VALUES(bill_no), bill_date=VALUES(bill_date),
            customer_name=VALUES(customer_name), sale_org_name=VALUES(sale_org_name),
            customer_group=VALUES(customer_group), real_qty=VALUES(real_qty),
            material_name=VALUES(material_name), material_number=VALUES(material_number),
            material_text=VALUES(material_text), material_barcode=VALUES(material_barcode),
            modify_date=VALUES(modify_date), sync_time=CURRENT_TIMESTAMP
        """
        
        return self._batch_insert(sql, data, self._prepare_sales_outstock_data)

    def insert_production_orders(self, data: List[Dict]) -> int:
        """插入生产订单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO production_orders (
            fid, bill_no, bill_type_name, bill_date, modify_date, cancel_status
        ) VALUES (
            %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            bill_no=VALUES(bill_no), bill_type_name=VALUES(bill_type_name),
            bill_date=VALUES(bill_date), modify_date=VALUES(modify_date),
            cancel_status=VALUES(cancel_status), sync_time=CURRENT_TIMESTAMP
        """
        
        return self._batch_insert(sql, data, self._prepare_production_order_data)

    def insert_forecast_orders(self, data: List[Dict]) -> int:
        """插入预测订单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO forecast_orders (
            entry_id, bill_no, forecast_org_name, customer_name, material_name,
            material_number, qty, base_name, base_property_ca9, base_property_uky,
            forecast_date, modify_date
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            bill_no=VALUES(bill_no), forecast_org_name=VALUES(forecast_org_name),
            customer_name=VALUES(customer_name), material_name=VALUES(material_name),
            material_number=VALUES(material_number), qty=VALUES(qty),
            base_name=VALUES(base_name), base_property_ca9=VALUES(base_property_ca9),
            base_property_uky=VALUES(base_property_uky), forecast_date=VALUES(forecast_date),
            modify_date=VALUES(modify_date), sync_time=CURRENT_TIMESTAMP
        """
        
        return self._batch_insert(sql, data, self._prepare_forecast_order_data)
    
    def _batch_insert(self, sql: str, data: List[Dict], prepare_func) -> int:
        """批量插入数据"""
        try:
            values = []
            for item in data:
                prepared_data = prepare_func(item)
                if prepared_data:
                    values.append(prepared_data)
            
            if values:
                self.cursor.executemany(sql, values)
                return len(values)
            return 0
            
        except Exception as e:
            logger.error(f"批量插入数据失败: {str(e)}")
            return 0
    
    def _prepare_sales_order_data(self, item) -> Optional[Tuple]:
        """准备销售订单数据"""
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FSaleOrderEntry_FENTRYID'),
                    item.get('FSaleOrderEntry_FSEQ'),
                    item.get('FBillTypeID_FName'),
                    item.get('FBillNo'),
                    self._parse_date(item.get('FDate')),
                    item.get('FCustId_FName'),
                    item.get('FSaleOrgId_FName'),
                    item.get('FCustId_FGROUP'),
                    item.get('FMaterialId_FName'),
                    item.get('FMaterialId_FNumber'),
                    item.get('FMaterialId_F_ora_Text_qtr'),
                    item.get('FMaterialId_FBarcode'),
                    item.get('FQTY'),
                    item.get('FCloseStatus'),
                    self._parse_date(item.get('FDeliveryDate')),
                    self._parse_datetime(item.get('FModifyDate'))
                )
            elif isinstance(item, list) and len(item) >= 16:
                # 列表格式数据（金蝶API直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    item[0],  # FSaleOrderEntry_FENTRYID
                    item[1],  # FSaleOrderEntry_FSEQ
                    item[2],  # FBillTypeID.FName
                    item[3],  # FBillNo
                    self._parse_date(str(item[4]) if item[4] else None),  # FDate
                    item[5],  # FCustId.FName
                    item[6],  # FSaleOrgId.FName
                    item[7],  # FCustId.FGROUP
                    item[8],  # FMaterialId.FName
                    item[9],  # FMaterialId.FNumber
                    item[10], # FMaterialId.F_ora_Text_qtr
                    item[11], # FMaterialId.FBarcode
                    item[12], # FQTY
                    item[13], # FCloseStatus
                    self._parse_date(str(item[14]) if item[14] else None),  # FDeliveryDate
                    self._parse_datetime(str(item[15]) if item[15] else None)  # FModifyDate
                )
            else:
                logger.error(f"不支持的数据类型，期望字典或列表，实际: {type(item)}, 内容: {item}")
                return None
        except Exception as e:
            logger.error(f"准备销售订单数据失败: {str(e)}, 数据: {item}")
            return None
    
    def _prepare_sales_outstock_data(self, item) -> Optional[Tuple]:
        """准备销售出库单数据"""
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FEntity_FENTRYID'),
                    item.get('FBillTypeID_FName'),
                    item.get('FBillNO'),
                    self._parse_date(item.get('FDate')),
                    item.get('FCustomerID_FNAME'),
                    item.get('FSaleOrgId_FNAME'),
                    item.get('FCustomerID_FGROUP'),
                    item.get('FRealQty'),
                    item.get('FMaterialID_FNAME'),
                    item.get('FMaterialID_FNUMBER'),
                    item.get('FMaterialID_F_ora_Text_qtr'),
                    item.get('FMaterialID_FBarcode'),
                    self._parse_datetime(item.get('FModifyDate'))
                )
            elif isinstance(item, list) and len(item) >= 13:
                # 列表格式数据（金蝶API直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    item[0],  # FEntity_FENTRYID
                    item[1],  # FBillTypeID.FName
                    item[2],  # FBillNO
                    self._parse_date(str(item[3]) if item[3] else None),  # FDate
                    item[4],  # FCustomerID.FNAME
                    item[5],  # FSaleOrgId.FNAME
                    item[6],  # FCustomerID.FGROUP
                    item[7],  # FRealQty
                    item[8],  # FMaterialID.FNAME
                    item[9],  # FMaterialID.FNUMBER
                    item[10], # FMaterialID.F_ora_Text_qtr
                    item[11], # FMaterialID.FBarcode
                    self._parse_datetime(str(item[12]) if item[12] else None)  # FModifyDate
                )
            else:
                logger.error(f"不支持的数据类型，期望字典或列表，实际: {type(item)}, 内容: {item}")
                return None
        except Exception as e:
            logger.error(f"准备销售出库单数据失败: {str(e)}, 数据: {item}")
            return None
    
    def _prepare_forecast_order_data(self, item) -> Optional[Tuple]:
        """准备预测订单数据"""
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FEntity_FENTRYID'),
                    item.get('FBillNo'),
                    item.get('FForeOrgId_FNAME'),
                    item.get('FCustId_FNAME'),
                    item.get('FMaterialId_FNAME'),
                    item.get('FMaterialId_FNUMBER'),
                    item.get('FQty'),
                    item.get('F_ora_Base_FNAME'),
                    item.get('F_ora_BaseProperty_ca9'),
                    item.get('F_ora_BaseProperty_uky'),
                    self._parse_date(item.get('F_ora_Date')),
                    self._parse_datetime(item.get('FModifyDate'))
                )
            elif isinstance(item, list) and len(item) >= 12:
                # 列表格式数据（金蝶API直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    item[0],  # FEntity_FENTRYID
                    item[1],  # FBillNo
                    item[2],  # FForeOrgId.FNAME
                    item[3],  # FCustId.FNAME
                    item[4],  # FMaterialId.FNAME
                    item[5],  # FMaterialId.FNUMBER
                    item[6],  # FQty
                    item[7],  # F_ora_Base.FNAME
                    item[8],  # F_ora_BaseProperty_ca9
                    item[9],  # F_ora_BaseProperty_uky
                    self._parse_date(str(item[10]) if item[10] else None),  # F_ora_Date
                    self._parse_datetime(str(item[11]) if item[11] else None)  # FModifyDate
                )
            else:
                logger.error(f"不支持的数据类型，期望字典或列表，实际: {type(item)}, 内容: {item}")
                return None
        except Exception as e:
            logger.error(f"准备预测订单数据失败: {str(e)}, 数据: {item}")
            return None
    
    def _parse_date(self, date_str) -> Optional[str]:
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            # 先转换为字符串处理
            date_str = str(date_str).strip()
            
            # 尝试多种日期格式
            formats = [
                '%Y-%m-%dT%H:%M:%S',      # ISO 8601 格式
                '%Y-%m-%d %H:%M:%S',      # 标准日期时间格式
                '%Y-%m-%d',               # 简单日期格式
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d'
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # 如果都失败，返回原始值（可能是已经是正确格式）
            if len(date_str) == 10 and '-' in date_str:
                return date_str
            
            return None
        except Exception:
            return None
    
    def _parse_datetime(self, datetime_str) -> Optional[str]:
        """解析日期时间字符串"""
        if not datetime_str:
            return None
        try:
            # 先转换为字符串处理
            datetime_str = str(datetime_str).strip()
            
            # 尝试多种日期时间格式
            formats = [
                '%Y-%m-%dT%H:%M:%S.%f',   # ISO 8601 带毫秒
                '%Y-%m-%dT%H:%M:%S',      # ISO 8601 格式
                '%Y-%m-%d %H:%M:%S.%f',   # 标准格式带毫秒
                '%Y-%m-%d %H:%M:%S',      # 标准日期时间格式
                '%Y-%m-%d',               # 只有日期
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d'
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue
            
            # 如果都失败，返回原始值（可能是已经是正确格式）
            if len(datetime_str) >= 10:
                return datetime_str
            
            return None
        except Exception:
            return None
    
    def log_sync_operation(self, sync_type: str, table_name: str, operation: str, 
                          record_count: int, status: str, message: str, 
                          start_time: datetime, end_time: datetime) -> bool:
        """记录同步操作日志"""
        try:
            duration = int((end_time - start_time).total_seconds())
            sql = """
            INSERT INTO sync_logs (sync_type, table_name, operation, record_count, 
                                 status, message, start_time, end_time, duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self.cursor.execute(sql, (
                sync_type, table_name, operation, record_count, status, message,
                start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration
            ))
            return True
        except Exception as e:
            logger.error(f"记录同步日志失败: {str(e)}")
            return False
    
    def get_last_modify_time(self, table_name: str) -> Optional[datetime]:
        """获取表中最后修改时间"""
        try:
            sql = f"SELECT MAX(modify_date) as last_modify FROM {table_name}"
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            if result and result['last_modify']:
                return result['last_modify']
            return None
        except Exception as e:
            logger.error(f"获取最后修改时间失败: {str(e)}")
            return None
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            if not self.connection:
                return self.connect()
            
            self.cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            return False


# 全局MySQL管理器实例
mysql_manager = MySQLManager()