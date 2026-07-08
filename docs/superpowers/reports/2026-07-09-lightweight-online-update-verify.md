# 轻量在线更新验证报告

## 自动化验证

- `python -m ruff check src/version.py src/services/update_service.py src/updater.py src/gui/pages/settings_page.py create_deploy.py tests/test_update_service.py tests/test_updater_dry_run.py tests/test_release_package.py tests/test_gui_windows11_shell.py`：通过。
- `python -m pytest tests\test_update_service.py tests\test_updater_dry_run.py tests\test_release_package.py -q`：通过，29 passed。
- `python -m pytest tests\test_gui_windows11_shell.py -q -k "settings_page"`：通过，17 passed，268 deselected，1 个既有 `pythonjsonlogger` deprecation warning。

## dry-run 结论

- updater 拒绝 zip-slip 路径，覆盖 `../`、绝对路径和反斜杠穿越输入。（原因：防止更新包写出安装目录）
- updater 替换程序文件时保留 `config.local.ini`、`config.ini`、`config.ini.backup`、`logs/`、`backups/`，并兼容大小写变体。（原因：Windows 文件系统通常大小写不敏感）
- updater 安装完整包时会移除旧的非保护文件，避免新旧版本文件混用。（原因：完整包更新应以新包内容为准）
- updater 替换失败时会从备份恢复旧文件。（原因：安装失败后客户端必须保持可恢复）
- release zip 生成会排除本机配置和日志，包括大小写变体。（原因：避免覆盖现场配置或泄露敏感信息）

## SQL Server 影响

本变更不改 SQL Server 表结构，不执行 SQL 脚本，不写同步业务表。（原因：在线更新只替换客户端程序文件和发布元数据）

## 剩余风险

- 第一版未强制代码签名校验。（原因：当前最小可行方案以 HTTPS 和 SHA256 为基础，代码签名作为后续增强）
- 设置页检查更新当前在 UI 主线程同步执行，超时由 `UpdateService` 默认 5 秒控制。（原因：第一版保持实现最小，后续可迁移到后台线程提升体验）
- manifest 地址仍为内网示例地址，真实发布前需要替换为现场可访问的 HTTPS 静态地址。（原因：不同部署环境的内网域名不同）
