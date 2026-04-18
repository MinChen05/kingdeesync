"""Production domain writers extracted from MySQLManager."""

from __future__ import annotations



import logging

from typing import Dict, List



from src.config.config_manager import config_manager



logger = logging.getLogger(__name__)



def insert_production_orders(manager, data: List[Dict]) -> int:
        """插入生产订单数据"""
        if not data:
            return 0

        # SQL Server/ MySQL 通用：新增 FCREATEDATE 字段
        sql = """
        INSERT INTO prd_mo (
            FID, FBILLNO, FBILLTYPE, FDATE, FPRDORGID, FWORKSHOPID, FDocumentStatus, FCREATEDATE, FMODIFYDATE, FCANCELSTATUS
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FBILLNO = VALUES(FBILLNO),
            FBILLTYPE = VALUES(FBILLTYPE),
            FDATE = VALUES(FDATE),
            FPRDORGID = VALUES(FPRDORGID),
            FWORKSHOPID = VALUES(FWORKSHOPID),
            FDocumentStatus = VALUES(FDocumentStatus),
            FCREATEDATE = VALUES(FCREATEDATE),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            FCANCELSTATUS = VALUES(FCANCELSTATUS)
        """
        # 确保目标库存在 FCREATEDATE（SQL Server/MySQL）
        try:
            if not manager.connection or not manager.cursor:
                manager.connect()
            tbl = "prd_mo"
            if getattr(manager, "db_type", "mysql") == "sqlserver":
                manager.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME='FCREATEDATE'", (tbl,)
                )
                exists = manager.cursor.fetchone() is not None
                if not exists:
                    manager.cursor.execute("ALTER TABLE prd_mo ADD FCREATEDATE DATETIME NULL")
                    try:
                        manager.connection.commit()
                    except Exception:
                        pass
            else:
                manager.cursor.execute(
                    "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME='FCREATEDATE'", (tbl,)
                )
                exists = manager.cursor.fetchone() is not None
                if not exists:
                    manager.cursor.execute("ALTER TABLE prd_mo ADD COLUMN FCREATEDATE DATETIME NULL")
                    try:
                        manager.connection.commit()
                    except Exception:
                        pass
        except Exception:
            pass

        return manager._batch_insert(sql, data, manager._prepare_production_order_data)

