from __future__ import annotations

import importlib
import json
import sys
import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

def _load_config_manager():
    original_modules = {
        name: sys.modules.get(name)
        for name in ("src.config", "src.config.config_manager", "src.config.config_accessors", "src.config.config_reader", "src.utils.crypto_util")
    }
    config_pkg = original_modules["src.config"]
    config_pkg_attr_present = bool(config_pkg and hasattr(config_pkg, "config_manager"))
    config_pkg_attr_value = getattr(config_pkg, "config_manager", None) if config_pkg_attr_present else None
    for name in original_modules:
        sys.modules.pop(name, None)

    crypto_util_stub = types.ModuleType("src.utils.crypto_util")

    class _CryptoUtil:
        @staticmethod
        def encrypt(value: str) -> str:
            return value

        @staticmethod
        def decrypt(value: str) -> str:
            return value

    crypto_util_stub.CryptoUtil = _CryptoUtil

    try:
        with patch.dict(sys.modules, {"src.utils.crypto_util": crypto_util_stub}):
            return importlib.import_module("src.config.config_manager")
    finally:
        if config_pkg is not None:
            if config_pkg_attr_present:
                setattr(config_pkg, "config_manager", config_pkg_attr_value)
            elif hasattr(config_pkg, "config_manager"):
                delattr(config_pkg, "config_manager")
        for name in ("src.config.config_manager", "src.config.config_accessors", "src.config.config_reader", "src.utils.crypto_util"):
            sys.modules.pop(name, None)
        for name, module in original_modules.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)


ConfigManager = _load_config_manager().ConfigManager


class ConfigManagerTests(unittest.TestCase):
    def test_db_config_and_form_query_overrides(self) -> None:
        sales_order = "\u9500\u552e\u8ba2\u5355"
        outstock = "\u9500\u552e\u51fa\u5e93\u5355"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_path = tmp_path / "config.ini"
            queries_path = tmp_path / "form-queries.json"

            config_path.write_text(
                "\n".join(
                    [
                        "[KINGDEE]",
                        "login_url = https://example.com/login",
                        "query_url = https://example.com/query",
                        "acct_id = demo",
                        "username = user",
                        "password = plain",
                        "lcid = 2052",
                        "",
                        "[DATABASE]",
                        "type = sqlserver",
                        "",
                        "[MYSQL]",
                        "host = 127.0.0.1",
                        "user = root",
                        "password = plain",
                        "database = kingdee",
                        "charset = utf8mb4",
                        "port = 3306",
                        "",
                        "[SQLSERVER]",
                        "host = 127.0.0.1",
                        "user = sa",
                        "password = plain",
                        "database = kingdee",
                        "port = 1433",
                        "driver = ODBC Driver 17 for SQL Server",
                        "",
                        "[SYNC]",
                        "auto_sync = false",
                        "sync_interval = 60",
                        f"default_forms = {sales_order},{outstock}",
                        "",
                        "[GUI]",
                        "window_width = 1200",
                        "window_height = 800",
                        "",
                        "[FILTER_STRINGS]",
                        f"{sales_order} = FBillNo = 'OVERRIDE'",
                    ]
                ),
                encoding="utf-8",
            )
            queries_path.write_text(
                json.dumps(
                    {
                        sales_order: {
                            "FormId": "SAL_SaleOrder",
                            "FieldKeys": "FID,FBillNo,FModifyDate",
                            "FilterString": "FDocumentStatus='C'",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            manager = ConfigManager(str(config_path))

            db_config = manager.get_db_config()
            self.assertEqual(db_config["type"], "sqlserver")
            self.assertEqual(db_config["sqlserver"]["driver"], "ODBC Driver 17 for SQL Server")
            self.assertEqual(db_config["mysql"]["database"], "kingdee")

            sync_config = manager.get_sync_config()
            self.assertEqual(sync_config["default_forms"], [sales_order, outstock])
            self.assertFalse(sync_config["auto_sync"])
            self.assertEqual(sync_config["sync_interval"], 60)

            queries = manager.get_form_queries()
            self.assertEqual(queries[sales_order]["FormId"], "SAL_SaleOrder")
            self.assertEqual(queries[sales_order]["FilterString"], "FBillNo = 'OVERRIDE'")

    def test_sync_config_exposes_circuit_breaker_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SYNC]",
                        "auto_sync = false",
                        "sync_interval = 60",
                    ]
                ),
                encoding="utf-8",
            )
            manager = ConfigManager(str(config_path))

            sync_config = manager.get_sync_config()

            self.assertTrue(sync_config["circuit_breaker_enabled"])
            self.assertEqual(sync_config["circuit_breaker_threshold"], 3)
            self.assertEqual(sync_config["circuit_breaker_cooldown_secs"], 30)


if __name__ == "__main__":
    unittest.main()

