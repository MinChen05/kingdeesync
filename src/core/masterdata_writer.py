"""Master-data writers extracted from MySQLManager."""

from __future__ import annotations

import logging
from typing import Dict, List

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)



def insert_customer_data(manager, data: List[Dict]) -> int:
        """插入客户资料数据"""
        if not data:
            logger.warning("没有客户资料数据需要插入")
            return 0

        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入客户资料数据")
                return 0
        try:
            manager._ensure_additional_columns_for_customer()
            # 准备SQL语句
            sql = """
            INSERT INTO customer 
            (FCUSTID, FNUMBER, FNAME, FGROUP, FSELLERNAME, FSTAFF, FCUSTLEVEL, FCUSTPYPE, FCREATEDATE, FMODIFYDATE)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            FNUMBER = VALUES(FNUMBER),
            FNAME = VALUES(FNAME),
            FGROUP = VALUES(FGROUP),
            FSELLERNAME = VALUES(FSELLERNAME),
            FSTAFF = VALUES(FSTAFF),
            FCUSTLEVEL = VALUES(FCUSTLEVEL),
            FCUSTPYPE = VALUES(FCUSTPYPE),
            FCREATEDATE = VALUES(FCREATEDATE),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            SYNC_TIME = CURRENT_TIMESTAMP
            """
            # 统一走批量插入路径，自动兼容 MySQL 与 SQL Server（转 MERGE）
            return manager._batch_insert(sql, data, manager._prepare_customer_data)

        except Exception as e:
            logger.error(f"插入客户资料数据失败: {str(e)}")
            return 0

def insert_stk_inventory(manager, data: List[Dict]) -> int:
        """插入即时库存数据（确保表存在）"""
        if not data:
            logger.warning("没有即时库存数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入即时库存数据")
                return 0
        try:
            # 跳过自动建表与字段检查，直接执行插入

            # 兼容新增字段：确保目标表存在 FMODIFYDATE 列（MySQL/SQL Server）
            try:
                is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"
                table_name = "stk_inventory"
                if is_sqlserver:
                    manager.cursor.execute(
                        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME='FMODIFYDATE'",
                        (table_name,),
                    )
                else:
                    manager.cursor.execute(
                        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME='FMODIFYDATE'",
                        (table_name,),
                    )
                exists = manager.cursor.fetchone() is not None
                if not exists:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN FMODIFYDATE DATETIME NULL"
                    if is_sqlserver:
                        alter_sql = f"ALTER TABLE {table_name} ADD FMODIFYDATE DATETIME NULL"
                    manager.cursor.execute(alter_sql)
                    try:
                        manager.connection.commit()
                    except Exception:
                        pass
                    logger.info(f"[{table_name}] 已自动添加 FMODIFYDATE 列")
            except Exception as e:
                logger.warning(f"预检查/添加 FMODIFYDATE 列失败（不影响后续插入）：{e}")

            # 按新字段顺序构造插入SQL（用于MySQL直插与SQL Server列解析）
            sql = """
                INSERT INTO stk_inventory 
                (FID, FSTOCKORGID, FSTOCKID, FSTOCKLOCID, FSTOCKSTATUSID, FBASEUNITID, FBASEQTY, FMATERIALID, FMODIFYDATE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FSTOCKORGID = VALUES(FSTOCKORGID),
                    FSTOCKID = VALUES(FSTOCKID),
                    FSTOCKLOCID = VALUES(FSTOCKLOCID),
                    FSTOCKSTATUSID = VALUES(FSTOCKSTATUSID),
                    FBASEUNITID = VALUES(FBASEUNITID),
                    FBASEQTY = VALUES(FBASEQTY),
                    FMATERIALID = VALUES(FMATERIALID),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_stk_inventory_data)
        except Exception as e:
            logger.error(f"插入即时库存数据失败: {str(e)}")
            return 0

def insert_bd_material(manager, data: List[Dict]) -> int:
        """插入物料主数据（BD_MATERIAL）"""
        if not data:
            logger.warning("没有物料数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入物料数据")
                return 0
        try:
            # 存储物料分组中文名称前，先确保目标列可写入文本
            manager._ensure_additional_columns_for_bd_material()
            manager._ensure_bd_material_group_text_column()

            sql = """
                INSERT INTO bd_material 
                (FMATERIALID, FNUMBER, FMASTERID, FMATERIALGROUP, FCREATEORGID, FUSEORGID,
                 FCREATEDATE, FMODIFYDATE, FDOCUMENTSTATUS, FFORBIDSTATUS, FAPPROVEDATE,
                 FREFSTATUS, F_TMHE_TEXT, F_JY_TEXT, F_JY_TEXT1, F_JY_TEXT2, F_JYX_TEXT1, F_JYX_TEXT2, F_JYX_TEXT4,
                 F_JYX_TEXT3, F_JYX_ASSISTANT, F_JYX_ASSISTANT1, F_JYX_ASSISTANT2, F_JY_QTY, F_JY_QTY1,
                 F_KDKF_HJFS, F_ORA_TEXT_9SB, F_ORA_TEXT_QTR, F_ORA_TEXT_QTR1, FERPCLSID, FCATEGORYID, FTYPEID,
                 FBARCODE, FNAME, FSPECIFICATION, FDESCRIPTION)
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    FNUMBER = VALUES(FNUMBER),
                    FMASTERID = VALUES(FMASTERID),
                    FMATERIALGROUP = VALUES(FMATERIALGROUP),
                    FCREATEORGID = VALUES(FCREATEORGID),
                    FUSEORGID = VALUES(FUSEORGID),
                    FCREATEDATE = VALUES(FCREATEDATE),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    FDOCUMENTSTATUS = VALUES(FDOCUMENTSTATUS),
                    FFORBIDSTATUS = VALUES(FFORBIDSTATUS),
                    FAPPROVEDATE = VALUES(FAPPROVEDATE),
                    FREFSTATUS = VALUES(FREFSTATUS),
                    F_TMHE_TEXT = VALUES(F_TMHE_TEXT),
                    F_JY_TEXT = VALUES(F_JY_TEXT),
                    F_JY_TEXT1 = VALUES(F_JY_TEXT1),
                    F_JY_TEXT2 = VALUES(F_JY_TEXT2),
                    F_JYX_TEXT1 = VALUES(F_JYX_TEXT1),
                    F_JYX_TEXT2 = VALUES(F_JYX_TEXT2),
                    F_JYX_TEXT4 = VALUES(F_JYX_TEXT4),
                    F_JYX_TEXT3 = VALUES(F_JYX_TEXT3),
                    F_JYX_ASSISTANT = VALUES(F_JYX_ASSISTANT),
                    F_JYX_ASSISTANT1 = VALUES(F_JYX_ASSISTANT1),
                    F_JYX_ASSISTANT2 = VALUES(F_JYX_ASSISTANT2),
                    F_JY_QTY = VALUES(F_JY_QTY),
                    F_JY_QTY1 = VALUES(F_JY_QTY1),
                    F_KDKF_HJFS = VALUES(F_KDKF_HJFS),
                    F_ORA_TEXT_9SB = VALUES(F_ORA_TEXT_9SB),
                    F_ORA_TEXT_QTR = VALUES(F_ORA_TEXT_QTR),
                    F_ORA_TEXT_QTR1 = VALUES(F_ORA_TEXT_QTR1),
                    FERPCLSID = VALUES(FERPCLSID),
                    FCATEGORYID = VALUES(FCATEGORYID),
                    FTYPEID = VALUES(FTYPEID),
                    FBARCODE = VALUES(FBARCODE),
                    FNAME = VALUES(FNAME),
                    FSPECIFICATION = VALUES(FSPECIFICATION),
                    FDESCRIPTION = VALUES(FDESCRIPTION),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_bd_material_data)
        except Exception as e:
            logger.error(f"插入物料数据失败: {str(e)}")
            return 0

