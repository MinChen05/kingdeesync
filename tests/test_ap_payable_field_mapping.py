from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock


class _DummyUpsertEngine:
    def __init__(self, *args, **kwargs):
        pass


class _DummyRepository:
    def __init__(self, *args, **kwargs):
        pass

    def reset(self):
        return None

    def missing_methods(self, *args, **kwargs):
        return []


class _DummyPool:
    def __init__(self, *args, **kwargs):
        pass


class _DummyConfigManager:
    def get_db_config(self):
        return {
            "type": "mysql",
            "mysql": {
                "host": "localhost",
                "user": "test",
                "password": "",
                "database": "test",
            },
        }

    def get_insert_method_map(self):
        return {}


@contextmanager
def _temporary_modules(stubs: dict[str, object]):
    sentinel = object()
    original: dict[str, object] = {}
    try:
        for module_name, module in stubs.items():
            original[module_name] = sys.modules.get(module_name, sentinel)
            sys.modules[module_name] = module
        yield
    finally:
        for module_name, previous in original.items():
            if previous is sentinel:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous


def _load_mysql_manager_class():
    stubs = {
        "pyodbc": types.SimpleNamespace(),
        "pymysql": types.SimpleNamespace(cursors=types.SimpleNamespace(DictCursor=object)),
        "dbutils": types.SimpleNamespace(),
        "dbutils.pooled_db": types.SimpleNamespace(PooledDB=_DummyPool),
        "src.config.config_manager": types.SimpleNamespace(config_manager=_DummyConfigManager()),
        "src.core.performance_logging": types.SimpleNamespace(log_prepare_metrics=lambda *args, **kwargs: None),
        "src.core.sync_log_repository": types.SimpleNamespace(SyncLogRepository=_DummyRepository),
        "src.core.sync_run_repository": types.SimpleNamespace(SyncRunRepository=_DummyRepository),
        "src.core.upsert_engine_mysql": types.SimpleNamespace(UpsertEngineMySQL=_DummyUpsertEngine),
        "src.core.upsert_engine_sqlserver": types.SimpleNamespace(UpsertEngineSqlServer=_DummyUpsertEngine),
        "src.core.write_outcome": types.SimpleNamespace(WriteOutcome=object),
        "src.core.writers_registry": types.SimpleNamespace(WriterRegistry=_DummyRepository),
    }
    module_path = Path(__file__).resolve().parents[1] / "src" / "core" / "mysql_manager.py"
    module_name = "src.core.mysql_manager"
    sentinel = object()
    previous_module = sys.modules.get(module_name, sentinel)

    with _temporary_modules(stubs):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load src.core.mysql_manager for tests")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            if previous_module is sentinel:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = previous_module

    return module.MySQLManager


MySQLManager = _load_mysql_manager_class()


