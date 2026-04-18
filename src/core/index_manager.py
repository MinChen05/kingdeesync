"""
数据库索引管理模块
自动创建和维护数据库索引
"""

import logging
from typing import List, Tuple, Optional
from src.core.mysql_manager import mysql_manager

logger = logging.getLogger(__name__)


class IndexManager:
    """数据库索引管理器"""

    # SQL Server 索引定义
    SQLSERVER_INDEXES = [
        # sync_logs 表索引
        ("sync_logs", "IX_sync_logs_start_time", "start_time"),
        ("sync_logs", "IX_sync_logs_table_name", "table_name"),
        ("sync_logs", "IX_sync_logs_status", "status"),
        ("sync_logs", "IX_sync_logs_time_status", "start_time, status"),
        ("sync_logs", "IX_sync_logs_sync_type", "sync_type"),
        # 业务表索引 - 增量同步字段
        ("saleorder", "IX_saleorder_modify_date", "FModifyDate"),
        ("saleorder", "IX_saleorder_billno", "FBILLNO"),
        ("saleorder", "IX_saleorder_cust", "FCUSTID"),
        ("sal_outstock", "IX_sal_outstock_modify_date", "FModifyDate"),
        ("sal_outstock", "IX_sal_outstock_billno", "FBILLNO"),
        ("sal_returnstock", "IX_sal_returnstock_modify_date", "FModifyDate"),
        ("sal_returnstock", "IX_sal_returnstock_billno", "FBILLNO"),
        ("pln_forecast", "IX_pln_forecast_modify_date", "FModifyDate"),
        ("pln_forecast", "IX_pln_forecast_billno", "FBILLNO"),
        ("sal_deliverynotice", "IX_sal_deliverynotice_modify_date", "FModifyDate"),
        ("prd_instock", "IX_prd_instock_modify_date", "FModifyDate"),
        ("prd_mo", "IX_prd_mo_modify_date", "FMODIFYDATE"),
        ("prd_mo", "IX_prd_mo_billno", "FBILLNO"),
        ("prd_moentry", "IX_prd_moentry_fid", "FID"),
        ("prd_moentry", "IX_prd_moentry_modify_date", "FMODIFYDATE"),
        ("prd_moentry", "IX_prd_moentry_material", "FMATERIALID"),
        ("customer", "IX_customer_modify_date", "FModifyDate"),
        ("customer", "IX_customer_number", "FNUMBER"),
        ("prd_ppbom", "IX_prd_ppbom_modify_date", "FMODIFYDATE"),
        ("prd_ppbom", "IX_prd_ppbom_billno", "FBILLNO"),
        ("prd_ppbomentry", "IX_prd_ppbomentry_fid", "FID"),
        ("prd_ppbomentry", "IX_prd_ppbomentry_modify_date", "FMODIFYDATE"),
        ("prd_ppbomentry", "IX_prd_ppbomentry_material", "FMATERIALID"),
        ("stk_inventory", "IX_stk_inventory_material", "FMATERIALID"),
        ("stk_inventory", "IX_stk_inventory_stock", "FSTOCKID"),
        ("stk_inventory", "IX_stk_inventory_mat_stock", "FMATERIALID, FSTOCKID"),
        ("bd_material", "IX_bd_material_modify_date", "FMODIFYDATE"),
        ("bd_material", "IX_bd_material_number", "FNUMBER"),
        ("eng_bom", "IX_eng_bom_modify_date", "FMODIFYDATE"),
        ("eng_bom", "IX_eng_bom_number", "FNUMBER"),
        ("eng_bomchild", "IX_eng_bomchild_fid", "FID"),
        ("eng_bomchild", "IX_eng_bomchild_modify_date", "FMODIFYDATE"),
        ("eng_bomchild", "IX_eng_bomchild_material", "FMATERIALID"),
        ("bd_stock", "IX_bd_stock_modify_date", "FMODIFYDATE"),
        ("bd_stock", "IX_bd_stock_number", "FNUMBER"),
        ("PUR_PurchaseOrder", "IX_pur_order_modify_date", "FModifyDate"),
        ("sub_subreqorder", "IX_sub_reqorder_modify_date", "FModifyDate"),
        ("GL_RPT_AccountBalance", "IX_gl_account_balance_acct", "FACCTID"),
    ]

    # MySQL 索引定义
    MYSQL_INDEXES = [
        # sync_logs 表索引
        ("sync_logs", "idx_sync_logs_start_time", "start_time"),
        ("sync_logs", "idx_sync_logs_table_name", "table_name"),
        ("sync_logs", "idx_sync_logs_status", "status"),
        ("sync_logs", "idx_sync_logs_time_status", "start_time, status"),
        ("sync_logs", "idx_sync_logs_sync_type", "sync_type"),
        # 业务表索引
        ("saleorder", "idx_saleorder_modify_date", "FModifyDate"),
        ("saleorder", "idx_saleorder_billno", "FBILLNO"),
        ("saleorder", "idx_saleorder_cust", "FCUSTID"),
        ("sal_outstock", "idx_sal_outstock_modify_date", "FModifyDate"),
        ("sal_outstock", "idx_sal_outstock_billno", "FBILLNO"),
        ("sal_returnstock", "idx_sal_returnstock_modify_date", "FModifyDate"),
        ("sal_returnstock", "idx_sal_returnstock_billno", "FBILLNO"),
        ("pln_forecast", "idx_pln_forecast_modify_date", "FModifyDate"),
        ("pln_forecast", "idx_pln_forecast_billno", "FBILLNO"),
        ("sal_deliverynotice", "idx_sal_deliverynotice_modify_date", "FModifyDate"),
        ("prd_instock", "idx_prd_instock_modify_date", "FModifyDate"),
        ("prd_mo", "idx_prd_mo_modify_date", "FMODIFYDATE"),
        ("prd_mo", "idx_prd_mo_billno", "FBILLNO"),
        ("prd_moentry", "idx_prd_moentry_fid", "FID"),
        ("prd_moentry", "idx_prd_moentry_modify_date", "FMODIFYDATE"),
        ("prd_moentry", "idx_prd_moentry_material", "FMATERIALID"),
        ("customer", "idx_customer_modify_date", "FModifyDate"),
        ("customer", "idx_customer_number", "FNUMBER"),
        ("prd_ppbom", "idx_prd_ppbom_modify_date", "FMODIFYDATE"),
        ("prd_ppbom", "idx_prd_ppbom_billno", "FBILLNO"),
        ("prd_ppbomentry", "idx_prd_ppbomentry_fid", "FID"),
        ("prd_ppbomentry", "idx_prd_ppbomentry_modify_date", "FMODIFYDATE"),
        ("prd_ppbomentry", "idx_prd_ppbomentry_material", "FMATERIALID"),
        ("stk_inventory", "idx_stk_inventory_material", "FMATERIALID"),
        ("stk_inventory", "idx_stk_inventory_stock", "FSTOCKID"),
        ("stk_inventory", "idx_stk_inventory_mat_stock", "FMATERIALID, FSTOCKID"),
        ("bd_material", "idx_bd_material_modify_date", "FMODIFYDATE"),
        ("bd_material", "idx_bd_material_number", "FNUMBER"),
        ("eng_bom", "idx_eng_bom_modify_date", "FMODIFYDATE"),
        ("eng_bom", "idx_eng_bom_number", "FNUMBER"),
        ("eng_bomchild", "idx_eng_bomchild_fid", "FID"),
        ("eng_bomchild", "idx_eng_bomchild_modify_date", "FMODIFYDATE"),
        ("eng_bomchild", "idx_eng_bomchild_material", "FMATERIALID"),
        ("bd_stock", "idx_bd_stock_modify_date", "FMODIFYDATE"),
        ("bd_stock", "idx_bd_stock_number", "FNUMBER"),
        ("PUR_PurchaseOrder", "idx_pur_order_modify_date", "FModifyDate"),
        ("sub_subreqorder", "idx_sub_reqorder_modify_date", "FModifyDate"),
        ("GL_RPT_AccountBalance", "idx_gl_account_balance_acct", "FACCTID"),
    ]

    def __init__(self):
        self.db_type = None

    def _ensure_connection(self) -> bool:
        """确保数据库连接可用"""
        try:
            if not getattr(mysql_manager, "connection", None):
                return mysql_manager.connect()
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def _get_db_type(self) -> str:
        """获取数据库类型"""
        if self.db_type:
            return self.db_type
        self.db_type = getattr(mysql_manager, "db_type", "sqlserver")
        return self.db_type

    def index_exists_sqlserver(self, table_name: str, index_name: str) -> bool:
        """检查SQL Server索引是否存在"""
        try:
            sql = """
                SELECT COUNT(*) FROM sys.indexes 
                WHERE name = ? AND object_id = OBJECT_ID(?)
            """
            mysql_manager.cursor.execute(sql, (index_name, table_name))
            result = mysql_manager.cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception:
            return False

    def index_exists_mysql(self, table_name: str, index_name: str) -> bool:
        """检查MySQL索引是否存在"""
        try:
            sql = """
                SELECT COUNT(*) FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND table_name = %s 
                AND index_name = %s
            """
            mysql_manager.cursor.execute(sql, (table_name, index_name))
            result = mysql_manager.cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception:
            return False

    def create_index(self, table_name: str, index_name: str, columns: str) -> bool:
        """创建索引"""
        try:
            db_type = self._get_db_type()

            # 检查索引是否已存在
            if db_type == "sqlserver":
                if self.index_exists_sqlserver(table_name, index_name):
                    logger.info(f"索引已存在: {index_name}")
                    return True
            else:
                if self.index_exists_mysql(table_name, index_name):
                    logger.info(f"索引已存在: {index_name}")
                    return True

            # 创建索引
            sql = f"CREATE INDEX {index_name} ON {table_name}({columns})"
            logger.info(f"创建索引: {sql}")
            mysql_manager.cursor.execute(sql)
            logger.info(f"索引创建成功: {index_name}")
            return True

        except Exception as e:
            logger.warning(f"创建索引失败 {index_name}: {e}")
            return False

    def create_all_indexes(self, progress_callback=None) -> Tuple[int, int, List[str]]:
        """
        创建所有索引

        Returns:
            (成功数, 失败数, 失败列表)
        """
        if not self._ensure_connection():
            return 0, 0, ["数据库连接失败"]

        db_type = self._get_db_type()
        indexes = self.SQLSERVER_INDEXES if db_type == "sqlserver" else self.MYSQL_INDEXES

        success_count = 0
        fail_count = 0
        failed_indexes = []

        total = len(indexes)
        for i, (table, index_name, columns) in enumerate(indexes):
            if progress_callback:
                progress_callback(f"创建索引 {index_name} ({i + 1}/{total})", int((i + 1) / total * 100))

            if self.create_index(table, index_name, columns):
                success_count += 1
            else:
                fail_count += 1
                failed_indexes.append(index_name)

        logger.info(f"索引创建完成: 成功 {success_count}, 失败 {fail_count}")
        return success_count, fail_count, failed_indexes

    def analyze_table(self, table_name: str) -> bool:
        """分析表（更新统计信息）"""
        try:
            db_type = self._get_db_type()

            if db_type == "sqlserver":
                # SQL Server 使用 UPDATE STATISTICS
                sql = f"UPDATE STATISTICS {table_name}"
            else:
                # MySQL 使用 ANALYZE TABLE
                sql = f"ANALYZE TABLE {table_name}"

            logger.info(f"分析表: {sql}")
            mysql_manager.cursor.execute(sql)
            return True

        except Exception as e:
            logger.warning(f"分析表失败 {table_name}: {e}")
            return False

    def analyze_all_tables(self) -> int:
        """分析所有表"""
        tables = [
            "sync_logs",
            "saleorder",
            "sal_outstock",
            "sal_returnstock",
            "pln_forecast",
            "sal_deliverynotice",
            "prd_instock",
            "prd_mo",
            "prd_moentry",
            "customer",
            "prd_ppbom",
            "prd_ppbomentry",
            "stk_inventory",
            "bd_material",
            "eng_bom",
            "eng_bomchild",
            "bd_stock",
            "PUR_PurchaseOrder",
            "sub_subreqorder",
            "GL_RPT_AccountBalance",
        ]

        success_count = 0
        for table in tables:
            if self.analyze_table(table):
                success_count += 1

        logger.info(f"表分析完成: 成功 {success_count}/{len(tables)}")
        return success_count

    def get_index_info(self) -> List[dict]:
        """获取索引信息"""
        try:
            if not self._ensure_connection():
                return []

            db_type = self._get_db_type()

            if db_type == "sqlserver":
                sql = """
                    SELECT 
                        OBJECT_NAME(i.object_id) AS table_name,
                        i.name AS index_name,
                        i.type_desc AS index_type,
                        s.user_seeks,
                        s.user_scans,
                        s.user_updates
                    FROM sys.indexes i
                    LEFT JOIN sys.dm_db_index_usage_stats s 
                        ON i.object_id = s.object_id AND i.index_id = s.index_id
                    WHERE i.name IS NOT NULL
                    AND OBJECT_NAME(i.object_id) IN (
                        'sync_logs', 'saleorder', 'sal_outstock', 'sal_returnstock',
                        'pln_forecast', 'sal_deliverynotice', 'prd_instock', 'prd_mo',
                        'prd_moentry', 'customer', 'prd_ppbom', 'prd_ppbomentry',
                        'stk_inventory', 'bd_material', 'eng_bom', 'eng_bomchild',
                        'bd_stock', 'PUR_PurchaseOrder', 'sub_subreqorder', 'GL_RPT_AccountBalance'
                    )
                    ORDER BY OBJECT_NAME(i.object_id), i.name
                """
            else:
                sql = """
                    SELECT 
                        TABLE_NAME as table_name,
                        INDEX_NAME as index_name,
                        INDEX_TYPE as index_type,
                        0 as user_seeks,
                        0 as user_scans,
                        0 as user_updates
                    FROM information_schema.statistics
                    WHERE table_schema = DATABASE()
                    ORDER BY TABLE_NAME, INDEX_NAME
                """

            mysql_manager.cursor.execute(sql)
            columns = [col[0] for col in mysql_manager.cursor.description]
            rows = mysql_manager.cursor.fetchall()

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"获取索引信息失败: {e}")
            return []

    def drop_unused_indexes(self, min_uses: int = 10) -> List[str]:
        """删除未使用的索引（谨慎使用）"""
        # 此功能仅在SQL Server上可用，且需要谨慎使用
        logger.warning("删除未使用索引功能已禁用，如需启用请修改代码")
        return []


# 全局索引管理器实例
index_manager = IndexManager()