def insert_bd_stock(manager, data: List[Dict]) -> int:
        """插入仓库主数据（BD_STOCK）"""
        if not data:
            logger.warning("没有仓库数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入仓库数据")
                return 0
        try:
            # 跳过自动建表与字段检查，直接执行插入

            # 插入 SQL（兼�?MySQL 直插�?SQL Server MERGE�?
            sql = """
                INSERT INTO bd_stock 
                (FSTOCKID, FMASTERID, FNUMBER, FUSEORGID, FMODIFYDATE, FDOCUMENTSTATUS, FFORBIDSTATUS, FNAME)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FMASTERID = VALUES(FMASTERID),
                    FNUMBER = VALUES(FNUMBER),
                    FUSEORGID = VALUES(FUSEORGID),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    FDOCUMENTSTATUS = VALUES(FDOCUMENTSTATUS),
                    FFORBIDSTATUS = VALUES(FFORBIDSTATUS),
                    FNAME = VALUES(FNAME),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_bd_stock_data)
        except Exception as e:
            logger.error(f"插入仓库数据失败: {str(e)}")
            return 0

def insert_bos_assistantdata_detail(manager, data: List[Dict]) -> int:
        """插入辅助资料明细（BOS_ASSISTANTDATA_DETAIL）"""
        if not data:
            logger.warning("没有辅助资料明细数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入辅助资料明细数据")
                return 0
        try:
            # 跳过自动建表与字段检查，直接执行插入

            # 插入 SQL（兼容字典/列表准备函数）
            sql = """
                INSERT INTO bos_assistantdata_detail 
                (FID, FNUMBER, FDataValue, FMODIFYDATE)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FNUMBER = VALUES(FNUMBER),
                    FDataValue = VALUES(FDataValue),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_bos_assistantdata_detail_data)
        except Exception as e:
            logger.error(f"插入辅助资料明细数据失败: {str(e)}")
            return 0

