"""
Configuration file IO and sensitive-value handling.
"""

from __future__ import annotations

import ast
import configparser
import copy
import logging
import os
import sys
from typing import Iterable

from src.utils.crypto_util import CryptoUtil

DEFAULT_SENSITIVE_KEYS = ("password", "api_key", "secret", "token")
DEFAULT_CONFIG_DATA = {
    "KINGDEE": {
        "login_url": "https://your-domain/k3cloud/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc",
        "query_url": "https://your-domain/k3cloud/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc",
        "acct_id": "your_acct_id",
        "username": "your_username",
        "password": "your_password",
        "lcid": "2052",
        "pagination_enabled": "false",
        "request_timeout": "0",
        "page_size": "20000",
        "max_pages": "100000",
        "rate_limit_qps": "2",
        "keep_session_alive": "true",
        "keep_alive_interval_secs": "600",
        "auto_logout_on_exit": "false",
    },
    "DATABASE": {
        "type": "sqlserver",
    },
    "MYSQL": {
        "host": "127.0.0.1",
        "user": "your_user",
        "password": "your_password",
        "database": "your_database",
        "charset": "utf8mb4",
        "port": "3306",
        "batch_size": "5000",
        "commit_every_n_batches": "2",
        "pool_maxconnections": "10",
        "pool_mincached": "2",
        "pool_maxcached": "5",
    },
    "SQLSERVER": {
        "host": "127.0.0.1",
        "user": "sa",
        "password": "your_password",
        "database": "your_database",
        "port": "1433",
        "driver": "ODBC Driver 17 for SQL Server",
        "dsn": "",
        "trusted_connection": "false",
        "encrypt": "auto",
        "trust_server_certificate": "true",
        "login_timeout": "15",
        "insert_threads": "6",
        "batch_size": "5000",
        "commit_every_n_batches": "2",
        "use_staging": "true",
        "force_staging_tables": "saleorder,sal_outstock,sal_returnstock,sal_deliverynotice,prd_instock,prd_mo,prd_moentry,prd_ppbom,prd_ppbomentry,eng_bom,eng_bomchild,stk_inventory,sub_subreqorder",
        "pool_maxconnections": "10",
        "pool_mincached": "2",
        "pool_maxcached": "5",
    },
    "SYNC": {
        "auto_sync": "False",
        "sync_interval": "60",
        "last_sync_time": "",
        "sync_type": "incremental",
        "default_forms": "",
        "fetch_concurrency": "4",
        "table_concurrency": "4",
        "time_window_days": "30",
        "full_start_date": "2000-01-01",
    },
    "GUI": {
        "theme": "blue",
        "window_width": "1200",
        "window_height": "800",
    },
}


def _resolve_existing_path(candidate: str) -> str | None:
    if os.path.isabs(candidate):
        return candidate if os.path.exists(candidate) else None

    if os.path.exists(candidate):
        return os.path.abspath(candidate)

    exe_dir = os.path.dirname(sys.executable)
    exe_candidate = os.path.join(exe_dir, candidate)
    if os.path.exists(exe_candidate):
        return exe_candidate

    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_candidate = os.path.join(script_dir, candidate)
    if os.path.exists(script_candidate):
        return script_candidate

    return None


def resolve_config_path(config_file: str) -> str:
    """Resolve config path with runtime-compatible lookup order."""
    candidates = [config_file]

    config_basename = os.path.basename(config_file).lower()
    if config_basename == "config.ini":
        config_dir = os.path.dirname(config_file)
        local_override = os.path.join(config_dir, "config.local.ini") if config_dir else "config.local.ini"
        candidates.insert(0, local_override)

    for candidate in candidates:
        resolved = _resolve_existing_path(candidate)
        if resolved:
            return resolved

    return candidates[-1]


def _is_sensitive_key(key: str, sensitive_keys: Iterable[str]) -> bool:
    return any(token in key.lower() for token in sensitive_keys)


def clean_list_like_values(config: configparser.ConfigParser, logger: logging.Logger) -> None:
    """Normalize legacy list-string values like "['value']" to "value"."""
    for section in config.sections():
        for key in config[section]:
            val = config[section][key]
            if not (isinstance(val, str) and val.strip().startswith("['") and val.strip().endswith("']")):
                continue

            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, list):
                    config[section][key] = str(parsed[0]) if parsed else ""
            except Exception as err:
                logger.debug("Error cleaning %s.%s: %s", section, key, err)


def encrypt_sensitive_values(
    config: configparser.ConfigParser,
    sensitive_keys: Iterable[str],
) -> None:
    """Encrypt sensitive keys in-place when value is plain text."""
    for section in config.sections():
        for key in config[section]:
            value = config[section][key]
            if not (_is_sensitive_key(key, sensitive_keys) and value):
                continue
            if value.startswith("encrypted:"):
                continue
            config[section][key] = f"encrypted:{CryptoUtil.encrypt(value)}"


def decrypt_sensitive_values(
    config: configparser.ConfigParser,
    sensitive_keys: Iterable[str],
    logger: logging.Logger,
) -> None:
    """Decrypt sensitive keys in-place for runtime usage."""
    for section in config.sections():
        for key in config[section]:
            value = config[section][key]
            if not (_is_sensitive_key(key, sensitive_keys) and value and value.startswith("encrypted:")):
                continue

            encrypted_part = value[10:]
            try:
                decrypted_value = CryptoUtil.decrypt(encrypted_part)
                if not decrypted_value:
                    logger.warning(
                        "Decrypted value is empty for [%s]%s; please re-enter and save this field.",
                        section,
                        key,
                    )
                config[section][key] = decrypted_value
            except Exception as err:
                logger.error("Failed to decrypt %s: %s", key, err)


class ConfigReader:
    """Owns config file location, defaults, loading, saving, and decryption."""

    def __init__(
        self,
        config_file: str = "config.ini",
        *,
        logger: logging.Logger | None = None,
        sensitive_keys: Iterable[str] = DEFAULT_SENSITIVE_KEYS,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.config_file = resolve_config_path(config_file)
        self.config = configparser.ConfigParser()
        self.sensitive_keys = tuple(sensitive_keys)
        self.load()

    def load(self) -> None:
        """Load config from disk or materialize defaults."""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding="utf-8")
            clean_list_like_values(self.config, self.logger)
            decrypt_sensitive_values(self.config, self.sensitive_keys, self.logger)
            return

        self.create_default()

    def save(self) -> None:
        """Persist current config to disk with encrypted secrets."""
        serialized = configparser.ConfigParser()
        serialized.read_dict(
            {section: dict(self.config[section]) for section in self.config.sections()}
        )
        encrypt_sensitive_values(serialized, self.sensitive_keys)

        with open(self.config_file, "w", encoding="utf-8") as fp:
            serialized.write(fp)

        self.load()

    def create_default(self) -> None:
        """Reset in-memory config to defaults and save it."""
        self.config = configparser.ConfigParser()
        self.config.read_dict(copy.deepcopy(DEFAULT_CONFIG_DATA))
        self.save()

    def ensure_section(self, section: str) -> None:
        """Make sure a section exists before updates."""
        if section not in self.config:
            self.config[section] = {}
