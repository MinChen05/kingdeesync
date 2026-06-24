from __future__ import annotations

from src.services.settings_service import SettingsService


def test_settings_service_test_connections_can_use_temporary_payload_without_saving(mocker) -> None:
    service = SettingsService()
    payload = {
        "kingdee": {"query_url": "https://query.example.com"},
        "database": {"host": "127.0.0.1"},
    }

    save_settings = mocker.patch.object(service, "save_settings")
    apply_runtime = mocker.patch.object(service, "apply_runtime_payload")
    mocker.patch("src.services.settings_service.kingdee_client.test_connection", return_value=True)
    mocker.patch("src.services.settings_service.mysql_manager.test_connection", return_value=False)

    kd_ok, db_ok, message = service.test_connections(payload, persist=False)

    assert kd_ok is True
    assert db_ok is False
    assert "金蝶: 成功" in message
    assert "数据库: 失败" in message
    save_settings.assert_not_called()
    apply_runtime.assert_called_once_with(payload)
