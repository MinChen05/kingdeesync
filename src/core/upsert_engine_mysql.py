"""MySQL upsert engine extracted from MySQLManager batch insert logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from src.core.mysql_manager import MySQLManager


class UpsertEngineMySQL:
    """Encapsulates MySQL-specific batch insert/upsert behavior."""

    def __init__(self, manager: "MySQLManager", *, logger: logging.Logger | None = None) -> None:
        self.manager = manager
        self.logger = logger or logging.getLogger(__name__)

    def execute(self, sql: str, values: List[List[Any]], batch_size: int) -> int:
        manager = self.manager
        logger = self.logger
        total_inserted = 0

        try:
            manager.cursor.execute("BEGIN")
            for i in range(0, len(values), batch_size):
                batch = values[i : i + batch_size]
                logger.info(
                    "处理批次 %s/%s，记录数: %s",
                    i // batch_size + 1,
                    (len(values) - 1) // batch_size + 1,
                    len(batch),
                )
                manager.cursor.executemany(sql, batch)
                total_inserted += len(batch)
                manager.cursor.execute("COMMIT")
                manager.cursor.execute("BEGIN")
                logger.debug("已提交批次 %s，累计插入 %s", i // batch_size + 1, total_inserted)

            manager.cursor.execute("COMMIT")
            logger.info("成功插入 %s 条记录", total_inserted)
            return total_inserted
        except Exception as exc:
            try:
                manager.cursor.execute("ROLLBACK")
            except Exception:
                pass
            logger.error("批量插入过程中发生错误，已回滚: %s", exc)
            raise