class ApPayableFieldMappingTests(unittest.TestCase):
    def test_prepare_ap_payable_data_reads_no_tax_amount_from_kingdee_field(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        prepared = manager._prepare_ap_payable_data(
            {
                "FID": 1001,
                "FEntityDetail_FENTRYID": 2001,
                "FEntityDetail_FSEQ": 1,
                "FBillTypeID.FNAME": "标准应付单",
                "FBillNo": "AP202601001",
                "FDATE": "2026-01-10",
                "FPURCHASEORGID.FNAME": "台州市金宇机电有限公司",
                "F_ora_Base1.FNAME": "测试客户",
                "FSUPPLIERID.FNAME": "测试供应商",
                "FSETACCOUNTTYPE": "3",
                "FMATERIALID.FNUMBER": "FEE-TRANS",
                "FMATERIALID.FNAME": "交通运输费",
                "FPRICEUNITID.FNAME": "元",
                "FPRICEQTY": "1",
                "FALLAMOUNTFOR_D": "113.00",
                "FNoTaxAmountFor_D": "100.00",
                "FDISCOUNTAMOUNTFOR": "0",
                "FModifyDate": "2026-01-10 10:00:00",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[15], 100.0)

    def test_prepare_ap_payable_data_prefers_detail_no_tax_amount_over_bill_total(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        prepared = manager._prepare_ap_payable_data(
            {
                "FID": 1002,
                "FEntityDetail_FENTRYID": 2002,
                "FEntityDetail_FSEQ": 1,
                "FBillTypeID.FNAME": "标准应付单",
                "FBillNo": "AP202601002",
                "FDATE": "2026-01-10",
                "FPURCHASEORGID.FNAME": "台州市金宇机电有限公司",
                "F_ora_Base1.FNAME": "测试客户",
                "FSUPPLIERID.FNAME": "测试供应商",
                "FSETACCOUNTTYPE": "3",
                "FMATERIALID.FNUMBER": "FEE-TRANS",
                "FMATERIALID.FNAME": "交通运输费",
                "FPRICEUNITID.FNAME": "元",
                "FPRICEQTY": "1",
                "FALLAMOUNTFOR_D": "113.00",
                "FNOTAXAMOUNTFOR_D": "100.00",
                "FNOTAXAMOUNTFOR": "999.00",
                "FDISCOUNTAMOUNTFOR": "0",
                "FModifyDate": "2026-01-10 10:00:00",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[15], 100.0)

    def test_prepare_ap_payable_data_does_not_use_bill_total_no_tax_amount(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)

        prepared = manager._prepare_ap_payable_data(
            {
                "FID": 1003,
                "FEntityDetail_FENTRYID": 2003,
                "FEntityDetail_FSEQ": 1,
                "FBillTypeID.FNAME": "标准应付单",
                "FBillNo": "AP202601003",
                "FDATE": "2026-01-10",
                "FPURCHASEORGID.FNAME": "台州市金宇机电有限公司",
                "F_ora_Base1.FNAME": "测试客户",
                "FSUPPLIERID.FNAME": "测试供应商",
                "FSETACCOUNTTYPE": "3",
                "FMATERIALID.FNUMBER": "FEE-TRANS",
                "FMATERIALID.FNAME": "交通运输费",
                "FPRICEUNITID.FNAME": "元",
                "FPRICEQTY": "1",
                "FALLAMOUNTFOR_D": "113.00",
                "FNOTAXAMOUNTFOR": "999.00",
                "FDISCOUNTAMOUNTFOR": "0",
                "FModifyDate": "2026-01-10 10:00:00",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[15], 0.0)

    def test_prepare_ap_payable_data_uses_field_mapping_resolver_for_no_tax_amount(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.field_mapping_resolver = Mock()
        manager.field_mapping_resolver.resolve_field.return_value = 321.45

        prepared = manager._prepare_ap_payable_data(
            {
                "FID": 1004,
                "FEntityDetail_FENTRYID": 2004,
                "FEntityDetail_FSEQ": 1,
                "FBillTypeID.FNAME": "标准应付单",
                "FBillNo": "AP202601004",
                "FDATE": "2026-01-10",
                "FPURCHASEORGID.FNAME": "台州市金宇机电有限公司",
                "F_ora_Base1.FNAME": "测试客户",
                "FSUPPLIERID.FNAME": "测试供应商",
                "FSETACCOUNTTYPE": "3",
                "FMATERIALID.FNUMBER": "FEE-TRANS",
                "FMATERIALID.FNAME": "交通运输费",
                "FPRICEUNITID.FNAME": "元",
                "FPRICEQTY": "1",
                "FALLAMOUNTFOR_D": "113.00",
                "FNOTAXAMOUNTFOR_D": "100.00",
                "FNOTAXAMOUNTFOR": "999.00",
                "FDISCOUNTAMOUNTFOR": "0",
                "FModifyDate": "2026-01-10 10:00:00",
            }
        )

        self.assertIsNotNone(prepared)
        resolve_call = manager.field_mapping_resolver.resolve_field.call_args
        self.assertIsNotNone(resolve_call)
        self.assertEqual(resolve_call.args[0], "ap_payable")
        self.assertEqual(resolve_call.args[1], "FNOTAXAMOUNTFOR")
        self.assertEqual(resolve_call.args[2]["FNOTAXAMOUNTFOR_D"], "100.00")
        self.assertEqual(resolve_call.args[2]["FNOTAXAMOUNTFOR"], "999.00")
        self.assertEqual(prepared[15], 321.45)

    def test_prepare_ap_payable_data_uses_field_mapping_resolver_for_no_tax_amount_on_list_payload(self) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.field_mapping_resolver = Mock()
        manager.field_mapping_resolver.resolve_field.return_value = 654.32

        prepared = manager._prepare_ap_payable_data(
            [
                1005,
                2005,
                1,
                "标准应付单",
                "AP202601005",
                "2026-01-10",
                "台州市金宇机电有限公司",
                "测试客户",
                "测试供应商",
                "3",
                "FEE-TRANS",
                "交通运输费",
                "元",
                "1",
                "113.00",
                "100.00",
                "0",
                None,
                None,
                "2026-01-10 10:00:00",
                "999.00",
            ]
        )

        self.assertIsNotNone(prepared)
        resolve_call = manager.field_mapping_resolver.resolve_field.call_args
        self.assertIsNotNone(resolve_call)
        self.assertEqual(resolve_call.args[0], "ap_payable")
        self.assertEqual(resolve_call.args[1], "FNOTAXAMOUNTFOR")
        self.assertEqual(resolve_call.args[2]["FNOTAXAMOUNTFOR_D"], "100.00")
        self.assertEqual(resolve_call.args[2]["FNOTAXAMOUNTFOR"], "999.00")
        self.assertEqual(prepared[15], 654.32)

    def test_prepare_ap_payable_data_falls_back_to_original_no_tax_amount_when_resolver_runtime_error_raises(
        self,
    ) -> None:
        manager = MySQLManager.__new__(MySQLManager)
        manager.field_mapping_resolver = Mock()
        manager.field_mapping_resolver.resolve_field.side_effect = RuntimeError("resolver failed")

        prepared = manager._prepare_ap_payable_data(
            {
                "FID": 1006,
                "FEntityDetail_FENTRYID": 2006,
                "FEntityDetail_FSEQ": 1,
                "FBillTypeID.FNAME": "标准应付单",
                "FBillNo": "AP202601006",
                "FDATE": "2026-01-10",
                "FPURCHASEORGID.FNAME": "台州市金宇机电有限公司",
                "F_ora_Base1.FNAME": "测试客户",
                "FSUPPLIERID.FNAME": "测试供应商",
                "FSETACCOUNTTYPE": "3",
                "FMATERIALID.FNUMBER": "FEE-TRANS",
                "FMATERIALID.FNAME": "交通运输费",
                "FPRICEUNITID.FNAME": "元",
                "FPRICEQTY": "1",
                "FALLAMOUNTFOR_D": "113.00",
                "FNOTAXAMOUNTFOR_D": "100.00",
                "FNOTAXAMOUNTFOR": "999.00",
                "FDISCOUNTAMOUNTFOR": "0",
                "FModifyDate": "2026-01-10 10:00:00",
            }
        )

        self.assertIsNotNone(prepared)
        self.assertEqual(prepared[15], 100.0)


if __name__ == "__main__":
    unittest.main()
