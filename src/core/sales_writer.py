"""Sales and transactional writers extracted from MySQLManager."""

from __future__ import annotations

import logging
from typing import Dict, List

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)



def insert_sales_orders(manager, data: List[Dict]) -> int:
        """插入销售订单数据"""
        if not data:
            return 0

        # 确保新增字段存在于目标表（FMATERIALID、FDOCUMENTSTATUS）
        try:
            manager._ensure_additional_columns_for_saleorder()
        except Exception as e:
            logger.warning(f"[saleorder] 自动检查/添加列失败（可忽略）：{e}")

        sql = """
        INSERT INTO saleorder (
            FID, FENTRYID, FSEQ, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME,
            FSALEORONAME, FCUSTGROUP, FMATERIALID, FMATERIALNAME, FMATERIALNUMBER, FMATERIALTYPE,
            FMATERIALSORT, FDESCRIPTION, FQTY, FCloseStatus, FDeliveryDate, FModifyDate, FStockOutQty,
            FMrpCloseStatus, FDOCUMENTSTATUS, SYNC_TIME
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FID = VALUES(FID),
            FSEQ = VALUES(FSEQ),
            FBILLTYPENAME = VALUES(FBILLTYPENAME),
            FBILLNO = VALUES(FBILLNO),
            FDATE = VALUES(FDATE),
            FCUSTNAME = VALUES(FCUSTNAME),
            FSALEORONAME = VALUES(FSALEORONAME),
            FCUSTGROUP = VALUES(FCUSTGROUP),
            FMATERIALID = VALUES(FMATERIALID),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FMATERIALTYPE = VALUES(FMATERIALTYPE),
            FMATERIALSORT = VALUES(FMATERIALSORT),
            FDESCRIPTION = VALUES(FDESCRIPTION),
            FQTY = VALUES(FQTY),
            FCloseStatus = VALUES(FCloseStatus),
            FDeliveryDate = VALUES(FDeliveryDate),
            FModifyDate = VALUES(FModifyDate),
            FStockOutQty = VALUES(FStockOutQty),
            FMrpCloseStatus = VALUES(FMrpCloseStatus),
            FDOCUMENTSTATUS = VALUES(FDOCUMENTSTATUS),
            SYNC_TIME = CURRENT_TIMESTAMP
        """

        inserted = manager._batch_insert(sql, data, manager._prepare_sales_order_data)
        # 回填 FMATERIALID（基于 FMATERIALNUMBER 与物料主数据的映射），避免 API 不返回内码导致为空
        try:
            if getattr(manager, "db_type", "mysql") == "sqlserver":
                backfill_sql = (
                    "UPDATE t SET t.FMATERIALID = m.FMATERIALID "
                    "FROM saleorder t INNER JOIN bd_material m ON t.FMATERIALNUMBER = m.FNUMBER "
                    "WHERE t.FMATERIALID IS NULL AND m.FMATERIALID IS NOT NULL"
                )
            else:
                backfill_sql = (
                    "UPDATE saleorder t INNER JOIN bd_material m ON t.FMATERIALNUMBER = m.FNUMBER "
                    "SET t.FMATERIALID = m.FMATERIALID "
                    "WHERE t.FMATERIALID IS NULL AND m.FMATERIALID IS NOT NULL"
                )
            manager.cursor.execute(backfill_sql)
            try:
                manager.connection.commit()
            except Exception:
                pass
            logger.info("[saleorder] 已基于物料表回填 FMATERIALID（按 FMATERIALNUMBER 匹配）")
        except Exception as e:
            logger.warning(f"[saleorder] 回填 FMATERIALID 失败：{e}")
        return inserted

