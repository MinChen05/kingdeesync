"""Service-layer facade for GUI settings operations."""

from __future__ import annotations

import logging
import os
from typing import Any

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
    def get_settings_snapshot() -> dict[str, dict[str, Any]]:
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

    def save_settings(self, payload: dict[str, dict[str, Any]]) -> None:
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

    @staticmethod
    def _runtime_configs_from_payload(payload: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        kd_current = config_manager.get_kingdee_config()
        db_current = config_manager.get_db_config()
        sql_current = dict(db_current.get("sqlserver", {}))

        kd_payload = payload.get("kingdee", {})
        db_payload = payload.get("database", {})

        kd_config = dict(kd_current)
        for key in ("login_url", "query_url", "acct_id", "username"):
            if key in kd_payload:
                kd_config[key] = str(kd_payload.get(key, "")).strip()
        password = str(kd_payload.get("password", "")).strip()
        if password:
            kd_config["password"] = password

        sql_config = dict(sql_current)
        for key in ("host", "database", "user"):
            if key in db_payload:
                sql_config[key] = str(db_payload.get(key, "")).strip()
        if "port" in db_payload:
            sql_config["port"] = str(db_payload.get("port", 1433)).strip()
        db_password = str(db_payload.get("password", "")).strip()
        if db_password:
            sql_config["password"] = db_password

        return kd_config, sql_config

    def apply_runtime_payload(self, payload: dict[str, dict[str, Any]]) -> None:
        kd_config, sql_config = self._runtime_configs_from_payload(payload)
        kingdee_client.config = kd_config
        kingdee_client.is_authenticated = False
        kingdee_client.session_id = None

        if mysql_manager.pool or mysql_manager.connection:
            mysql_manager.disconnect()
        mysql_manager.db_type = "sqlserver"
        mysql_manager.config = sql_config
        mysql_manager.pool = None
        mysql_manager._pool_init_failed = False
        mysql_manager._init_pool()

    def test_connections(
        self,
        payload: dict[str, dict[str, Any]] | None = None,
        *,
        persist: bool = True,
    ) -> tuple[bool, bool, str]:
        if payload is not None and persist:
            self.save_settings(payload)
            self.refresh_runtime_clients()
        elif payload is not None:
            self.apply_runtime_payload(payload)
        else:
            self.refresh_runtime_clients()

        try:
            kd_ok = bool(kingdee_client.test_connection())
            db_ok = bool(mysql_manager.test_connection())
        finally:
            if payload is not None and not persist:
                self.refresh_runtime_clients()

        message = f"金蝶: {'成功' if kd_ok else '失败'}\n数据库: {'成功' if db_ok else '失败'}"
        return kd_ok, db_ok, message


settings_service = SettingsService()
