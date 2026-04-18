"""
Business-facing config accessors and JSON-backed config helpers.
"""

from __future__ import annotations

import configparser
import copy
import json
import logging
import os
from typing import Any, Dict

from src.config.config_reader import ConfigReader


def load_tables_json(config_file: str, logger: logging.Logger) -> Dict[str, Any]:
    """Load tables.json from runtime-aware candidate paths."""
    try:
        config_dir = os.path.dirname(os.path.abspath(config_file))
        mapping_file = os.path.join(config_dir, "tables.json")

        if not os.path.exists(mapping_file):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            mapping_file = os.path.join(base_dir, "config", "tables.json")

        if os.path.exists(mapping_file):
            with open(mapping_file, "r", encoding="utf-8") as fp:
                return json.load(fp)
    except Exception as err:
        logger.error("Error loading tables.json: %s", err)

    return {}


def resolve_form_queries_candidates(config_file: str) -> list[str]:
    """Build form-queries.json candidate paths."""
    config_dir = os.path.dirname(os.path.abspath(config_file))
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(base_dir)

    return [
        os.path.join(config_dir, "form-queries.json"),
        os.path.join(config_dir, "src", "config", "form-queries.json"),
        os.path.join(config_dir, "dotnet", "form-queries.json"),
        os.path.join(base_dir, "config", "form-queries.json"),
        os.path.join(root_dir, "dotnet", "form-queries.json"),
    ]


