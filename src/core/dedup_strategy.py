"""Deduplication strategies for SQL Server data synchronization."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeduplicationStrategy:
    """Handles source data deduplication to prevent MERGE conflicts."""

    def __init__(self, manager):
        self.manager = manager

    def deduplicate_by_primary_key(
        self,
        values: list[list[Any]],
        columns: list[str],
        table: str,
        enabled: bool = True,
    ) -> list[list[Any]]:
        """按主键对源数据进行去重，避免 MERGE 8672 错误"""
        if not enabled or not values:
            return values

        try:
            pk_raw = self.manager._get_primary_key(table) or columns[0]
            pk_cols = (
                [c.strip() for c in pk_raw.split(",")]
                if (isinstance(pk_raw, str) and "," in pk_raw)
                else [pk_raw]
            )

            # 找到主键列索引
            pk_indices = []
            for pkc in pk_cols:
                idx = None
                for i, c in enumerate(columns):
                    if str(c).strip().upper() == str(pkc).strip().upper():
                        idx = i
                        break
                if idx is not None:
                    pk_indices.append(idx)

            if not pk_indices:
                return values

            original_count = len(values)
            dedup_map = {}
            duplicate_counter = 0
            invalid_pk_counter = 0

            for row in values:
                try:
                    key_tuple = (
                        tuple([self.manager._hashable_key(row[i]) for i in pk_indices])
                        if len(pk_indices) > 1
                        else (self.manager._hashable_key(row[pk_indices[0]]),)
                    )
                except Exception:
                    key_tuple = ()

                invalid_pk = False
                try:
                    if any((kv is None) or (str(kv).strip() == "") for kv in key_tuple):
                        invalid_pk = True
                except Exception:
                    invalid_pk = True

                if invalid_pk:
                    invalid_pk_counter += 1
                    continue

                if key_tuple in dedup_map:
                    duplicate_counter += 1
                dedup_map[key_tuple] = row

            deduplicated = list(dedup_map.values())
            if len(deduplicated) < original_count:
                logger.info(
                    f"[DEDUP] 基于主键 {pk_cols} 去重：{original_count} -> {len(deduplicated)} "
                    f"（表 {table}），重复 {duplicate_counter}，无效主键 {invalid_pk_counter}"
                )
            return deduplicated

        except Exception as e:
            logger.warning(f"[DEDUP] 基于主键去重过程异常（表 {table}）：{e}")
            return values

    def deduplicate_by_column(
        self,
        values: list[list[Any]],
        columns: list[str],
        column_name: str,
        table: str,
    ) -> list[list[Any]]:
        """按指定列去重"""
        if not values:
            return values

        try:
            col_idx = None
            for idx, col in enumerate(columns):
                if str(col).strip().upper() == column_name.upper():
                    col_idx = idx
                    break

            if col_idx is None:
                return values

            original_count = len(values)
            dedup_map: dict[str, list[Any]] = {}

            for row in values:
                key = row[col_idx]
                key_str = None if key is None else str(key).strip()
                # 将空/缺失值视为同一键，避免空值重复
                if not key_str:
                    key_str = ""
                # 后出现的记录覆盖先前，确保以最新数据为准
                dedup_map[key_str] = row

            deduplicated = list(dedup_map.values())
            if len(deduplicated) < original_count:
                logger.info(
                    f"[DEDUP] {table} 的 {column_name} 去重：{original_count} -> {len(deduplicated)}"
                )
            return deduplicated

        except Exception as e:
            logger.warning(f"[DEDUP] {table} 去重过程异常：{e}")
            return values

    def filter_required_fields(
        self,
        values: list[list[Any]],
        columns: list[str],
        required_columns: list[str],
        table: str,
    ) -> list[list[Any]]:
        """过滤必填字段为空的行"""
        if not values or not required_columns:
            return values

        try:
            required_indices = []
            for rc in required_columns:
                idx = None
                for i, c in enumerate(columns):
                    if str(c).strip().upper() == rc.upper():
                        idx = i
                        break
                if idx is not None:
                    required_indices.append(idx)

            if not required_indices:
                return values

            filtered = []
            invalid_required = 0

            for row in values:
                try:
                    if any((row[i] is None) or (str(row[i]).strip() == "") for i in required_indices):
                        invalid_required += 1
                        continue
                except Exception:
                    invalid_required += 1
                    continue
                filtered.append(row)

            if invalid_required > 0:
                logger.warning(f"[{table}] 必填字段为空已跳过: {invalid_required} 条")

            return filtered

        except Exception:
            return values