def insert_sales_returnstock(manager, data: List[Dict]) -> int:
        """插入销售退货单数据"""
        if not data:
            return 0

        sql = """
        INSERT INTO sal_returnstock (
            FENTRYID, FBILLNO, FDATE, FRetcustNAME, FRetcustGROUP, FSalesManNAME,
            FReturnType, FRealQty, FMaterialNAME, FMaterialFNUMBER, FMaterialTYPE,
            FMaterialSort, FDeliveryDate, FModifyDate
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FBILLNO = VALUES(FBILLNO),
            FDATE = VALUES(FDATE),
            FRetcustNAME = VALUES(FRetcustNAME),
            FRetcustGROUP = VALUES(FRetcustGROUP),
            FSalesManNAME = VALUES(FSalesManNAME),
            FReturnType = VALUES(FReturnType),
            FRealQty = VALUES(FRealQty),
            FMaterialNAME = VALUES(FMaterialNAME),
            FMaterialFNUMBER = VALUES(FMaterialFNUMBER),
            FMaterialTYPE = VALUES(FMaterialTYPE),
            FMaterialSort = VALUES(FMaterialSort),
            FDeliveryDate = VALUES(FDeliveryDate),
            FModifyDate = VALUES(FModifyDate)
        """

        return manager._batch_insert(sql, data, manager._prepare_sales_returnstock_data)

def insert_sales_outstock(manager, data: List[Dict]) -> int:
        """插入销售出库单数据"""
        if not data:
            return 0

        # 检查并添加 FDESCRIPTION 列
        try:
            conn = manager.pool.connection()
            try:
                with conn.cursor() as cursor:
                    is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"
                    table_name = "sal_outstock"
                    col_name = "FDESCRIPTION"

                    if is_sqlserver:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                            (table_name, col_name),
                        )
                    else:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                            (table_name, col_name),
                        )

                    if not cursor.fetchone():
                        logger.info(f"正在为 {table_name} 表添加 {col_name} 列...")
                        if is_sqlserver:
                            cursor.execute(f"ALTER TABLE {table_name} ADD {col_name} NVARCHAR(2000) NULL")
                        else:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} VARCHAR(2000) NULL")
                        conn.commit()
                    else:
                        # 尝试调整列宽
                        try:
                            if is_sqlserver:
                                cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} NVARCHAR(2000) NULL")
                            else:
                                cursor.execute(f"ALTER TABLE {table_name} MODIFY COLUMN {col_name} VARCHAR(2000) NULL")
                            conn.commit()
                        except Exception:
                            pass
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"检查/添加列失败: {e}")

        sql = """
        INSERT INTO sal_outstock (
            FENTRYID, FSEQ, FBILLTYPENAME, FBILLNO, FDATE, FCUSTNAME,
            FSALEORGNAME, FCUSTGROUP, FREALQTY, FMATERIALNAME, FMATERIALNUMBER,
            FMATERIALTYPE, FMATERIALSORT, FSRCBILLNO, FMODIFYDATE, SYNC_TIME, FDESCRIPTION
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FSEQ = VALUES(FSEQ),
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
            FSRCBILLNO = VALUES(FSRCBILLNO),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            SYNC_TIME = CURRENT_TIMESTAMP,
            FDESCRIPTION = VALUES(FDESCRIPTION)
        """

        return manager._batch_insert(sql, data, manager._prepare_sales_outstock_data)

def insert_delivery_notice(manager, data: List[Dict]) -> int:
        """插入发货通知单数据（SAL_DELIVERYNOTICE）"""
        if not data:
            return 0

        sql = """
        INSERT INTO sal_deliverynotice (
            FID, FENTRYID, FSEQ, FBILLNO, FDATE, FCUSTNAME,
            FMATERIALNAME, FMATERIALNUMBER, FQTY, FSUMOUTQTY, FCLOSESTATUS_MX, FMODIFYDATE,
            FSRCBILLNO, SYNC_TIME
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FSEQ = VALUES(FSEQ),
            FBILLNO = VALUES(FBILLNO),
            FDATE = VALUES(FDATE),
            FCUSTNAME = VALUES(FCUSTNAME),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FQTY = VALUES(FQTY),
            FSUMOUTQTY = VALUES(FSUMOUTQTY),
            FCLOSESTATUS_MX = VALUES(FCLOSESTATUS_MX),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            FSRCBILLNO = VALUES(FSRCBILLNO),
            SYNC_TIME = CURRENT_TIMESTAMP
        """

        return manager._batch_insert(sql, data, manager._prepare_delivery_notice_data)