def load_form_queries_json(config_file: str, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    """Load form-queries.json with fallback candidates."""
    for file_path in resolve_form_queries_candidates(config_file):
        try:
            if not os.path.exists(file_path):
                continue

            with open(file_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)

            if isinstance(data, dict):
                return data
        except Exception as err:
            logger.warning("Failed to load form-queries.json: %s - %s", file_path, err)

    logger.error("No usable form-queries.json was found; returning empty config")
    return {}


def _as_bool(value: Any, default: bool) -> bool:
    try:
        return str(value).strip().lower() == "true"
    except Exception:
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


class ConfigAccessors:
    """Parses raw config data into business-facing views."""

    def __init__(self, reader: ConfigReader, *, logger: logging.Logger | None = None) -> None:
        self.reader = reader
        self.logger = logger or logging.getLogger(__name__)

    @property
    def config(self) -> configparser.ConfigParser:
        return self.reader.config

    @property
    def config_file(self) -> str:
        return self.reader.config_file

    def _load_tables_json(self) -> Dict[str, Any]:
        return load_tables_json(self.config_file, self.logger)

    def _load_form_queries_json(self) -> Dict[str, Dict[str, Any]]:
        return load_form_queries_json(self.config_file, self.logger)

    def get_table_mapping(self) -> Dict[str, str]:
        raw = self._load_tables_json()
        if not raw:
            return {}

        result: Dict[str, str] = {}
        for form_name, val in raw.items():
            if isinstance(val, dict):
                result[form_name] = val.get("table", "")
            else:
                result[form_name] = str(val)
        return result

    def get_insert_method_map(self) -> Dict[str, str]:
        raw = self._load_tables_json()
        result: Dict[str, str] = {}
        for form_name, val in raw.items():
            if not isinstance(val, dict):
                continue
            method = val.get("insert_method")
            if method:
                result[form_name] = method
        return result

    def get_kingdee_config(self) -> Dict[str, Any]:
        if "KINGDEE" not in self.config:
            self.reader.create_default()

        cfg: Dict[str, Any] = dict(self.config["KINGDEE"])
        cfg["pagination_enabled"] = _as_bool(cfg.get("pagination_enabled", "false"), False)
        cfg["request_timeout"] = _as_int(cfg.get("request_timeout", "0"), 0)
        cfg["page_size"] = _as_int(cfg.get("page_size", "50000"), 50000)
        cfg["max_pages"] = _as_int(cfg.get("max_pages", "100000"), 100000)
        cfg["rate_limit_qps"] = _as_float(cfg.get("rate_limit_qps", "2"), 2.0)
        cfg["keep_session_alive"] = _as_bool(cfg.get("keep_session_alive", "true"), True)
        cfg["keep_alive_interval_secs"] = _as_int(cfg.get("keep_alive_interval_secs", "600"), 600)
        cfg["auto_logout_on_exit"] = _as_bool(cfg.get("auto_logout_on_exit", "false"), False)
        return cfg

    def get_mysql_config(self) -> Dict[str, str]:
        return dict(self.config["MYSQL"])

    def get_db_config(self) -> Dict[str, Any]:
        db_type = "mysql"
        try:
            if "DATABASE" in self.config and "type" in self.config["DATABASE"]:
                db_type = self.config["DATABASE"]["type"].strip().lower()
            elif "DB" in self.config and "type" in self.config["DB"]:
                db_type = self.config["DB"]["type"].strip().lower()
        except Exception:
            db_type = "mysql"

        mysql_cfg: Dict[str, str] = {}
        try:
            mysql_cfg = self.get_mysql_config()
        except Exception:
            mysql_cfg = {
                "host": "127.0.0.1",
                "user": "root",
                "password": "",
                "database": "kingdee",
                "charset": "utf8mb4",
                "port": "3306",
            }

        sqlserver_cfg: Dict[str, str] = {}
        try:
            if "SQLSERVER" in self.config:
                sqlserver_cfg = dict(self.config["SQLSERVER"])
            else:
                sqlserver_cfg = {
                    "host": "127.0.0.1",
                    "user": "sa",
                    "password": "your_password",
                    "database": "kingdee",
                    "port": "1433",
                    "driver": "ODBC Driver 17 for SQL Server",
                }
        except Exception:
            sqlserver_cfg = {
                "host": "127.0.0.1",
                "user": "sa",
                "password": "your_password",
                "database": "kingdee",
                "port": "1433",
                "driver": "ODBC Driver 17 for SQL Server",
            }

        return {"type": db_type, "mysql": mysql_cfg, "sqlserver": sqlserver_cfg}

    def get_sync_config(self) -> Dict[str, Any]:
        sync_config: Dict[str, Any] = dict(self.config["SYNC"])
        sync_config["auto_sync"] = _as_bool(sync_config["auto_sync"], False)
        sync_config["sync_interval"] = _as_int(sync_config["sync_interval"], 60)

        fetch_concurrency = _as_int(sync_config.get("fetch_concurrency", "1"), 1)
        sync_config["fetch_concurrency"] = max(1, min(fetch_concurrency, 8))

        table_concurrency = _as_int(
            sync_config.get("table_concurrency", sync_config.get("fetch_concurrency", "1")),
            sync_config["fetch_concurrency"],
        )
        sync_config["table_concurrency"] = max(1, min(table_concurrency, 8))

        time_window_days = _as_int(sync_config.get("time_window_days", "30"), 30)
        sync_config["time_window_days"] = max(1, min(time_window_days, 365))
        sync_config["full_start_date"] = sync_config.get("full_start_date", "2000-01-01")

        default_forms_raw = sync_config.get("default_forms", "")
        if default_forms_raw:
            sync_config["default_forms"] = [s for s in default_forms_raw.split(",") if s.strip()]
        else:
            sync_config["default_forms"] = []
        return sync_config

    def save_sync_preferences(self, forms: list[str], mode: str) -> None:
        try:
            self.reader.ensure_section("SYNC")
            self.config["SYNC"]["default_forms"] = ",".join(forms)
            self.config["SYNC"]["sync_type"] = mode
            self.reader.save()
        except Exception as err:
            self.logger.error("Failed to save sync preferences: %s", err)

    def get_gui_config(self) -> Dict[str, Any]:
        gui_config: Dict[str, Any] = dict(self.config["GUI"])
        gui_config["window_width"] = _as_int(gui_config["window_width"], 1200)
        gui_config["window_height"] = _as_int(gui_config["window_height"], 800)
        return gui_config

    def update_config(self, section: str, key: str, value: Any) -> None:
        self.reader.ensure_section(section)
        if isinstance(value, list):
            value = str(value[0]) if value else ""

        self.config[section][key] = str(value)
        self.reader.save()

    def get_increment_field(self, key: str) -> str:
        try:
            section = "INCREMENTAL_FIELDS"
            if section in self.config and key in self.config[section]:
                return self.config[section][key].strip()
        except Exception:
            pass
        return ""

    def set_increment_field(self, key: str, field: str) -> None:
        if not key or not field:
            return

        self.reader.ensure_section("INCREMENTAL_FIELDS")
        self.config["INCREMENTAL_FIELDS"][key] = field
        self.reader.save()

    def remove_increment_field(self, key: str) -> None:
        try:
            if "INCREMENTAL_FIELDS" in self.config and key in self.config["INCREMENTAL_FIELDS"]:
                del self.config["INCREMENTAL_FIELDS"][key]
                self.reader.save()
        except Exception:
            pass

    def get_form_queries(self) -> Dict[str, Dict[str, Any]]:
        queries = self._load_form_queries_json()
        if not queries:
            return {}

        queries = copy.deepcopy(queries)

        try:
            if "FILTER_STRINGS" in self.config:
                for form_name, filter_str in self.config["FILTER_STRINGS"].items():
                    if form_name in queries and isinstance(queries[form_name], dict):
                        queries[form_name]["FilterString"] = filter_str.strip()
        except Exception as err:
            self.logger.warning("Failed to read filter overrides: %s", err)

        return queries
