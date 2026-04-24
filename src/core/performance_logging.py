from __future__ import annotations

import logging


def log_prepare_metrics(
    logger: logging.Logger,
    *,
    table_name: str,
    source_rows: int,
    prepared_rows: int,
    duration_seconds: float,
) -> None:
    logger.info(
        f"[PERF][{table_name}] prepare "
        f"source={int(source_rows)} valid={int(prepared_rows)} seconds={float(duration_seconds):.3f}"
    )


def log_write_metrics(
    logger: logging.Logger,
    *,
    table_name: str,
    batch_index: int,
    total_batches: int,
    row_count: int,
    exec_seconds: float,
    commit_seconds: float,
) -> None:
    total_seconds = float(exec_seconds) + float(commit_seconds)
    logger.info(
        f"[PERF][{table_name}] batch {int(batch_index)}/{int(total_batches)} "
        f"rows={int(row_count)} executemany={float(exec_seconds):.3f} "
        f"commit={float(commit_seconds):.3f} total={total_seconds:.3f}"
    )
