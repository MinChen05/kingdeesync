import sys
import types
import unittest


class _FakeCursor:
    def __init__(self):
        self.executed_sql = None
        self.executed_values = None

    def executemany(self, sql, values):
        self.executed_sql = sql
        self.executed_values = values


class _FakeConnection:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class _FakeDbManager:
    db_type = "sqlserver"

    def __init__(self):
        self.connection = _FakeConnection()
        self.cursor = _FakeCursor()

    def connect(self):
        return True


class AccountBalanceSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules.setdefault(
            "src.config.config_manager",
            types.SimpleNamespace(config_manager=types.SimpleNamespace()),
        )
        sys.modules.setdefault(
            "src.core.kingdee_api",
            types.SimpleNamespace(kingdee_client=types.SimpleNamespace()),
        )
        sys.modules.setdefault(
            "src.core.mysql_manager",
            types.SimpleNamespace(mysql_manager=types.SimpleNamespace()),
        )

        from src.core.account_balance_sync import AccountBalanceSyncManager

        cls.manager_cls = AccountBalanceSyncManager

    def test_insert_data_parses_thousands_separators_in_amount_fields(self):
        manager = self.manager_cls()
        fake_db = _FakeDbManager()

        inserted = manager._insert_data(
            [
                {
                    "FBALANCEID": "6711.04",
                    "FBALANCENAME": "客户扣款",
                    "FDETAILNUMBER": "010TLKJ222024001/CX003",
                    "FDETAILNAME": "台铃科技股份有限公司/两轮产品线",
                    "FDEBIT": "1,208.85",
                    "FCREDIT": "5,757.60",
                    "FACCTYEAR": "2026",
                    "FACCTPERIOD": "1",
                }
            ],
            db_manager=fake_db,
        )

        self.assertEqual(inserted, 1)
        row = fake_db.cursor.executed_values[0]
        self.assertEqual(row[10], 1208.85)
        self.assertEqual(row[12], 5757.60)


if __name__ == "__main__":
    unittest.main()
