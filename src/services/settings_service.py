"""Service-layer facade for GUI settings operations."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from src.config.config_manager import config_manager
from src.core.kingdee_api import kingdee_client
from src.core.mysql_manager import mysql_manager

logger = logging.getLogger(__name__)


class SettingsService:
    """Encapsulate settings load/save/test behavior for the GUI layer."""

    @staticmethod
    def get_config_source() -> str:
        return config_manager.config_file

    @staticmethod
    def get_config_source_name() -> str:
        return os.path.basename(config_manager.config_file)

    @staticmethod
    def get_database_type() -> str:
        return str(config_manager.get_db_config().get("type", "sqlserver")).strip().upper()

    @staticmethod
    def get_settings_snapshot() -> Dict[str, Dict[str, Any]]:
        return {
            "kingdee": config_manager.get_kingdee_config(),
            "database": config_manager.get_db_config().get("sqlserver", {}),
        }

    @staticmethod
    def _ensure_sections() -> None:
        if "KINGDEE" not in config_manager.config:
            config_manager.config["KINGDEE"] = {}
        if "DATABASE" not in config_manager.config:
            config_manager.config["DATABASE"] = {}
        if "SQLSERVER" not in config_manager.config:
            config_manager.config["SQLSERVER"] = {}

    def save_settings(self, payload: Dict[str, Dict[str, Any]]) -> None:
        self._ensure_sections()

        kingdee_payload = payload.get("kingdee", {})
        kd_cfg = config_manager.config["KINGDEE"]
        kd_cfg["login_url"] = str(kingdee_payload.get("login_url", "")).strip()
        kd_cfg["query_url"] = str(kingdee_payload.get("query_url", "")).strip()
        kd_cfg["acct_id"] = str(kingdee_payload.get("acct_id", "")).strip()
        kd_cfg["username"] = str(kingdee_payload.get("username", "")).strip()

        password = str(kingdee_payload.get("password", "")).strip()
        if password:
            kd_cfg["password"] = password

        config_manager.config["DATABASE"]["type"] = "sqlserver"

        db_payload = payload.get("database", {})
        db_cfg = config_manager.config["SQLSERVER"]
        db_cfg["host"] = str(db_payload.get("host", "")).strip()
        db_cfg["port"] = str(db_payload.get("port", 1433)).strip()
        db_cfg["database"] = str(db_payload.get("database", "")).strip()
        db_cfg["user"] = str(db_payload.get("user", "")).strip()

        db_password = str(db_payload.get("password", "")).strip()
        if db_password:
            db_cfg["password"] = db_password

        config_manager.save_config()

    @staticmethod
    def refresh_runtime_clients() -> None:
        kingdee_client.config = config_manager.get_kingdee_config()
        mysql_manager.reload_config()

    def test_connections(self, payload: Dict[str, Dict[str, Any]] | None = None) -> tuple[bool, bool, str]:
        if payload is not None:
            self.save_settings(payload)

        self.refresh_runtime_clients()

        kd_ok = bool(kingdee_client.test_connection())
        db_ok = bool(mysql_manager.test_connection())

        message = f"金蝶: {'成功' if kd_ok else '失败'}\n数据库: {'成功' if db_ok else '失败'}"
        return kd_ok, db_ok, message


settings_service = SettingsService()