def insert_forecast_orders(manager, data: List[Dict]) -> int:
        """插入预测订单数据"""
        if not data:
            return 0

        # 检查并添加 F_ORA_DATE、FDescription、FCUSTGROUP 列
        try:
            conn = manager.pool.connection()
            try:
                with conn.cursor() as cursor:
                    is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"
                    table_name = "pln_forecast"

                    # 检查 F_ORA_DATE
                    col_name = "F_ORA_DATE"
                    if is_sqlserver:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                            (table_name, col_name),
                        )
                    else:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                            (table_name, col_name),
                        )

                    if not cursor.fetchone():
                        logger.info(f"正在为 {table_name} 表添加 {col_name} 列...")
                        if is_sqlserver:
                            cursor.execute(f"ALTER TABLE {table_name} ADD {col_name} DATETIME NULL")
                        else:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} DATETIME NULL")
                        conn.commit()

                    # 检查 FDescription
                    col_name = "FDescription"
                    if is_sqlserver:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                            (table_name, col_name),
                        )
                    else:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                            (table_name, col_name),
                        )

                    if not cursor.fetchone():
                        logger.info(f"正在为 {table_name} 表添加 {col_name} 列...")
                        if is_sqlserver:
                            cursor.execute(f"ALTER TABLE {table_name} ADD {col_name} NVARCHAR(2000) NULL")
                        else:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} VARCHAR(2000) NULL")
                        conn.commit()
                    else:
                        # 尝试调整列宽
                        try:
                            if is_sqlserver:
                                cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} NVARCHAR(2000) NULL")
                            else:
                                cursor.execute(f"ALTER TABLE {table_name} MODIFY COLUMN {col_name} VARCHAR(2000) NULL")
                            conn.commit()
                        except Exception:
                            pass

                    col_name = "FCUSTGROUP"
                    if is_sqlserver:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                            (table_name, col_name),
                        )
                    else:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                            (table_name, col_name),
                        )

                    if not cursor.fetchone():
                        logger.info(f"正在为 {table_name} 表添加 {col_name} 列...")
                        if is_sqlserver:
                            cursor.execute(f"ALTER TABLE {table_name} ADD {col_name} NVARCHAR(255) NULL")
                        else:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} VARCHAR(255) NULL")
                        conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"检查/添加列失败: {e}")

        sql = """
        INSERT INTO pln_forecast (
            FENTRYID, FBILLNO, FFOREORGNAME, FCUSTNAME, FCUSTGROUP, FMATERIALNAME, 
            FMATERIALNUMBER, FQTY, FORA_BASE_FNAME, FORA_BASEPROPERTY_CA9, FORA_BASEPROPERTY_UKY, 
            FDATE, FMODIFYDATE, F_ORA_DATE, FDescription
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON DUPLICATE KEY UPDATE
            FBILLNO = VALUES(FBILLNO),
            FFOREORGNAME = VALUES(FFOREORGNAME),
            FCUSTNAME = VALUES(FCUSTNAME),
            FCUSTGROUP = VALUES(FCUSTGROUP),
            FMATERIALNAME = VALUES(FMATERIALNAME),
            FMATERIALNUMBER = VALUES(FMATERIALNUMBER),
            FQTY = VALUES(FQTY),
            FORA_BASE_FNAME = VALUES(FORA_BASE_FNAME),
            FORA_BASEPROPERTY_CA9 = VALUES(FORA_BASEPROPERTY_CA9),
            FORA_BASEPROPERTY_UKY = VALUES(FORA_BASEPROPERTY_UKY),
            FDATE = VALUES(FDATE),
            FMODIFYDATE = VALUES(FMODIFYDATE),
            F_ORA_DATE = VALUES(F_ORA_DATE),
            FDescription = VALUES(FDescription)
        """

        return manager._batch_insert(sql, data, manager._prepare_forecast_order_data)

