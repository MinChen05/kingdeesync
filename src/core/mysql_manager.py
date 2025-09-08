"""MySQL数据库连接和操作模块（大写字段名版本）
负责与MySQL数据库进行数据交互
"""
import pymysql
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from src.config.config_manager import config_manager

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
            # 先关闭现有连接
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            
            # 处理字符集配置
            charset = self.config.get('charset', 'utf8mb4')
            if '_' in charset:  # 如果包含collation，只取字符集部分
                charset = charset.split('_')[0]
            
            logger.info(f"正在连接MySQL数据库: {self.config['host']}:{self.config.get('port', 3306)}")
            
            self.connection = pymysql.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database=self.config['database'],
                charset=charset,
                port=int(self.config.get('port', 3306)),
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=30,  # 连接超时
                read_timeout=30,     # 读取超时
                write_timeout=30     # 写入超时
            )
            self.cursor = self.connection.cursor()
            logger.info(f"成功连接到MySQL数据库: {self.config['database']}")
            return True
        except Exception as e:
            logger.error(f"连接MySQL数据库失败: {str(e)}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("已断开MySQL数据库连接")
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            if not self.connection or self.connection.open == False:
                return self.connect()
            
            # 执行简单查询测试连接
            self.cursor.execute("SELECT 1")
            result = self.cursor.fetchone()
            return result is not None and result.get('1') == 1
        except Exception as e:
            logger.error(f"测试MySQL数据库连接失败: {str(e)}")
            return False
    
    def log_sync_operation(self, sync_type: str, table_name: str, operation: str, 
                          record_count: int, status: str, message: str,
                          start_time: datetime, end_time: datetime) -> bool:
        """记录同步操作日志"""
        try:
            if not self.connection or not self.cursor:
                logger.warning("数据库连接丢失，尝试重新连接...")
                if not self.connect():
                    logger.error("重新连接数据库失败，无法记录同步日志")
                    return False
            
            # 计算持续时间（秒）
            duration_seconds = int((end_time - start_time).total_seconds())
            
            # 插入同步日志
            sql = """
            INSERT INTO sync_logs 
            (sync_type, table_name, operation, record_count, status, message, 
             start_time, end_time, duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            self.cursor.execute(sql, (
                sync_type, table_name, operation, record_count, status, message,
                start_time, end_time, duration_seconds
            ))
            
            logger.debug(f"已记录同步操作: {table_name} {operation} {status}")
            return True
            
        except Exception as e:
            logger.error(f"记录同步日志失败: {str(e)}")
            return False
    
    def get_last_modify_time(self, table_name: str) -> Optional[datetime]:
        """获取表中最后修改时间"""
        try:
            if not self.connection or not self.cursor:
                logger.warning("数据库连接丢失，尝试重新连接...")
                if not self.connect():
                    logger.error("重新连接数据库失败，无法获取最后修改时间")
                    return None
            
            # 根据表名获取最后修改时间字段
            modify_time_field = "FMODIFYDATE"
            
            # 查询最后修改时间
            sql = f"SELECT MAX({modify_time_field}) as last_modify_time FROM {table_name}"
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            
            if result and result.get('last_modify_time'):
                return result.get('last_modify_time')
            return None
            
        except Exception as e:
            logger.error(f"获取表 {table_name} 最后修改时间失败: {str(e)}")
            return None
    
    def create_tables(self, create_tables: bool = True) -> bool:
        """创建数据表（可选）"""
        if not create_tables:
            logger.info("跳过数据表创建，使用现有数据库表")
            return True
            
        if not self.connection:
            if not self.connect():
                return False
        
        try:
            # 创建同步日志表（始终创建，用于记录同步历史）
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
            
            self.cursor.execute(sync_log_sql)
            logger.info("同步日志表创建/检查完成")
            
            # 检查生产订单表是否存在
            self.cursor.execute("SHOW TABLES LIKE 'prd_mo'")
            if not self.cursor.fetchone():
                # 构建字段定义
                field_definitions = ["FID int(11) NOT NULL",
                "FENTRYID int(11) NULL",
                "FSEQ int(11) NULL",
                "FBILLNO varchar(80) NULL",
                "FBILLTYPE varchar(36) NULL",
                "FMATERIALNUMBER varchar(80) NULL",
                "FWORKSHOPNAME varchar(100) NULL",
                "FDATE datetime NULL",
                "FQTY decimal(18,6) NULL",
                "FSALEORDERID varchar(36) NULL",
                "FSRCBILLNO varchar(80) NULL",
                "FPLANSTARTDATE datetime NULL",
                "FPLANFINISHDATE datetime NULL",
                "FMODIFYDATE datetime NULL",
                "FCANCELSTATUS char(1) NULL",
                "FSTATUS char(1) NULL",
                "FSTOCKINQUAQTY decimal(23,2) NULL",
                "SYNC_TIME datetime NULL DEFAULT CURRENT_TIMESTAMP",
                "PRIMARY KEY (FID)"]
                
                # 构建创建表SQL
                field_defs_str = ',\n                '.join(field_definitions)
                create_sql = f"""CREATE TABLE prd_mo (
                    {field_defs_str}
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;"""
                
                self.cursor.execute(create_sql)
                logger.info("生产订单表创建完成")
            else:
                logger.info("生产订单表已存在，跳过创建")
            
            # 检查生产用料清单表是否存在
            self.cursor.execute("SHOW TABLES LIKE 'prd_ppbom'")
            if not self.cursor.fetchone():
                # 创建生产用料清单表
                ppbom_sql = """
                CREATE TABLE prd_ppbom (
                    FID int(11) NOT NULL,
                    FENTRYID int(11) NULL,
                    FMOID int(11) NULL,
                    FBILLNO varchar(30) NULL,
                    FMATERIALNUMBER varchar(30) NULL,
                    FMATERIALNAME varchar(20) NULL,
                    FPrdOrgId varchar(30) NULL,
                    FWorkshopName varchar(20) NULL,
                    FFatherQTY decimal(18,2) NULL,
                    FMODIFYDATE datetime NULL,
                    SYNC_TIME datetime NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (FID)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
                """
                self.cursor.execute(ppbom_sql)
                logger.info("生产用料清单表创建完成")
            else:
                logger.info("生产用料清单表已存在，跳过创建")
            
            return True
            
        except Exception as e:
            logger.error(f"创建数据表失败: {str(e)}")
            return False
    
    def _parse_date(self, date_str):
        """解析日期字符串"""
        if not date_str:
            return None
        try:
            # 尝试解析日期格式
            if isinstance(date_str, str):
                if 'T' in date_str:
                    # ISO格式: 2023-01-01T00:00:00
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                elif len(date_str) == 10:
                    # 日期格式: 2023-01-01
                    return datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    # 其他格式尝试
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            elif isinstance(date_str, datetime):
                return date_str
            else:
                return None
        except Exception as e:
            logger.warning(f"日期解析失败: {date_str}, 错误: {str(e)}")
            return None
    
    def _parse_datetime(self, dt_str):
        """解析日期时间字符串"""
        return self._parse_date(dt_str)
    
    def insert_production_orders(self, data: List[Dict]) -> int:
        """插入生产订单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO prd_mo (
            FID, FENTRYID, FSEQ, FBILLNO, FBILLTYPE, FMATERIALNUMBER, FWORKSHOPNAME, FDATE, FQTY, FSALEORDERID, FSRCBILLNO, FPLANSTARTDATE, FPLANFINISHDATE, FMODIFYDATE, FCANCELSTATUS, FSTATUS, FSTOCKINQUAQTY
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FENTRYID = VALUES(FENTRYID),
            FSEQ = VALUES(FSEQ),
            FBILLNO = VALUES(FBILLNO),
            FBILLTYPE = VALUES(FBILLTYPE),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FWORKSHOPNAME = VALUES(FWORKSHOPNAME),
            FDATE = VALUES(FDATE),
            FQTY = VALUES(FQTY),
            FSALEORDERID = VALUES(FSALEORDERID),
            FSRCBILLNO = VALUES(FSRCBILLNO),
            FPLANSTARTDATE = VALUES(FPLANSTARTDATE),
            FPLANFINISHDATE = VALUES(FPLANFINISHDATE),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            FCANCELSTATUS = VALUES(FCANCELSTATUS),
            FSTATUS = VALUES(FSTATUS),
            FSTOCKINQUAQTY = VALUES(FSTOCKINQUAQTY)
        """
        
        return self._batch_insert(sql, data, self._prepare_production_order_data)
    
    def _batch_insert(self, sql: str, data: List[Dict], prepare_func) -> int:
        """批量插入数据"""
        try:
            # 检查数据库连接
            if not self.connection or not self.cursor:
                logger.warning("数据库连接丢失，尝试重新连接...")
                if not self.connect():
                    logger.error("重新连接数据库失败")
                    return 0
            
            values = []
            for item in data:
                prepared_data = prepare_func(item)
                if prepared_data:
                    values.append(prepared_data)
            
            if values:
                self.cursor.executemany(sql, values)
                logger.info(f"成功插入 {len(values)} 条记录")
                return len(values)
            return 0
            
        except Exception as e:
            logger.error(f"批量插入数据失败: {str(e)}")
            # 如果是连接相关错误，尝试重新连接
            if "connection" in str(e).lower() or "packet" in str(e).lower():
                logger.warning("检测到连接错误，尝试重新连接...")
                self.connection = None
                self.cursor = None
            return 0
    
    def _convert_production_status(self, status_value):
        """转换生产订单状态值
        状态值对应关系：
        1 -> 计划
        2 -> 计划确认
        3 -> 下达
        4 -> 开工
        5 -> 完工
        6 -> 结案
        7 -> 结算
        """
        status_map = {
            # 数字转中文（数据库字段已改为varchar(4)）
            '1': '计划',
            '2': '计划确认',
            '3': '下达',
            '4': '开工',
            '5': '完工',
            '6': '结案',
            '7': '结算',
            # 处理可能的文本值（保持不变）
            '计划': '计划',
            '计划确认': '计划确认',
            '下达': '下达',
            '开工': '开工',
            '完工': '完工',
            '结案': '结案',
            '结算': '结算'
        }
        
        if status_value is None:
            return None
            
        # 转换为字符串并去除空格
        status_str = str(status_value).strip()
        
        # 返回映射值，如果没有对应的映射则返回原值
        return status_map.get(status_str, status_str)
    
    def _prepare_production_order_data(self, item) -> Optional[Tuple]:
        """准备生产订单数据
        按照数据库字段顺序: FID, FENTRYID, FSEQ, FBILLNO, FBILLTYPE, FMATERIALNUMBER, FWORKSHOPNAME, 
        FDATE, FQTY, FSALEORDERID, FSRCBILLNO, FPLANSTARTDATE, FPLANFINISHDATE, FMODIFYDATE, FCANCELSTATUS, FSTATUS, FSTOCKINQUAQTY
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FID'),                        # FID
                    item.get('FTreeEntity_FENTRYID'),       # FENTRYID
                    item.get('FTreeEntity_FSEQ'),           # FSEQ
                    item.get('FBILLNO'),                    # FBILLNO
                    item.get('FBILLTYPE.FNAME'),            # FBILLTYPE
                    item.get('FMATERIALID.FNUMBER'),        # FMATERIALNUMBER
                    item.get('FWorkShopID.FNAME'),          # FWORKSHOPNAME
                    self._parse_datetime(item.get('FDATE')),      # FDATE
                    item.get('FQTY'),                       # FQTY
                    item.get('FSALEORDERID'),               # FSALEORDERID
                    item.get('FSRCBILLNO'),                 # FSRCBILLNO
                    self._parse_datetime(item.get('FPLANSTARTDATE')),  # FPLANSTARTDATE
                    self._parse_datetime(item.get('FPLANFINISHDATE')), # FPLANFINISHDATE
                    self._parse_datetime(item.get('FMODIFYDATE')),     # FMODIFYDATE
                    item.get('FCANCELSTATUS'),              # FCANCELSTATUS
                    self._convert_production_status(item.get('FSTATUS')),  # FSTATUS
                    item.get('FSTOCKINQUAQTY')              # FSTOCKINQUAQTY
                )
            elif isinstance(item, list):
                # 列表格式数据
                if len(item) >= 15:  # 至少需要15个字段才能处理
                    return (
                        item[0],                            # FID
                        item[1],                            # FENTRYID
                        item[2],                            # FSEQ
                        item[3],                            # FBILLNO
                        item[4],                            # FBILLTYPE
                        item[5],                            # FMATERIALNUMBER
                        item[6],                            # FWORKSHOPNAME
                        self._parse_datetime(item[7]),      # FDATE
                        item[8],                            # FQTY
                        item[9],                            # FSALEORDERID
                        item[10],                           # FSRCBILLNO
                        self._parse_datetime(item[11]),     # FPLANSTARTDATE
                        self._parse_datetime(item[12]),     # FPLANFINISHDATE
                        self._parse_datetime(item[13]),     # FMODIFYDATE
                        item[14],                           # FCANCELSTATUS
                        self._convert_production_status(item[15] if len(item) > 15 else None),  # FSTATUS
                        item[16] if len(item) > 16 else None   # FSTOCKINQUAQTY
                    )
                else:
                    logger.warning(f"列表数据项不足: {len(item)}")
                    return None
            else:
                logger.warning(f"不支持的数据类型: {type(item)}")
                return None
        except Exception as e:
            logger.error(f"准备生产订单数据失败: {str(e)}")
            return None
            
    def _prepare_production_ppbom_data(self, item) -> Optional[Tuple]:
        """准备生产用料清单数据
        按照数据库字段顺序: FID, FENTRYID, FMOID, FBILLNO, FMATERIALNUMBER, FMATERIALNAME, 
        FPrdOrgId, FWorkshopName, FFatherQTY, FMODIFYDATE
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FID'),                        # FID
                    None,                                   # FENTRYID (不存在，设为NULL)
                    item.get('FMOID'),                      # FMOID
                    item.get('FBILLNO'),                    # FBILLNO
                    item.get('FMATERIALID.FNUMBER'),        # FMATERIALNUMBER
                    item.get('FMATERIALID.FNAME'),          # FMATERIALNAME
                    None,                                   # FPrdOrgId (不存在，设为NULL)
                    item.get('FWORKSHOPID.FNAME'),          # FWorkshopName
                    item.get('FQTY'),                       # FFatherQTY
                    self._parse_datetime(item.get('FMODIFYDATE'))  # FMODIFYDATE
                )
            elif isinstance(item, list) and len(item) >= 8:
                # 列表格式数据 - 根据API返回的实际字段顺序
                return (
                    item[0],                                # FID
                    None,                                   # FENTRYID (不存在，设为NULL)
                    item[1],                                # FMOID
                    item[2],                                # FBILLNO
                    item[3],                                # FMATERIALNUMBER (FMATERIALID.FNUMBER)
                    item[4],                                # FMATERIALNAME (FMATERIALID.FNAME)
                    None,                                   # FPrdOrgId (不存在，设为NULL)
                    item[5],                                # FWorkshopName (FWORKSHOPID.FNAME)
                    item[6],                                # FFatherQTY (FQTY)
                    self._parse_datetime(item[7])           # FMODIFYDATE
                )
            else:
                logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
                return None
        except Exception as e:
            logger.error(f"准备生产用料清单数据失败: {str(e)}")
            return None
            
    def insert_sales_orders(self, data: List[Dict]) -> int:
        """插入销售订单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO saleorder (
            FENTRYID, FSEQ, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME, 
            FSALEORONAME, FCUSTGROUP, FMATERIALNAME, FMATERIALNUMBER, FMATERIALTYPE, 
            FMATERIALSORT, FQTY, FCloseStatus, FDeliveryDate, FModifyDate
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FSEQ = VALUES(FSEQ),
            FBILLTYPENAME = VALUES(FBILLTYPENAME),
            FBILLNO = VALUES(FBILLNO),
            FDATE = VALUES(FDATE),
            FCUSTNAME = VALUES(FCUSTNAME),
            FSALEORONAME = VALUES(FSALEORONAME),
            FCUSTGROUP = VALUES(FCUSTGROUP),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FMATERIALTYPE = VALUES(FMATERIALTYPE),
            FMATERIALSORT = VALUES(FMATERIALSORT),
            FQTY = VALUES(FQTY),
            FCloseStatus = VALUES(FCloseStatus),
            FDeliveryDate = VALUES(FDeliveryDate),
            FModifyDate = VALUES(FModifyDate)
        """
        
        return self._batch_insert(sql, data, self._prepare_sales_order_data)
        
    def insert_sales_outstock(self, data: List[Dict]) -> int:
        """插入销售出库单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO sal_outstock (
            FENTRYID, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME, 
            FSALEORGNAME, FCUSTGROUP, FREALQTY, FMATERIALNAME, FMATERIALNUMBER, 
            FMATERIALTYPE, FMATERIALSORT, FMODIFYDATE
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FBILLTYPENAME = VALUES(FBILLTYPENAME),
            FBILLNO = VALUES(FBILLNO),
            FDATE = VALUES(FDATE),
            FCUSTNAME = VALUES(FCUSTNAME),
            FSALEORGNAME = VALUES(FSALEORGNAME),
            FCUSTGROUP = VALUES(FCUSTGROUP),
            FREALQTY = VALUES(FREALQTY),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FMATERIALTYPE = VALUES(FMATERIALTYPE),
            FMATERIALSORT = VALUES(FMATERIALSORT),
            FMODIFYDATE = VALUES(FMODIFYDATE)
        """
        
        return self._batch_insert(sql, data, self._prepare_sales_outstock_data)
        
    def insert_forecast_orders(self, data: List[Dict]) -> int:
        """插入预测订单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO pln_forecast (
            FENTRYID, FBILLNO, FFOREORGNAME, FCUSTNAME, FMATERIALNAME, 
            FMATERIALNUMBER, FQTY, FORA_BASE_FNAME, FORA_BASEPROPERTY_CA9, FORA_BASEPROPERTY_UKY, 
            FDATE, FMODIFYDATE
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FBILLNO = VALUES(FBILLNO),
            FFOREORGNAME = VALUES(FFOREORGNAME),
            FCUSTNAME = VALUES(FCUSTNAME),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FQTY = VALUES(FQTY),
            FORA_BASE_FNAME = VALUES(FORA_BASE_FNAME),
            FORA_BASEPROPERTY_CA9 = VALUES(FORA_BASEPROPERTY_CA9),
            FORA_BASEPROPERTY_UKY = VALUES(FORA_BASEPROPERTY_UKY),
            FDATE = VALUES(FDATE),
            FMODIFYDATE = VALUES(FMODIFYDATE)
        """
        
        return self._batch_insert(sql, data, self._prepare_forecast_order_data)
        
    def insert_production_ppbom(self, data: List[Dict]) -> int:
        """插入生产用料清单数据"""
        if not data:
            return 0
        
        sql = """
        INSERT INTO prd_ppbom (
            FID, FENTRYID, FMOID, FBILLNO, FMATERIALNUMBER, FMATERIALNAME, 
            FPrdOrgId, FWorkshopName, FFatherQTY, FMODIFYDATE
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FENTRYID = VALUES(FENTRYID),
            FMOID = VALUES(FMOID),
            FBILLNO = VALUES(FBILLNO),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FPrdOrgId = VALUES(FPrdOrgId),
            FWorkshopName = VALUES(FWorkshopName),
            FFatherQTY = VALUES(FFatherQTY),
            FMODIFYDATE = VALUES(FMODIFYDATE)
        """
        
        return self._batch_insert(sql, data, self._prepare_production_ppbom_data)
    
    def _prepare_sales_order_data(self, item) -> Optional[Tuple]:
        """准备销售订单数据
        按照数据库字段顺序: FENTRYID, FSEQ, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME, 
        FSALEORONAME, FCUSTGROUP, FMATERIALNAME, FMATERIALNUMBER, FMATERIALTYPE, 
        FMATERIALSORT, FQTY, FCloseStatus, FDeliveryDate, FModifyDate
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FSaleOrderEntry_FENTRYID'),   # FENTRYID
                    item.get('FSaleOrderEntry_FSEQ'),       # FSEQ
                    item.get('FBillTypeID.FName'),          # FBILLTYPENAME
                    item.get('FBillNo'),                    # FBILLNO
                    self._parse_date(item.get('FDate')),     # FDATE
                    item.get('FCustId.FName'),              # FCUSTNAME
                    item.get('FSaleOrgId.FName'),           # FSALEORONAME
                    item.get('FCustId.FGROUP'),             # FCUSTGROUP
                    item.get('FMaterialId.FName'),          # FMATERIALNAME
                    item.get('FMaterialId.FNumber'),        # FMATERIALNUMBER
                    item.get('FMaterialId.F_ora_Text_qtr'), # FMATERIALTYPE
                    item.get('FMaterialId.FBarcode'),       # FMATERIALSORT
                    item.get('FQTY'),                       # FQTY
                    item.get('FCloseStatus'),               # FCloseStatus
                    self._parse_date(item.get('FDeliveryDate')), # FDeliveryDate
                    self._parse_datetime(item.get('FModifyDate'))  # FModifyDate
                )
            elif isinstance(item, list) and len(item) >= 16:
                # 列表格式数据（金蝶API直接返回的数组格式）
                return (
                    item[0],                                # FENTRYID
                    item[1],                                # FSEQ
                    item[2],                                # FBILLTYPENAME
                    item[3],                                # FBILLNO
                    self._parse_date(str(item[4]) if item[4] else None),  # FDATE
                    item[5],                                # FCUSTNAME
                    item[6],                                # FSALEORONAME
                    item[7],                                # FCUSTGROUP
                    item[8],                                # FMATERIALNAME
                    item[9],                                # FMATERIALNUMBER
                    item[10],                               # FMATERIALTYPE
                    item[11],                               # FMATERIALSORT
                    item[12],                               # FQTY
                    item[13],                               # FCloseStatus
                    self._parse_date(str(item[14]) if item[14] else None),  # FDeliveryDate
                    self._parse_datetime(str(item[15]) if item[15] else None)  # FModifyDate
                )
            else:
                logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
                return None
        except Exception as e:
            logger.error(f"准备销售订单数据失败: {str(e)}, 数据: {item}")
            return None
            
    def _prepare_sales_outstock_data(self, item) -> Optional[Tuple]:
        """准备销售出库单数据
        按照数据库字段顺序: FENTRYID, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME, 
        FSALEORGNAME, FCUSTGROUP, FREALQTY, FMATERIALNAME, FMATERIALNUMBER, 
        FMATERIALTYPE, FMATERIALSORT, FMODIFYDATE
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FEntity_FENTRYID'),           # FENTRYID
                    item.get('FBillTypeID.FName'),          # FBILLTYPENAME
                    item.get('FBillNO'),                    # FBILLNO
                    self._parse_date(item.get('FDate')),     # FDATE
                    item.get('FCustomerID.FNAME'),          # FCUSTNAME
                    item.get('FSaleOrgId.FNAME'),           # FSALEORGNAME
                    item.get('FCustomerID.FGROUP'),         # FCUSTGROUP
                    item.get('FRealQty'),                   # FREALQTY
                    item.get('FMaterialID.FNAME'),          # FMATERIALNAME
                    item.get('FMaterialID.FNUMBER'),        # FMATERIALNUMBER
                    item.get('FMaterialID.F_ora_Text_qtr'), # FMATERIALTYPE
                    item.get('FMaterialID.FBarcode'),       # FMATERIALSORT
                    self._parse_datetime(item.get('FModifyDate'))  # FMODIFYDATE
                )
            elif isinstance(item, list) and len(item) >= 13:
                # 列表格式数据（金蝶API直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    item[0],                                # FENTRYID
                    item[1],                                # FBILLTYPENAME
                    item[2],                                # FBILLNO
                    self._parse_date(str(item[3]) if item[3] else None),  # FDATE
                    item[4],                                # FCUSTNAME
                    item[5],                                # FSALEORGNAME
                    item[6],                                # FCUSTGROUP
                    item[7],                                # FREALQTY
                    item[8],                                # FMATERIALNAME
                    item[9],                                # FMATERIALNUMBER
                    item[10],                               # FMATERIALTYPE
                    item[11],                               # FMATERIALSORT
                    self._parse_datetime(str(item[12]) if item[12] else None)  # FMODIFYDATE
                )
            else:
                logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
                return None
        except Exception as e:
            logger.error(f"准备销售出库单数据失败: {str(e)}, 数据: {item}")
            return None
            
    def _prepare_forecast_order_data(self, item) -> Optional[Tuple]:
        """准备预测订单数据
        按照数据库字段顺序: FENTRYID, FBILLNO, FFOREORGNAME, FCUSTNAME, FMATERIALNAME, 
        FMATERIALNUMBER, FQTY, FORA_BASE_FNAME, FORA_BASEPROPERTY_CA9, FORA_BASEPROPERTY_UKY, 
        FDATE, FMODIFYDATE
        """
        try:
            # 检查数据类型
            if isinstance(item, dict):
                # 字典格式数据
                return (
                    item.get('FEntity_FENTRYID'),            # FENTRYID
                    item.get('FBillNo'),                     # FBILLNO
                    item.get('FForeOrgId.FNAME'),            # FFORGNAME
                    item.get('FCustId.FNAME'),               # FCUSTNAME
                    item.get('FMaterialId.FNAME'),           # FMATERIALNAME
                    item.get('FMaterialId.FNUMBER'),         # FMATERIALNUMBER
                    item.get('FQty'),                        # FQTY
                    item.get('F_ora_Base.FNAME'),            # FORA_BASE_FNAME
                    item.get('F_ora_BaseProperty_ca9'),      # FORA_BASEPROPERTY_CA9
                    item.get('F_ora_BaseProperty_uky'),      # FORA_BASEPROPERTY_UKY
                    self._parse_datetime(item.get('F_ora_Date')),  # FDATE
                    self._parse_datetime(item.get('FModifyDate'))  # FMODIFYDATE
                )
            elif isinstance(item, list) and len(item) >= 12:
                # 列表格式数据（金蝶API直接返回的数组格式）
                # 根据 FieldKeys 的顺序映射到数据库字段
                return (
                    item[0],                                # FENTRYID
                    item[1],                                # FBILLNO
                    item[2],                                # FFORGNAME
                    item[3],                                # FCUSTNAME
                    item[4],                                # FMATERIALNAME
                    item[5],                                # FMATERIALNUMBER
                    item[6],                                # FQTY
                    item[7],                                # FORA_BASE_FNAME
                    item[8],                                # FORA_BASEPROPERTY_CA9
                    item[9],                                # FORA_BASEPROPERTY_UKY
                    self._parse_datetime(str(item[10]) if item[10] else None),  # FDATE
                    self._parse_datetime(str(item[11]) if item[11] else None)   # FMODIFYDATE
                )
            else:
                logger.warning(f"不支持的数据类型或列表数据项不足: {type(item)}")
                return None
        except Exception as e:
            logger.error(f"准备预测订单数据失败: {str(e)}, 数据: {item}")
            return None

# 全局MySQL管理器实例
mysql_manager = MySQLManager()