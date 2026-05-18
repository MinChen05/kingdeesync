"""
科目余额表同步模块
支持按月逐个同步，并写入会计年度和期间字段
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from src.core.kingdee_api import kingdee_client
from src.core.mysql_manager import mysql_manager
from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


class AccountBalanceSyncManager:
    """科目余额表同步管理器"""

    # 科目余额表表名
    TABLE_NAME = "GL_RPT_AccountBalance"
    FORM_NAME = "科目余额表"

    def __init__(self):
        self._is_cancelled = False

    @staticmethod
    def _parse_amount(value: Any) -> float:
        """Parse Kingdee report amount strings, including values with thousands separators."""
        if value is None or value == "":
            return 0
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return 0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0

    def sync_by_month(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        truncate_before_sync: bool = True,
        progress_callback: Optional[callable] = None,
        db_manager=None,
    ) -> Dict[str, Any]:
        """
        按月同步科目余额表

        Args:
            start_year: 起始年份
            start_month: 起始月份
            end_year: 结束年份
            end_month: 结束月份
            truncate_before_sync: 是否在同步前清空表
            progress_callback: 进度回调函数

        Returns:
            同步结果
        """
        self._is_cancelled = False
        start_time = datetime.now()
        total_records = 0
        failed_periods = []
        success_periods = []

        logger.info(f"开始按月同步科目余额表: {start_year}.{start_month:02d} - {end_year}.{end_month:02d}")

        # 检查连接
        if not self._check_connections(db_manager=db_manager):
            return self._create_result("failed", "连接检查失败", 0, start_time)

        # 清空表（如果需要）
        if truncate_before_sync:
            if progress_callback:
                progress_callback("正在清空科目余额表...", 0)
            if not self._truncate_table(db_manager=db_manager):
                return self._create_result("failed", "清空表失败", 0, start_time)

        # 生成月份列表
        months = self._generate_month_list(start_year, start_month, end_year, end_month)
        total_months = len(months)
        empty_periods = []

        for idx, (year, month) in enumerate(months):
            if self._is_cancelled:
                logger.info("同步已取消")
                break

            # 计算进度
            progress = int((idx / total_months) * 100)
            if progress_callback:
                progress_callback(f"正在同步 {year}年{month:02d}月...", progress)

            try:
                # 同步单个月份
                records = self._sync_single_month(year, month, db_manager=db_manager)
                if records > 0:
                    total_records += records
                    success_periods.append(f"{year}.{month:02d}")
                    logger.info(f"同步 {year}年{month:02d}月 完成，共 {records} 条记录")
                else:
                    empty_periods.append(f"{year}.{month:02d}")
                    logger.info(f"{year}年{month:02d}月 无数据，跳过")

            except Exception as e:
                logger.error(f"同步 {year}年{month:02d}月 失败: {e}")
                failed_periods.append(f"{year}.{month:02d}")

        # 构建结果
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if not failed_periods:
            if total_records > 0:
                status = "success"
                message = f"同步完成，共 {total_records} 条记录，{len(empty_periods)}个月无数据"
            else:
                status = "success"
                message = "同步完成，所有月份均无数据"
        elif not success_periods:
            status = "failed"
            message = f"所有月份同步失败: {', '.join(failed_periods)}"
        else:
            status = "partial"
            message = (
                f"部分完成，成功{len(success_periods)}个月，失败{len(failed_periods)}个月: {', '.join(failed_periods)}"
            )

        result = self._create_result(status, message, total_records, start_time)
        result["duration"] = duration
        result["success_periods"] = success_periods
        result["failed_periods"] = failed_periods

        if progress_callback:
            progress_callback(message, 100)

        return result

    def _sync_single_month(self, year: int, month: int, db_manager=None) -> int:
        """
        同步单个月份的数据

        Args:
            year: 年份
            month: 月份

        Returns:
            同步的记录数
        """
        # 获取查询配置
        query_config = config_manager.get_form_queries().get(self.FORM_NAME, {})
        if not query_config:
            raise Exception(f"未找到 {self.FORM_NAME} 的查询配置")

        # 构建查询参数（动态设置期间）
        query_params = self._build_query_params(query_config, year, month)

        # 查询数据
        logger.info(f"正在查询 {year}年{month:02d}月 科目余额数据...")
        logger.debug(f"查询参数: {query_params}")

        data = kingdee_client.query_data(self.TABLE_NAME, query_params)

        if data is None:
            logger.warning(f"查询 {year}年{month:02d}月 数据返回None，可能无数据")
            return 0

        if not data:
            logger.info(f"{year}年{month:02d}月 无数据")
            return 0

        logger.info(f"查询到 {year}年{month:02d}月 数据 {len(data)} 条")
        logger.debug(f"第一条数据样例: {data[0] if data else 'N/A'}")

        # 添加会计年度和期间字段
        for row in data:
            row["FACCTYEAR"] = year
            row["FACCTPERIOD"] = month

        # 插入数据库
        logger.info(f"正在插入 {year}年{month:02d}月 数据，共 {len(data)} 条...")
        inserted = self._insert_data(data, db_manager=db_manager)
        logger.info(f"成功插入 {year}年{month:02d}月 数据 {inserted} 条")

        return inserted

    def _build_query_params(self, query_config: Dict, year: int, month: int) -> Dict:
        """
        构建查询参数

        Args:
            query_config: 基础配置
            year: 年份
            month: 月份

        Returns:
            查询参数
        """
        params = {
            "FormId": query_config.get("FormId", "GL_RPT_AccountBalance"),
            "FieldKeys": query_config.get("FieldKeys", ""),
            "FilterString": query_config.get("FilterString", []),
            "StartRow": 0,
            "Limit": 0,
        }

        # 构建Model参数（动态设置期间）
        model = query_config.get("Model", {}).copy()
        model["FSTARTYEAR"] = str(year)
        model["FSTARTPERIOD"] = str(month)
        model["FENDYEAR"] = str(year)
        model["FENDPERIOD"] = str(month)

        params["Model"] = model

        return params

    def _insert_data(self, data: List[Dict], db_manager=None) -> int:
        """
        插入数据到数据库

        Args:
            data: 数据列表

        Returns:
            插入的记录数
        """
        if not data:
            return 0

        manager = db_manager or mysql_manager

        try:
            # 确保数据库连接
            if not getattr(manager, "connection", None):
                manager.connect()

            # 构建插入SQL
            columns = [
                "FBALANCEID",
                "FBALANCENAME",
                "FDETAILNUMBER",
                "FDETAILNAME",
                "FBEGINYEARDEBITLOCAL",
                "FBEGINYEARCREDITLOCAL",
                "FBEGINDEBIT",
                "FBEGINDEBITLOCAL",
                "FBEGINCREDIT",
                "FBEGINCREDITLOCAL",
                "FDEBIT",
                "FDEBITLOCAL",
                "FCREDIT",
                "FCREDITLOCAL",
                "FYTDDEBIT",
                "FYTDDEBITLOCAL",
                "FYTDCREDIT",
                "FYTDCREDITLOCAL",
                "FENDDEBIT",
                "FENDDEBITLOCAL",
                "FENDCREDIT",
                "FENDCREDITLOCAL",
                "FPROFITLOCAL",
                "FYTDPROFITLOCAL",
                "FACCTYEAR",
                "FACCTPERIOD",  # 会计期间字段
            ]

            is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"

            if is_sqlserver:
                placeholders = ", ".join(["?" for _ in columns])
                sql = f"INSERT INTO {self.TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders})"
            else:
                placeholders = ", ".join(["%s" for _ in columns])
                sql = f"INSERT INTO {self.TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders})"

            # 准备数据
            values_list = []
            for row in data:
                values = []
                for col in columns:
                    val = row.get(col)
                    # 处理空值和数值类型
                    if val is None:
                        values.append(None)
                    elif col in ["FACCTYEAR", "FACCTPERIOD"]:
                        values.append(int(val) if val else None)
                    elif col.startswith("F") and col not in [
                        "FBALANCEID",
                        "FBALANCENAME",
                        "FDETAILNUMBER",
                        "FDETAILNAME",
                    ]:
                        # 金蝶报表金额可能带千分位逗号，例如 "1,208.85"。
                        values.append(self._parse_amount(val))
                    else:
                        values.append(str(val) if val else "")
                values_list.append(tuple(values))

            # 批量插入
            if values_list:
                manager.cursor.executemany(sql, values_list)
                manager.connection.commit()
                return len(values_list)

            return 0

        except Exception as e:
            logger.error(f"插入科目余额数据失败: {e}")
            if getattr(manager, "connection", None):
                try:
                    manager.connection.rollback()
                except Exception:
                    pass
            raise

    def _truncate_table(self, db_manager=None) -> bool:
        """清空表"""
        manager = db_manager or mysql_manager
        try:
            if not getattr(manager, "connection", None):
                manager.connect()

            is_sqlserver = getattr(manager, "db_type", "mysql") == "sqlserver"

            if is_sqlserver:
                sql = f"TRUNCATE TABLE {self.TABLE_NAME}"
            else:
                sql = f"TRUNCATE TABLE {self.TABLE_NAME}"

            manager.cursor.execute(sql)
            manager.connection.commit()
            logger.info(f"已清空表 {self.TABLE_NAME}")
            return True

        except Exception as e:
            logger.error(f"清空表失败: {e}")
            return False

    def _check_connections(self, db_manager=None) -> bool:
        """检查连接"""
        manager = db_manager or mysql_manager

        # 检查金蝶连接
        if not kingdee_client.test_connection():
            logger.error("金蝶API连接失败")
            return False

        # 检查数据库连接
        if not manager.test_connection():
            logger.error("数据库连接失败")
            return False

        return True

    def _generate_month_list(
        self, start_year: int, start_month: int, end_year: int, end_month: int
    ) -> List[Tuple[int, int]]:
        """生成月份列表"""
        months = []
        year = start_year
        month = start_month

        while year < end_year or (year == end_year and month <= end_month):
            months.append((year, month))
            month += 1
            if month > 12:
                month = 1
                year += 1

        return months

    def _create_result(self, status: str, message: str, records: int, start_time: datetime) -> Dict[str, Any]:
        """创建结果字典"""
        return {
            "status": status,
            "message": message,
            "total_records": records,
            "start_time": start_time,
            "end_time": datetime.now(),
            "duration": (datetime.now() - start_time).total_seconds(),
            "details": {},
        }

    def cancel(self):
        """取消同步"""
        self._is_cancelled = True


# 全局实例
account_balance_sync_manager = AccountBalanceSyncManager()
