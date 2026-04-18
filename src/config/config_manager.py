"""
Compatibility facade for configuration access.
"""

from __future__ import annotations

import configparser
import logging
from typing import Any, Dict

from src.config.config_accessors import ConfigAccessors
from src.config.config_reader import ConfigReader

logger = logging.getLogger(__name__)


class ConfigManager:
    """Keep the existing public interface while delegating responsibilities."""

    def __init__(self, config_file: str = "config.ini") -> None:
        self._reader = ConfigReader(config_file=config_file, logger=logger)
        self._accessors = ConfigAccessors(self._reader, logger=logger)

    @property
    def config_file(self) -> str:
        return self._reader.config_file

    @property
    def config(self) -> configparser.ConfigParser:
        return self._reader.config

    @property
    def sensitive_keys(self) -> tuple[str, ...]:
        return self._reader.sensitive_keys

    def load_config(self) -> None:
        self._reader.load()

    def create_default_config(self) -> None:
        self._reader.create_default()

    def save_config(self) -> None:
        self._reader.save()

    def get_table_mapping(self) -> Dict[str, str]:
        return self._accessors.get_table_mapping()

    def get_insert_method_map(self) -> Dict[str, str]:
        return self._accessors.get_insert_method_map()

    def get_kingdee_config(self) -> Dict[str, Any]:
        return self._accessors.get_kingdee_config()

    def get_mysql_config(self) -> Dict[str, str]:
        return self._accessors.get_mysql_config()

    def get_db_config(self) -> Dict[str, Any]:
        return self._accessors.get_db_config()

    def get_sync_config(self) -> Dict[str, Any]:
        return self._accessors.get_sync_config()

    def save_sync_preferences(self, forms: list[str], mode: str) -> None:
        self._accessors.save_sync_preferences(forms, mode)

    def get_gui_config(self) -> Dict[str, Any]:
        return self._accessors.get_gui_config()

    def update_config(self, section: str, key: str, value: Any) -> None:
        self._accessors.update_config(section, key, value)

    def get_increment_field(self, key: str) -> str:
        return self._accessors.get_increment_field(key)

    def set_increment_field(self, key: str, field: str) -> None:
        self._accessors.set_increment_field(key, field)

    def remove_increment_field(self, key: str) -> None:
        self._accessors.remove_increment_field(key)

    def get_form_queries(self) -> Dict[str, Dict[str, Any]]:
        return self._accessors.get_form_queries()


config_manager = ConfigManager()