def insert_prd_moentry(manager, data: List[Dict]) -> int:
        """插入生产订单明细数据（PRD_MOENTRY）"""
        if not data:
            return 0

        # 确保目标表存在 F_ora_Text1, FMATERIALNUMBER, FDESCRIPTION 列
        try:
            if not manager.connection or not manager.cursor:
                manager.connect()
            tbl = "PRD_MOENTRY"
            is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"

            # 要检查的列列表
            columns_to_check = [
                ("F_ora_Text1", "NVARCHAR(255)" if is_sqlserver else "VARCHAR(255)"),
                ("FMATERIALNUMBER", "NVARCHAR(255)" if is_sqlserver else "VARCHAR(255)"),
                ("FDESCRIPTION", "NVARCHAR(255)" if is_sqlserver else "VARCHAR(255)"),
                ("FSRCBILLENTRYSEQ", "INT" if is_sqlserver else "INT"),
            ]

            for col_name, col_type in columns_to_check:
                if is_sqlserver:
                    col_check_sql = "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?"
                    alter_sql = f"ALTER TABLE PRD_MOENTRY ADD {col_name} {col_type} NULL"
                else:
                    col_check_sql = "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s"
                    alter_sql = f"ALTER TABLE PRD_MOENTRY ADD COLUMN {col_name} {col_type} NULL"

                manager.cursor.execute(col_check_sql, (tbl, col_name))
                if not manager.cursor.fetchone():
                    logger.info(f"正在为 PRD_MOENTRY 表添加 {col_name} 列...")
                    manager.cursor.execute(alter_sql)
                    try:
                        manager.connection.commit()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"检查/添加 PRD_MOENTRY 列失败: {e}")

        sql = """
        INSERT INTO PRD_MOENTRY (
            FID, FENTRYID, FSEQ, FSRCBILLNO, FSRCBILLENTRYSEQ, FSRCBILLENTRYID, FSALEORDERNO, FMATERIALID, FMATERIALNUMBER, FDESCRIPTION, FQTY, FSTOCKINQUAAUXQTY, FPLANSTARTDATE, FPLANFINISHDATE, FBOMID, FREQUESTORGID, FSTOCKINORGID, FSTOCKID, FWORKSHOPID, FSTATUS, F_ora_Text1, FMODIFYDATE
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FSEQ = VALUES(FSEQ),
            FSRCBILLNO = VALUES(FSRCBILLNO),
            FSRCBILLENTRYSEQ = VALUES(FSRCBILLENTRYSEQ),
            FSRCBILLENTRYID = VALUES(FSRCBILLENTRYID),
            FSALEORDERNO = VALUES(FSALEORDERNO),
            FMATERIALID = VALUES(FMATERIALID),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FDESCRIPTION = VALUES(FDESCRIPTION),
            FQTY = VALUES(FQTY),
            FSTOCKINQUAAUXQTY = VALUES(FSTOCKINQUAAUXQTY),
            FPLANSTARTDATE = VALUES(FPLANSTARTDATE),
            FPLANFINISHDATE = VALUES(FPLANFINISHDATE),
            FBOMID = VALUES(FBOMID),
            FREQUESTORGID = VALUES(FREQUESTORGID),
            FSTOCKINORGID = VALUES(FSTOCKINORGID),
            FSTOCKID = VALUES(FSTOCKID),
            FWORKSHOPID = VALUES(FWORKSHOPID),
            FSTATUS = VALUES(FSTATUS),
            F_ora_Text1 = VALUES(F_ora_Text1),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            SYNC_TIME = CURRENT_TIMESTAMP
        """

        return manager._batch_insert(sql, data, manager._prepare_prd_moentry_data)

def insert_prd_ppbom(manager, data: List[Dict]) -> int:
        """插入生产用料清单主表数据（扩展字段）"""
        if not data:
            return 0
        sql = """
        INSERT INTO prd_ppbom (
            FID, FBILLNO, FMATERIALID, FPrdOrgId, FWorkShopID, FBOMID, FBaseQty, FQty, FMOTYPE, FMOID, FMOBILLNO, FMOENTRYID, FMOENTRYSEQ, FDocumentStatus, FCreateDate, FModifyDate, FApproveDate, FSaleOrderID, FSaleOrderNo, FSaleOrderEntryID, FSaleOrderEntrySeq
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            FBILLNO=VALUES(FBILLNO),
            FMATERIALID=VALUES(FMATERIALID),
            FPrdOrgId=VALUES(FPrdOrgId),
            FWorkShopID=VALUES(FWorkShopID),
            FBOMID=VALUES(FBOMID),
            FBaseQty=VALUES(FBaseQty),
            FQty=VALUES(FQty),
            FMOTYPE=VALUES(FMOTYPE),
            FMOID=VALUES(FMOID),
            FMOBILLNO=VALUES(FMOBILLNO),
            FMOENTRYID=VALUES(FMOENTRYID),
            FMOENTRYSEQ=VALUES(FMOENTRYSEQ),
            FDocumentStatus=VALUES(FDocumentStatus),
            FCreateDate=VALUES(FCreateDate),
            FModifyDate=VALUES(FModifyDate),
            FApproveDate=VALUES(FApproveDate),
            FSaleOrderID=VALUES(FSaleOrderID),
            FSaleOrderNo=VALUES(FSaleOrderNo),
            FSaleOrderEntryID=VALUES(FSaleOrderEntryID),
            FSaleOrderEntrySeq=VALUES(FSaleOrderEntrySeq),
            SYNC_TIME=CURRENT_TIMESTAMP
        """
        return manager._batch_insert(sql, data, manager._prepare_prd_ppbom_data)