def insert_purchase_order(manager, data: List[Dict]) -> int:
        """插入采购订单数据（PUR_PurchaseOrder）"""
        if not data:
            return 0
        sql = """
            INSERT INTO PUR_PurchaseOrder (
                FID, FENTRYID, FBillNo, FDocumentStatus, FSupplier, FPurchaseDept, F_ora_Assistant,
                FNUMBER, FNAME, FSpecification, FQTY, FCreateDate, FModifyDate, FApproveDate
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                FBillNo=VALUES(FBillNo),
                FDocumentStatus=VALUES(FDocumentStatus),
                FSupplier=VALUES(FSupplier),
                FPurchaseDept=VALUES(FPurchaseDept),
                F_ora_Assistant=VALUES(F_ora_Assistant),
                FNUMBER=VALUES(FNUMBER),
                FNAME=VALUES(FNAME),
                FSpecification=VALUES(FSpecification),
                FQTY=VALUES(FQTY),
                FCreateDate=VALUES(FCreateDate),
                FModifyDate=VALUES(FModifyDate),
                FApproveDate=VALUES(FApproveDate),
                SYNC_TIME=CURRENT_TIMESTAMP
            """
        return manager._batch_insert(sql, data, manager._prepare_purchase_order_data)

def insert_sub_subreqorder(manager, data: List[Dict]) -> int:
        if not data:
            return 0

        # 检查并添加 FDescription 列
        try:
            conn = manager.pool.connection()
            try:
                with conn.cursor() as cursor:
                    is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"
                    table_name = "sub_subreqorder"
                    col_name = "FDescription"

                    # 检查列是否存在
                    if is_sqlserver:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND COLUMN_NAME=?",
                            (table_name, col_name),
                        )
                    else:
                        cursor.execute(
                            "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=%s AND COLUMN_NAME=%s",
                            (table_name, col_name),
                        )

                    exists = cursor.fetchone() is not None

                    if not exists:
                        logger.info(f"正在为 {table_name} 表添加 {col_name} 列...")
                        if is_sqlserver:
                            cursor.execute(f"ALTER TABLE {table_name} ADD {col_name} NVARCHAR(2000) NULL")
                        else:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} VARCHAR(2000) NULL")
                        conn.commit()
                    else:
                        # 列已存在，尝试扩大长度以避免截断
                        try:
                            if is_sqlserver:
                                cursor.execute(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} NVARCHAR(2000) NULL")
                            else:
                                cursor.execute(f"ALTER TABLE {table_name} MODIFY COLUMN {col_name} VARCHAR(2000) NULL")
                            conn.commit()
                            logger.info(f"已调整 {table_name}.{col_name} 列大小")
                        except Exception:
                            pass
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"检查/添加列失败: {e}")

        sql = """
            INSERT INTO sub_subreqorder (
                FID, FENTRYID, FSrcBillNO, FSRCBILLENTRYSEQ, FSRCBILLENTRYID, FSrcBillId, FBillTypeNAME, FBillNo, FDATE, FCustomer,
                FNUMBER, FQty, FStockInQty, FSupplier, FModifyDate, FDOCUMENTSTATUS, FDescription
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                FSrcBillNO=VALUES(FSrcBillNO),
                FSRCBILLENTRYSEQ=VALUES(FSRCBILLENTRYSEQ),
                FSRCBILLENTRYID=VALUES(FSRCBILLENTRYID),
                FSrcBillId=VALUES(FSrcBillId),
                FBillTypeNAME=VALUES(FBillTypeNAME),
                FBillNo=VALUES(FBillNo),
                FDATE=VALUES(FDATE),
                FCustomer=VALUES(FCustomer),
                FNUMBER=VALUES(FNUMBER),
                FQty=VALUES(FQty),
                FStockInQty=VALUES(FStockInQty),
                FSupplier=VALUES(FSupplier),
                FModifyDate=VALUES(FModifyDate),
                FDOCUMENTSTATUS=VALUES(FDOCUMENTSTATUS),
                FDescription=VALUES(FDescription),
                SYNC_TIME=CURRENT_TIMESTAMP
            """
        return manager._batch_insert(sql, data, manager._prepare_sub_subreqorder_data)

