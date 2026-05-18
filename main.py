#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdee data sync tool entrypoint.

Supports GUI mode and selected CLI utilities:
    python main.py [gui]
    python main.py sync [options]
    python main.py maintenance [options]
    python main.py check
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

if getattr(sys, "frozen", False):
    project_root = os.path.dirname(sys.executable)
else:
    project_root = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, project_root)

CHECK_COMMANDS = (
    ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
    ("mypy", [sys.executable, "-m", "mypy"]),
    ("unittest", [sys.executable, "-m", "unittest", "discover", "tests", "-v"]),
)


def initialize_dependency_container() -> bool:
    """Initialize DI container lazily for commands that need runtime services."""
    try:
        from src.core.dependency_container import container  # noqa: F401

        return True
    except Exception as exc:  # pragma: no cover - defensive logging path
        logging.getLogger(__name__).warning("Dependency container initialization failed: %s", exc)
        return False


def setup_cli_logging() -> None:
    """Configure lightweight CLI logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def run_gui() -> None:
    """Launch the GUI application."""
    try:
        initialize_dependency_container()
        from src.utils.kingdee_sync_tool import main as gui_main

        gui_main()
    except Exception as exc:
        logging.getLogger(__name__).error("Failed to start GUI: %s", exc, exc_info=True)
        sys.exit(1)


def run_sync(args: argparse.Namespace) -> None:
    """Run a sync task from the CLI."""
    setup_cli_logging()
    logger = logging.getLogger("CLI.Sync")

    try:
        initialize_dependency_container()
        from src.core.data_sync import DataSyncManager, SyncType
        from src.services.sync_service import sync_service

        mode_map = {
            "incremental": SyncType.INCREMENTAL,
            "full": SyncType.FULL,
            "reset": SyncType.COMPLETE,
        }
        sync_type = mode_map.get(args.mode, SyncType.INCREMENTAL)
        repaired = sync_service.repair_stale_sync_runs()
        if repaired:
            logger.warning("Recovered %s stale running sync run(s) before CLI sync", repaired)

        manager = DataSyncManager()
        logger.info(
            "Starting sync: tables=%s, mode=%s",
            args.tables if args.tables else "all",
            args.mode,
        )
        result = manager.sync_data(sync_type=sync_type, form_names=args.tables)
        logger.info("Sync finished: %s", result)
    except Exception as exc:
        logger.error("Sync failed: %s", exc, exc_info=True)
        sys.exit(1)


def run_maintenance(args: argparse.Namespace) -> None:
    """Run maintenance tasks from the CLI."""
    setup_cli_logging()
    logger = logging.getLogger("CLI.Maintenance")

    try:
        initialize_dependency_container()
        if args.action == "archive_logs":
            from src.services.reporting import archive_sync_logs, ensure_sync_logs_indexes

            logger.info("Starting log maintenance...")
            ok_idx = ensure_sync_logs_indexes()
            logger.info("Index creation result: %s", ok_idx)

            ok_arc = archive_sync_logs(days_to_keep=args.days)
            logger.info("Archive result: %s, keep_days=%s", ok_arc, args.days)
    except Exception as exc:
        logger.error("Maintenance task failed: %s", exc, exc_info=True)
        sys.exit(1)


def run_check(_args: argparse.Namespace) -> None:
    """Run the repo quality gates defined in pyproject.toml."""
    setup_cli_logging()
    logger = logging.getLogger("CLI.Check")

    for tool_name, cmd in CHECK_COMMANDS:
        logger.info("Running %s: %s", tool_name, " ".join(cmd))
        exit_code = subprocess.call(cmd, cwd=project_root)
        if exit_code != 0:
            logger.error("%s failed with exit code %s", tool_name, exit_code)
            sys.exit(exit_code)

    logger.info("Checks completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kingdee data sync tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("gui", help="Launch GUI mode")

    sync_parser = subparsers.add_parser("sync", help="Run data sync")
    sync_parser.add_argument("--tables", nargs="+", help="Specific forms to sync")
    sync_parser.add_argument(
        "--mode",
        choices=["incremental", "full", "reset"],
        default="incremental",
        help="Sync mode",
    )

    maint_parser = subparsers.add_parser("maintenance", help="Run maintenance tasks")
    maint_parser.add_argument(
        "--action",
        choices=["archive_logs"],
        required=True,
        help="Maintenance action",
    )
    maint_parser.add_argument(
        "--days",
        type=int,
        default=180,
        help="Days of logs to retain",
    )

    subparsers.add_parser("check", help="Run lint and type checks")

    if len(sys.argv) == 1:
        run_gui()
        return

    args = parser.parse_args()
    if args.command == "gui":
        run_gui()
    elif args.command == "sync":
        run_sync(args)
    elif args.command == "maintenance":
        run_maintenance(args)
    elif args.command == "check":
        run_check(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