def insert_prd_ppbom_entry(manager, data: List[Dict]) -> int:
        """插入生产用料清单明细数据"""
        if not data:
            return 0

        # SQL Server 专用处理：检查并修正字段类型
        if getattr(manager, "db_type", "mysql") == "sqlserver":
            try:

                def _drop_indexes_for_column(column_name: str) -> None:
                    try:
                        manager.cursor.execute(
                            """
                            SELECT i.name
                            FROM sys.indexes i
                            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                            WHERE i.object_id = OBJECT_ID('prd_ppbomentry')
                              AND c.name = ?
                              AND i.is_primary_key = 0
                              AND i.is_unique_constraint = 0
                            """,
                            (column_name,),
                        )
                        rows = manager.cursor.fetchall() or []
                        for r in rows:
                            idx_name = None
                            if isinstance(r, dict):
                                idx_name = r.get("name")
                            elif isinstance(r, (list, tuple)) and len(r) > 0:
                                idx_name = r[0]
                            if idx_name:
                                manager.cursor.execute(f"DROP INDEX {idx_name} ON prd_ppbomentry")
                        try:
                            manager.connection.commit()
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"删除 prd_ppbomentry.{column_name} 关联索引失败: {e}")

                manager.cursor.execute(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'prd_ppbomentry'
                    AND COLUMN_NAME IN ('FMATERIALID', 'FMOBILLNO')
                    """
                )
                rows = manager.cursor.fetchall() or []
                col_types = {str(r[0]).upper(): str(r[1]).lower() for r in rows if len(r) >= 2}
                numeric_types = {"int", "bigint", "numeric", "decimal", "float", "real", "money", "smallmoney"}
                if col_types.get("FMATERIALID") in numeric_types:
                    logger.info("检测到 prd_ppbomentry.FMATERIALID 为数值类型，正在转换为 NVARCHAR(64)...")
                    try:
                        _drop_indexes_for_column("FMATERIALID")
                        manager.cursor.execute("ALTER TABLE prd_ppbomentry ALTER COLUMN FMATERIALID NVARCHAR(64)")
                        manager.connection.commit()
                        logger.info("已将 prd_ppbomentry.FMATERIALID 修改为 NVARCHAR(64)")
                    except Exception as e:
                        logger.warning(f"修改 prd_ppbomentry.FMATERIALID 失败: {e}")
                if col_types.get("FMOBILLNO") in numeric_types:
                    logger.info("检测到 prd_ppbomentry.FMOBILLNO 为数值类型，正在转换为 NVARCHAR(64)...")
                    try:
                        _drop_indexes_for_column("FMOBILLNO")
                        manager.cursor.execute("ALTER TABLE prd_ppbomentry ALTER COLUMN FMOBILLNO NVARCHAR(64)")
                        manager.connection.commit()
                        logger.info("已将 prd_ppbomentry.FMOBILLNO 修改为 NVARCHAR(64)")
                    except Exception as e:
                        logger.warning(f"修改 prd_ppbomentry.FMOBILLNO 失败: {e}")
            except Exception as e:
                logger.warning(f"检查 prd_ppbomentry 结构失败: {e}")

        # SQLServer 需要将 API 字段 FMATERIALID2/FNEEDDATE2/FNEEDQTY2 映射到库字段 FMATERIALID/FNEEDDATE/FNEEDQTY
        if getattr(manager, "db_type", "mysql") == "sqlserver":
            sql = """
                INSERT INTO prd_ppbomentry (
                    FID, FENTRYID, FSEQ, FMOID, FMOBILLNO, FMOENTRYID, FMOENTRYSEQ, FBOMENTRYID, FMATERIALID, FNEEDDATE,
                    FBASESTDQTY, FBASENEEDQTY, FBASEMUSTQTY, FSTDQTY, FNEEDQTY, FMUSTQTY, FBASEPICKEDQTY, FPLANEND, FMODIFYDATE
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    FID=VALUES(FID),
                    FSEQ=VALUES(FSEQ),
                    FMOID=VALUES(FMOID),
                    FMOBILLNO=VALUES(FMOBILLNO),
                    FMOENTRYID=VALUES(FMOENTRYID),
                    FMOENTRYSEQ=VALUES(FMOENTRYSEQ),
                    FBOMENTRYID=VALUES(FBOMENTRYID),
                    FMATERIALID=VALUES(FMATERIALID),
                    FNEEDDATE=VALUES(FNEEDDATE),
                    FBASESTDQTY=VALUES(FBASESTDQTY),
                    FBASENEEDQTY=VALUES(FBASENEEDQTY),
                    FBASEMUSTQTY=VALUES(FBASEMUSTQTY),
                    FSTDQTY=VALUES(FSTDQTY),
                    FNEEDQTY=VALUES(FNEEDQTY),
                    FMUSTQTY=VALUES(FMUSTQTY),
                    FBASEPICKEDQTY=VALUES(FBASEPICKEDQTY),
                    FPLANEND=VALUES(FPLANEND),
                    FMODIFYDATE=VALUES(FMODIFYDATE),
                    SYNC_TIME=CURRENT_TIMESTAMP
                """
        else:
            sql = """
                INSERT INTO prd_ppbomentry (
                    FID, FENTRYID, FSEQ, FMOID, FMOBILLNO, FMOENTRYID, FMOENTRYSEQ, FBOMENTRYID, FMATERIALID2, FNEEDDATE2,
                    FBASESTDQTY, FBASENEEDQTY, FBASEMUSTQTY, FSTDQTY, FNEEDQTY2, FMUSTQTY, FBASEPICKEDQTY, FPLANEND, FMODIFYDATE
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    FID=VALUES(FID),
                    FSEQ=VALUES(FSEQ),
                    FMOID=VALUES(FMOID),
                    FMOBILLNO=VALUES(FMOBILLNO),
                    FMOENTRYID=VALUES(FMOENTRYID),
                    FMOENTRYSEQ=VALUES(FMOENTRYSEQ),
                    FBOMENTRYID=VALUES(FBOMENTRYID),
                    FMATERIALID2=VALUES(FMATERIALID2),
                    FNEEDDATE2=VALUES(FNEEDDATE2),
                    FBASESTDQTY=VALUES(FBASESTDQTY),
                    FBASENEEDQTY=VALUES(FBASENEEDQTY),
                    FBASEMUSTQTY=VALUES(FBASEMUSTQTY),
                    FSTDQTY=VALUES(FSTDQTY),
                    FNEEDQTY2=VALUES(FNEEDQTY2),
                    FMUSTQTY=VALUES(FMUSTQTY),
                    FBASEPICKEDQTY=VALUES(FBASEPICKEDQTY),
                    FPLANEND=VALUES(FPLANEND),
                    FMODIFYDATE=VALUES(FMODIFYDATE),
                    SYNC_TIME=CURRENT_TIMESTAMP
                """
        return manager._batch_insert(sql, data, manager._prepare_prd_ppbom_entry_data)

def insert_prd_ppbom_main(manager, data: List[Dict]) -> int:
        """插入生产用料清单主表数据（精简字段）"""
        if not data:
            return 0
        sql = """
            INSERT INTO prd_ppbom_main (
                FID, FBILLNO, FMATERIALID, FPrdOrgId, FWorkShopID, FBaseQty, FCreateDate, FModifyDate
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                FBILLNO=VALUES(FBILLNO),
                FMATERIALID=VALUES(FMATERIALID),
                FPrdOrgId=VALUES(FPrdOrgId),
                FWorkShopID=VALUES(FWorkShopID),
                FBaseQty=VALUES(FBaseQty),
                FCreateDate=VALUES(FCreateDate),
                FModifyDate=VALUES(FModifyDate),
                SYNC_TIME=CURRENT_TIMESTAMP
            """
        return manager._batch_insert(sql, data, manager._prepare_prd_ppbom_main_data)

def insert_prd_instock(manager, data: List[Dict]) -> int:
        """插入生产入库单数据（PRD_INSTOCK）"""
        if not data:
            return 0

        sql = """
        INSERT INTO prd_instock (
            FID, FENTRYID, FBILLNO, FDATE, FMATERIALID, FREALQTY, FSRCENTRYSEQ, FSRCBILLNO,
            FMoEntrySeq, FDOCUMENTSTATUS, FMoBillNo, FModifyDate
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FBILLNO = VALUES(FBILLNO),
            FDATE = VALUES(FDATE),
            FMATERIALID = VALUES(FMATERIALID),
            FREALQTY = VALUES(FREALQTY),
            FSRCENTRYSEQ = VALUES(FSRCENTRYSEQ),
            FSRCBILLNO = VALUES(FSRCBILLNO),
            FMoEntrySeq = VALUES(FMoEntrySeq),
            FDOCUMENTSTATUS = VALUES(FDOCUMENTSTATUS),
            FMoBillNo = VALUES(FMoBillNo),
            FModifyDate = VALUES(FModifyDate),
            SYNC_TIME = CURRENT_TIMESTAMP
        """

        try:
            if not manager.connection or not manager.cursor:
                manager.connect()
            tbl = "prd_instock"
            is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"
            if is_sqlserver:
                col_sql = "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?"
            else:
                col_sql = "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s"

            def _ensure_col(col_name: str, ddl_sqlserver: str, ddl_mysql: str) -> None:
                try:
                    if is_sqlserver:
                        manager.cursor.execute(col_sql, (tbl, col_name))
                    else:
                        manager.cursor.execute(col_sql, (tbl, col_name))
                    exists = manager.cursor.fetchone() is not None
                    if not exists:
                        if is_sqlserver:
                            manager.cursor.execute(ddl_sqlserver)
                        else:
                            manager.cursor.execute(ddl_mysql)
                        try:
                            manager.connection.commit()
                        except Exception:
                            pass
                except Exception:
                    pass

            _ensure_col(
                "FMATERIALID",
                "ALTER TABLE prd_instock ADD FMATERIALID INT NULL",
                "ALTER TABLE prd_instock ADD COLUMN FMATERIALID INT NULL",
            )
            _ensure_col(
                "FSRCENTRYSEQ",
                "ALTER TABLE prd_instock ADD FSRCENTRYSEQ INT NULL",
                "ALTER TABLE prd_instock ADD COLUMN FSRCENTRYSEQ INT NULL",
            )
            _ensure_col(
                "FMOBILLNO",
                "ALTER TABLE prd_instock ADD FMoBillNo NVARCHAR(160) NULL",
                "ALTER TABLE prd_instock ADD COLUMN FMoBillNo VARCHAR(160) NULL",
            )
            _ensure_col(
                "FModifyDate",
                "ALTER TABLE prd_instock ADD FModifyDate DATETIME NULL",
                "ALTER TABLE prd_instock ADD COLUMN FModifyDate DATETIME NULL",
            )
            _ensure_col(
                "FMOENTRYSEQ",
                "ALTER TABLE prd_instock ADD FMoEntrySeq INT NULL",
                "ALTER TABLE prd_instock ADD COLUMN FMoEntrySeq INT NULL",
            )
            _ensure_col(
                "FDOCUMENTSTATUS",
                "ALTER TABLE prd_instock ADD FDOCUMENTSTATUS CHAR(1) NULL",
                "ALTER TABLE prd_instock ADD COLUMN FDOCUMENTSTATUS CHAR(1) NULL",
            )
        except Exception:
            pass

        return manager._batch_insert(sql, data, manager._prepare_prd_instock_data)