def insert_ap_payable(manager, data: List[Dict]) -> int:
        """
        插入应付单数据

        字段映射:
        FID -> FID
        FEntityDetail_FENTRYID -> FENTRYID
        FEntityDetail_FSEQ -> FSEQ
        FBillTypeID.FNAME -> FBILLNAME
        FBillNo -> FBILLNO
        FDATE -> FDATE
        FPURCHASEORGID.FNAME -> FPURCHASEORGNAME
        F_ora_Base1.FNAME -> FCUSTOMER
        FSUPPLIERID.FNAME -> FSUPPLIERNAME
        FSETACCOUNTTYPE -> FSETACCOUNTTYPE
        FMATERIALID.FNUMBER -> FMATERIALNUMBER
        FMATERIALID.FNAME -> FMATERIALNAME
        FPRICEUNITID.FNAME -> FPRICEUNITNAME
        FPRICEQTY -> FPRICEQTY
        FALLAMOUNTFOR_D -> FALLAMOUNTFOR_D
        FNOTAXAMOUNTFOR -> FNOTAXAMOUNTFOR
        FDISCOUNTAMOUNTFOR -> FDISCOUNTAMOUNTFOR
        FModifyDate -> FModifyDate
        """
        if not data:
            return 0

        try:
            manager._ensure_additional_columns_for_ap_payable()
        except Exception as e:
            logger.warning(f"[AP_Payable] 自动检查/补列失败（可忽略）: {e}")

        sql = """
            INSERT INTO AP_Payable (
                FID, FENTRYID, FSEQ, FBILLNAME, FBILLNO, FDATE, FPURCHASEORGNAME, FCUSTOMER,
                FSUPPLIERNAME, FSETACCOUNTTYPE, FMATERIALNUMBER, FMATERIALNAME, FPRICEUNITNAME,
                FPRICEQTY, FALLAMOUNTFOR_D, FNOTAXAMOUNTFOR, FDISCOUNTAMOUNTFOR, FENTRYDISCOUNTRATE, FENTRYTAXRATE, FModifyDate
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                FID=VALUES(FID),
                FSEQ=VALUES(FSEQ),
                FBILLNAME=VALUES(FBILLNAME),
                FBILLNO=VALUES(FBILLNO),
                FDATE=VALUES(FDATE),
                FPURCHASEORGNAME=VALUES(FPURCHASEORGNAME),
                FCUSTOMER=VALUES(FCUSTOMER),
                FSUPPLIERNAME=VALUES(FSUPPLIERNAME),
                FSETACCOUNTTYPE=VALUES(FSETACCOUNTTYPE),
                FMATERIALNUMBER=VALUES(FMATERIALNUMBER),
                FMATERIALNAME=VALUES(FMATERIALNAME),
                FPRICEUNITNAME=VALUES(FPRICEUNITNAME),
                FPRICEQTY=VALUES(FPRICEQTY),
                FALLAMOUNTFOR_D=VALUES(FALLAMOUNTFOR_D),
                FNOTAXAMOUNTFOR=VALUES(FNOTAXAMOUNTFOR),
                FDISCOUNTAMOUNTFOR=VALUES(FDISCOUNTAMOUNTFOR),
                FENTRYDISCOUNTRATE=VALUES(FENTRYDISCOUNTRATE),
                FENTRYTAXRATE=VALUES(FENTRYTAXRATE),
                FModifyDate=VALUES(FModifyDate),
                SYNC_TIME=CURRENT_TIMESTAMP
        """
        return manager._batch_insert(sql, data, manager._prepare_ap_payable_data)