def insert_assistantdata(manager, data: List[Dict]) -> int:
        """插入辅助资料（ASSISTANTDATA）"""
        if not data:
            logger.warning("没有辅助资料数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入辅助资料数据")
                return 0
        try:
            # 跳过自动建表与字段检查，直接执行插入
            # 插入 SQL（兼容字�?列表准备函数�?
            sql = """
                INSERT INTO ASSISTANTDATA 
                (FID, FNUMBER, FDataValue, FMODIFYDATE)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FNUMBER = VALUES(FNUMBER),
                    FDataValue = VALUES(FDataValue),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_assistantdata_data)
        except Exception as e:
            logger.error(f"插入辅助资料数据失败: {str(e)}")
            return 0

def insert_eng_bom(manager, data: List[Dict]) -> int:
        """插入物料清单（ENG_BOM）"""
        if not data:
            logger.warning("没有物料清单数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入物料清单数据")
                return 0
        try:
            # 跳过自动建表与字段检查，直接执行插入

            sql = """
                INSERT INTO eng_bom 
                (FID, FMASTERID, FNUMBER, FBILLTYPE, FDOCUMENTSTATUS, FMATERIALID, FFORBIDSTATUS, FUSEORGID, FMODIFYDATE, FBASEUNITID, FQTY, FBOMUSE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FMASTERID = VALUES(FMASTERID),
                    FNUMBER = VALUES(FNUMBER),
                    FBILLTYPE = VALUES(FBILLTYPE),
                    FDOCUMENTSTATUS = VALUES(FDOCUMENTSTATUS),
                    FMATERIALID = VALUES(FMATERIALID),
                    FFORBIDSTATUS = VALUES(FFORBIDSTATUS),
                    FUSEORGID = VALUES(FUSEORGID),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    FBASEUNITID = VALUES(FBASEUNITID),
                    FQTY = VALUES(FQTY),
                    FBOMUSE = VALUES(FBOMUSE),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_eng_bom_data)
        except Exception as e:
            logger.error(f"插入物料清单数据失败: {str(e)}")
            return 0

def insert_eng_bom_child(manager, data: List[Dict]) -> int:
        """插入物料清单子项（ENG_BOM 子项）"""
        if not data:
            logger.warning("没有物料清单子项数据需要插入")
            return 0
        if not manager.connection or not manager.cursor:
            logger.warning("数据库连接丢失，尝试重新连接...")
            if not manager.connect():
                logger.error("重新连接数据库失败，无法插入物料清单子项数据")
                return 0
        try:
            manager._ensure_additional_columns_for_eng_bomchild()

            sql = """
                INSERT INTO eng_bomchild
                (FID, FENTRYID, FSEQ, FMATERIALID, FCHILDNUMBER, FCHILDNAME, FNUMERATOR, FDENOMINATOR, FISSUETYPE, FBACKFLUSHTYPE, FSUPPLYORG, FSTOCKID, FENTRYROWID, FREPLACEGROUP, FQTY, FACTUALQTY, FMASTERID, FMATERIALTYPE, FMODIFYDATE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    FSEQ = VALUES(FSEQ),
                    FMATERIALID = VALUES(FMATERIALID),
                    FCHILDNUMBER = VALUES(FCHILDNUMBER),
                    FCHILDNAME = VALUES(FCHILDNAME),
                    FNUMERATOR = VALUES(FNUMERATOR),
                    FDENOMINATOR = VALUES(FDENOMINATOR),
                    FISSUETYPE = VALUES(FISSUETYPE),
                    FBACKFLUSHTYPE = VALUES(FBACKFLUSHTYPE),
                    FSUPPLYORG = VALUES(FSUPPLYORG),
                    FSTOCKID = VALUES(FSTOCKID),
                    FENTRYROWID = VALUES(FENTRYROWID),
                    FREPLACEGROUP = VALUES(FREPLACEGROUP),
                    FQTY = VALUES(FQTY),
                    FACTUALQTY = VALUES(FACTUALQTY),
                    FMASTERID = VALUES(FMASTERID),
                    FMATERIALTYPE = VALUES(FMATERIALTYPE),
                    FMODIFYDATE = VALUES(FMODIFYDATE),
                    SYNC_TIME = CURRENT_TIMESTAMP
                """
            return manager._batch_insert(sql, data, manager._prepare_eng_bom_child_data)
        except Exception as e:
            logger.error(f"插入物料清单子项数据失败: {str(e)}")
            return 0

