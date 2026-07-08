"""Query filter construction for form sync workflows."""

from __future__ import annotations

import logging
from typing import Optional

from src.config.config_manager import config_manager
from src.core.mysql_manager import mysql_manager

logger = logging.getLogger(__name__)


class FilterBuilder:
    """Builds Kingdee query filters for incremental/full/complete sync."""

    def __init__(self, *, logger_: logging.Logger | None = None) -> None:
        self.logger = logger_ or logger

    @staticmethod
    def _sync_type_value(sync_type) -> str:
        return str(getattr(sync_type, "value", sync_type or "")).lower()

    def build_filter_string(
        self,
        form_name: str,
        sync_type,
        table_name: str,
        db_manager=None,
    ) -> Optional[str]:
        """Build the filter string for a form sync request."""
        manager = db_manager or mysql_manager
        base_queries = config_manager.get_form_queries()
        form_config = base_queries.get(form_name, {})
        base_filter = form_config.get("FilterString", "")
        field_keys = form_config.get("FieldKeys", "")

        modify_field = None

        if form_name != "即时库存":
            persisted = config_manager.get_increment_field(table_name) or config_manager.get_increment_field(form_name)
            if persisted:
                modify_field = persisted
            else:
                modify_field = "FModifyDate"
                candidates = [
                    "FModifyDate",
                    "FMODIFYDATE",
                    "FLastUpdateTime",
                    "FLASTUPDATETIME",
                    "FLastUpdateDate",
                    "FLASTUPDATEDATE",
                    "FInventoryDate",
                    "FINVENTORYDATE",
                    "FInventoryTime",
                    "FINVENTORYTIME",
                    "FUpdateTime",
                    "FUPDATE_TIME",
                    "FUpdateDate",
                    "FUPDATEDATE",
                    "FUPDATETIME",
                ]
                try:
                    keys = [k.strip().split(".")[-1] for k in field_keys.split(",") if k.strip()]
                    for candidate in candidates:
                        if candidate in keys:
                            modify_field = candidate
                            break
                except Exception:
                    pass

            if modify_field and not persisted:
                try:
                    config_manager.set_increment_field(table_name, modify_field)
                except Exception:
                    pass

        sync_type_value = self._sync_type_value(sync_type)
        if sync_type_value == "incremental":
            if form_name == "即时库存":
                self.logger.info("[%s] 使用当前库存快照同步，跳过增量时间过滤", form_name)
                return base_filter

            last_time = manager.get_last_modify_time(table_name)
            if last_time and modify_field:
                if isinstance(last_time, str):
                    time_value = last_time
                elif hasattr(last_time, "strftime"):
                    time_value = last_time.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_value = str(last_time)

                time_expr = f"{modify_field} > '{time_value}'"
                if base_filter and base_filter.strip():
                    return f"{base_filter} and {time_expr}"
                return time_expr

            self.logger.info("[%s] 未找到上次同步时间，将退化为全量查询", form_name)
            return base_filter

        if sync_type_value in {"full", "complete"}:
            return base_filter

        return base_filter
