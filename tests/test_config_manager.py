from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
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
            yield importlib.import_module("src.config.config_manager")
    finally:
        live_config_pkg = sys.modules.get("src.config")
        if config_pkg is not None:
            if config_pkg_attr_present:
                config_pkg.config_manager = config_pkg_attr_value
            elif hasattr(config_pkg, "config_manager"):
                delattr(config_pkg, "config_manager")
        if live_config_pkg is not None and live_config_pkg is not config_pkg:
            if config_pkg_attr_present:
                live_config_pkg.config_manager = config_pkg_attr_value
            elif hasattr(live_config_pkg, "config_manager"):
                delattr(live_config_pkg, "config_manager")
        for name in ("src.config.config_manager", "src.config.config_accessors", "src.config.config_reader", "src.utils.crypto_util"):
            sys.modules.pop(name, None)
        for name, module in original_modules.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)


class ConfigManagerTests(unittest.TestCase):
    def test_package_attr_cleanup_does_not_leave_detached_config_manager(self) -> None:
        original_pkg = sys.modules.get("src.config")
        original_has_attr = bool(original_pkg and hasattr(original_pkg, "config_manager"))
        original_attr_value = getattr(original_pkg, "config_manager", None) if original_has_attr else None

        with _load_config_manager():
            pass

        config_pkg = sys.modules.get("src.config")
        if original_has_attr:
            self.assertIsNotNone(config_pkg)
            self.assertIs(config_pkg.config_manager, original_attr_value)
        else:
            self.assertTrue(config_pkg is None or not hasattr(config_pkg, "config_manager"))

    def test_db_config_and_form_query_overrides(self) -> None:
        sales_order = "\u9500\u552e\u8ba2\u5355"
        outstock = "\u9500\u552e\u51fa\u5e93\u5355"

        with _load_config_manager() as config_manager_module:
            config_cls = config_manager_module.ConfigManager
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
                            "driver = ODBC Driver 18 for SQL Server",
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

                manager = config_cls(str(config_path))

                db_config = manager.get_db_config()
                self.assertEqual(db_config["type"], "sqlserver")
                self.assertEqual(db_config["sqlserver"]["driver"], "ODBC Driver 18 for SQL Server")
                self.assertEqual(db_config["mysql"]["database"], "kingdee")

                sync_config = manager.get_sync_config()
                self.assertEqual(sync_config["default_forms"], [sales_order, outstock])
                self.assertFalse(sync_config["auto_sync"])
                self.assertEqual(sync_config["sync_interval"], 60)

                queries = manager.get_form_queries()
                self.assertEqual(queries[sales_order]["FormId"], "SAL_SaleOrder")
                self.assertEqual(queries[sales_order]["FilterString"], "FBillNo = 'OVERRIDE'")

    def test_default_config_path_materializes_local_config_when_no_file_exists(self) -> None:
        with _load_config_manager() as config_manager_module:
            config_cls = config_manager_module.ConfigManager
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                requested_path = tmp_path / "config.ini"
                local_path = tmp_path / "config.local.ini"

                manager = config_cls(str(requested_path))

                self.assertEqual(Path(manager.config_file), local_path)
                self.assertTrue(local_path.exists())
                self.assertFalse(requested_path.exists())

    def test_existing_legacy_config_ini_remains_read_compatible(self) -> None:
        with _load_config_manager() as config_manager_module:
            config_cls = config_manager_module.ConfigManager
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                legacy_path = tmp_path / "config.ini"
                legacy_path.write_text(
                    "\n".join(
                        [
                            "[KINGDEE]",
                            "username = legacy-user",
                            "password = legacy-password",
                            "",
                            "[DATABASE]",
                            "type = sqlserver",
                            "",
                            "[SQLSERVER]",
                            "host = legacy-host",
                            "password = legacy-db-password",
                            "",
                            "[SYNC]",
                            "auto_sync = false",
                            "sync_interval = 60",
                        ]
                    ),
                    encoding="utf-8",
                )

                manager = config_cls(str(legacy_path))

                self.assertEqual(Path(manager.config_file), legacy_path)
                self.assertFalse((tmp_path / "config.local.ini").exists())
                self.assertEqual(manager.get_kingdee_config()["username"], "legacy-user")

    def test_sync_config_exposes_circuit_breaker_defaults(self) -> None:
        with _load_config_manager() as config_manager_module:
            config_cls = config_manager_module.ConfigManager
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
                manager = config_cls(str(config_path))

                sync_config = manager.get_sync_config()

        self.assertTrue(sync_config["circuit_breaker_enabled"])
        self.assertEqual(sync_config["circuit_breaker_threshold"], 3)
        self.assertEqual(sync_config["circuit_breaker_cooldown_secs"], 30)

    def test_sync_config_migrates_legacy_full_sync_type_to_complete(self) -> None:
        with _load_config_manager() as config_manager_module:
            config_cls = config_manager_module.ConfigManager
            with tempfile.TemporaryDirectory() as tmp_dir:
                config_path = Path(tmp_dir) / "config.ini"
                config_path.write_text(
                    "\n".join(
                        [
                            "[SYNC]",
                            "auto_sync = false",
                            "sync_interval = 60",
                            "default_forms = 物料",
                            "sync_type = full",
                        ]
                    ),
                    encoding="utf-8",
                )
                manager = config_cls(str(config_path))

                sync_config = manager.get_sync_config()
                disk_text = config_path.read_text(encoding="utf-8")

        self.assertEqual(sync_config["sync_type"], "complete")
        self.assertIn("sync_type = complete", disk_text)

    def test_get_field_mappings_reads_json_from_config_directory(self) -> None:
        with _load_config_manager() as config_manager_module:
            config_cls = config_manager_module.ConfigManager
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                config_path = tmp_path / "config.ini"
                mappings_path = tmp_path / "field_mappings.json"
                config_path.write_text("[SYNC]\nauto_sync = false\nsync_interval = 60\n", encoding="utf-8")
                mappings_path.write_text(
                    json.dumps(
                        {
                            "prd_mo": {
                                "FCANCELSTATUS": {
                                    "sources": ["FCANCELSTATUS", "FCancelStatus"],
                                    "type": "string",
                                    "default": "",
                                }
                            }
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                manager = config_cls(str(config_path))

                mappings = manager.get_field_mappings()

        self.assertIn("prd_mo", mappings)
        self.assertEqual(
            mappings["prd_mo"]["FCANCELSTATUS"]["sources"],
            ["FCANCELSTATUS", "FCancelStatus"],
        )

    def test_builtin_tables_json_registers_ar_receivable_sync(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tables = json.loads((repo_root / "src" / "config" / "tables.json").read_text(encoding="utf-8"))
        form_queries = json.loads((repo_root / "src" / "config" / "form-queries.json").read_text(encoding="utf-8"))

        self.assertIn("应收单", form_queries)
        self.assertIn("应收单", tables)
        self.assertEqual(tables["应收单"]["table"], "AR_receivable")
        self.assertEqual(tables["应收单"]["insert_method"], "insert_ar_receivable")

    def test_builtin_material_query_requests_fdescription(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        form_queries = json.loads((repo_root / "src" / "config" / "form-queries.json").read_text(encoding="utf-8"))

        field_keys = form_queries["物料"]["FieldKeys"].split(",")

        self.assertIn("FDescription", field_keys)
        self.assertEqual(field_keys[-1], "FDescription")


if __name__ == "__main__":
    unittest.main()

