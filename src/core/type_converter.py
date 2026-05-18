"""SQL Server type conversion utilities for safe data type handling."""

from typing import Any, Dict, List, Optional, Tuple


class TypeConverter:
    """Handles SQL Server type conversions to prevent type mismatch errors."""

    INT_TYPES = {"int", "bigint", "smallint", "tinyint"}
    DEC_TYPES = {"numeric", "decimal", "float", "real", "money", "smallmoney"}
    DT_TYPES = {"datetime", "datetime2", "smalldatetime", "date", "time"}
    TEXT_TYPES = {"nvarchar", "varchar", "nchar", "char"}

    def __init__(self, cursor):
        self.cursor = cursor

    def get_column_type_map(self, table_name: str) -> dict[str, tuple[str, int | None]]:
        """获取表的列类型映射"""
        col_type_map = {}
        try:
            self.cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
                """,
                (table_name,),
            )
            rows = self.cursor.fetchall() or []
            for r in rows:
                if isinstance(r, dict):
                    name = r.get("COLUMN_NAME")
                    dtype = r.get("DATA_TYPE")
                    max_len = r.get("CHARACTER_MAXIMUM_LENGTH")
                else:
                    name = r[0] if len(r) > 0 else None
                    dtype = r[1] if len(r) > 1 else None
                    max_len = r[2] if len(r) > 2 else None
                if name:
                    col_type_map[str(name).upper()] = (
                        str(dtype).lower() if dtype is not None else "",
                        max_len,
                    )
        except Exception:
            col_type_map = {}
        return col_type_map

    def build_source_conversion_parts(
        self, columns: list[str], col_type_map: dict[str, tuple[str, int | None]]
    ) -> list[str]:
        """构建类型安全的源数据转换表达式"""
        source_parts = []
        for c in columns:
            c_up = str(c).strip().upper()
            dtype, max_len = col_type_map.get(c_up, ("", None))

            if dtype in self.INT_TYPES:
                source_parts.append(f"COALESCE(TRY_CONVERT(BIGINT, CONVERT(NVARCHAR(64), ?)), 0) AS {c}")
            elif dtype in self.DEC_TYPES:
                source_parts.append(f"COALESCE(TRY_CONVERT(DECIMAL(23,10), CONVERT(NVARCHAR(64), ?)), 0) AS {c}")
            elif dtype in self.DT_TYPES:
                source_parts.append(f"TRY_CONVERT(DATETIME, ?) AS {c}")
            elif dtype in self.TEXT_TYPES:
                if max_len == -1:
                    cast_type = f"{dtype.upper()}(MAX)"
                elif max_len is not None and int(max_len) > 0:
                    cast_type = f"{dtype.upper()}({int(max_len)})"
                else:
                    cast_type = f"{dtype.upper()}(255)"
                source_parts.append(f"TRY_CONVERT({cast_type}, ?) AS {c}")
            else:
                source_parts.append(f"TRY_CONVERT(NVARCHAR(255), ?) AS {c}")

        return source_parts
