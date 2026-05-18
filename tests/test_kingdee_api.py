from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class _RequestError(Exception):
        pass

    class _TimeoutError(_RequestError):
        pass

    class _ReadTimeoutError(_TimeoutError):
        pass

    class _ConnectionError(_RequestError):
        pass

    class _HTTPError(_RequestError):
        pass

    class _Session:
        def __init__(self) -> None:
            self.verify = True
            self.headers = {}

        def post(self, *args, **kwargs):
            raise NotImplementedError

        def close(self) -> None:
            pass

    requests_stub.Session = _Session
    requests_stub.exceptions = types.SimpleNamespace(
        RequestException=_RequestError,
        Timeout=_TimeoutError,
        ReadTimeout=_ReadTimeoutError,
        ConnectionError=_ConnectionError,
        HTTPError=_HTTPError,
    )
    sys.modules["requests"] = requests_stub

if "src.config.config_manager" not in sys.modules:
    config_manager_stub = types.ModuleType("src.config.config_manager")
    config_manager_stub.config_manager = SimpleNamespace(
        get_kingdee_config=dict,
        get_form_queries=dict,
        get_insert_method_map=dict,
        get_table_mapping=dict,
        get_db_config=lambda: {"type": "mysql", "mysql": {}, "sqlserver": {}},
        get_sync_config=lambda: {"circuit_breaker_enabled": True, "circuit_breaker_threshold": 3, "circuit_breaker_cooldown_secs": 30},
        get_increment_field=lambda _key: None,
        set_increment_field=lambda _key, _value: None,
        update_config=lambda *_args, **_kwargs: None,
    )
    sys.modules["src.config.config_manager"] = config_manager_stub

