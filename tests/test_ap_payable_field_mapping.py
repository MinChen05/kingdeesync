from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import Mock

_STUBBED_MODULES: list[str] = []


class _DummyUpsertEngine:
    def __init__(self, *args, **kwargs):
        pass


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


def _install_stub(module_name: str, module: object) -> None:
    if module_name in sys.modules:
        return

    sys.modules[module_name] = module
    _STUBBED_MODULES.append(module_name)


_install_stub("pyodbc", types.SimpleNamespace())
_install_stub("pymysql", types.SimpleNamespace(cursors=types.SimpleNamespace(DictCursor=object)))
_install_stub("dbutils", types.SimpleNamespace())
_install_stub("dbutils.pooled_db", types.SimpleNamespace(PooledDB=_DummyPool))
_install_stub("src.config.config_manager", types.SimpleNamespace(config_manager=_DummyConfigManager()))
_install_stub("src.core.upsert_engine_mysql", types.SimpleNamespace(UpsertEngineMySQL=_DummyUpsertEngine))
_install_stub("src.core.upsert_engine_sqlserver", types.SimpleNamespace(UpsertEngineSqlServer=_DummyUpsertEngine))
_install_stub("src.core.write_outcome", types.SimpleNamespace(WriteOutcome=object))

from src.core.mysql_manager import MySQLManager

sys.modules.pop("src.core.mysql_manager", None)
for _module_name in _STUBBED_MODULES:
    sys.modules.pop(_module_name, None)


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
        manager.field_mapping_resolver.resolve_field.assert_any_call(
            "ap_payable",
            "FNOTAXAMOUNTFOR",
            unittest.mock.ANY,
        )
        self.assertEqual(prepared[15], 321.45)


if __name__ == "__main__":
    unittest.main()