from src.core.kingdee_api import KingdeeAPIClient


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class KingdeeAPIClientQueryTests(unittest.TestCase):
    def _make_client(self) -> KingdeeAPIClient:
        with patch("src.core.kingdee_api.config_manager") as mock_config_manager:
            mock_config_manager.get_kingdee_config.return_value = {
                "ssl_verify": "false",
                "login_url": "https://example.com/login",
                "query_url": "https://example.com/query",
                "rate_limit_qps": 0,
                "request_retries": 1,
                "retry_base_delay": 0.01,
                "retry_max_delay": 0.01,
                "request_connect_timeout": 5,
                "request_read_timeout": 5,
                "max_request_read_timeout": 5,
                "page_size": 20000,
                "max_pages": 2,
            }
            client = KingdeeAPIClient()
        client.is_authenticated = True
        return client

    def test_test_connection_uses_session_preflight_for_authenticated_session(self) -> None:
        client = self._make_client()
        client._keep_alive_ping = Mock(return_value=True)
        client.login = Mock(side_effect=AssertionError("should not login"))

        connected = client.test_connection()

        self.assertTrue(connected)
        client._keep_alive_ping.assert_called_once_with()

    def test_ensure_session_logs_preflight_success(self) -> None:
        client = self._make_client()
        client._keep_alive_ping = Mock(return_value=True)

        with self.assertLogs("src.core.kingdee_api", level="INFO") as captured:
            connected = client.ensure_session()

        self.assertTrue(connected)
        self.assertIn("同步前会话预检通过", "\n".join(captured.output))

    def test_test_connection_relogs_when_preflight_ping_fails(self) -> None:
        client = self._make_client()
        client._keep_alive_ping = Mock(return_value=False)
        client.logout = Mock()
        client.login = Mock(return_value=True)

        with self.assertLogs("src.core.kingdee_api", level="INFO") as captured:
            connected = client.test_connection()

        self.assertTrue(connected)
        client.logout.assert_called_once_with(force=True)
        client.login.assert_called_once_with()
        self.assertIn("同步前会话预检失败", "\n".join(captured.output))
        self.assertIn("同步前会话重登成功", "\n".join(captured.output))

    def test_ensure_session_refreshes_cross_day_session_in_overnight_window(self) -> None:
        client = self._make_client()
        client.session_started_at = datetime(2026, 5, 17, 23, 50, 0)
        client._keep_alive_ping = Mock(side_effect=AssertionError("should not ping during forced refresh"))
        client.logout = Mock()
        client.login = Mock(return_value=True)

        with self.assertLogs("src.core.kingdee_api", level="INFO") as captured:
            connected = client.ensure_session(now=datetime(2026, 5, 18, 0, 30, 0))

        self.assertTrue(connected)
        client.logout.assert_called_once_with(force=True)
        client.login.assert_called_once_with()
        self.assertIn("命中凌晨会话刷新窗口", "\n".join(captured.output))
        self.assertIn("凌晨窗口会话刷新成功", "\n".join(captured.output))

    def test_query_data_rejects_list_wrapped_session_error_payload(self) -> None:
        client = self._make_client()
        page_callback = Mock()
        client.session.post = Mock(
            return_value=FakeResponse(
                [
                    {
                        "Result": {
                            "ResponseStatus": {
                                "IsSuccess": False,
                                "Errors": [{"Message": "会话信息已丢失，请重新登录"}],
                            }
                        }
                    }
                ]
            )
        )

        rows = client.query_data(
            "销售订单",
            {
                "FormId": "SAL_SaleOrder",
                "FieldKeys": "FID,FBillNo",
                "StartRow": 0,
                "Limit": 0,
            },
            page_callback=page_callback,
        )

        self.assertIsNone(rows)
        page_callback.assert_not_called()

    def test_query_data_retries_same_page_once_after_session_error(self) -> None:
        client = self._make_client()
        client.logout = Mock()
        client.login = Mock(return_value=True)
        client.session.post = Mock(
            side_effect=[
                FakeResponse(
                    {
                        "Result": {
                            "ResponseStatus": {
                                "IsSuccess": False,
                                "Errors": [{"Message": "会话信息已丢失，请重新登录"}],
                            }
                        }
                    }
                ),
                FakeResponse(
                    {
                        "Result": {
                            "ResponseStatus": {"IsSuccess": True},
                            "Result": [[1, "SO001"]],
                        }
                    }
                ),
            ]
        )

        rows = client.query_data(
            "销售订单",
            {
                "FormId": "SAL_SaleOrder",
                "FieldKeys": "FID,FBillNo",
                "StartRow": 0,
                "Limit": 0,
            },
        )

        self.assertEqual(rows, [{"FID": 1, "FBillNo": "SO001"}])
        client.logout.assert_called_once_with(force=True)
        client.login.assert_called_once()

    def test_query_data_retries_when_session_error_is_embedded_in_row_payload(self) -> None:
        client = self._make_client()
        client.logout = Mock()
        client.login = Mock(return_value=True)
        client.session.post = Mock(
            side_effect=[
                FakeResponse(
                    {
                        "Result": {
                            "ResponseStatus": {"IsSuccess": True},
                            "Result": [
                                [
                                    {
                                        "Result": {
                                            "ResponseStatus": {
                                                "IsSuccess": False,
                                                "Errors": [{"Message": "会话信息已丢失，请重新登录"}],
                                            }
                                        }
                                    }
                                ]
                            ],
                        }
                    }
                ),
                FakeResponse(
                    {
                        "Result": {
                            "ResponseStatus": {"IsSuccess": True},
                            "Result": [[1, "SO001"]],
                        }
                    }
                ),
            ]
        )

        rows = client.query_data(
            "销售订单",
            {
                "FormId": "SAL_SaleOrder",
                "FieldKeys": "FID,FBillNo",
                "StartRow": 0,
                "Limit": 0,
            },
        )

        self.assertEqual(rows, [{"FID": 1, "FBillNo": "SO001"}])
        client.logout.assert_called_once_with(force=True)
        client.login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
