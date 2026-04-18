"""Settings page built on the shared Windows 11 page scaffold."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.buttons import LoadingButton
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
from src.gui.feedback import UiFeedback
from src.gui.ui_text import ButtonText, LoadingText
from src.services.settings_service import settings_service

logger = logging.getLogger(__name__)


class SettingsSummaryCard(Win11SummaryCard):
    """Compact summary card used by the settings overview row."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(title=title, value=value, subtitle=subtitle, parent=parent)
        self.subtitle_label.setProperty("ui", "win11-helper-text")

    def set_data(self, value: str, subtitle: str | None = None) -> None:
        self.set_value(value)
        if subtitle is not None:
            self.set_subtitle(subtitle)


class SettingsPage(Win11PageScaffold):
    """System connection settings page."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        self._setting_rows: list[tuple[QFrame, QBoxLayout, QWidget]] = []
        super().__init__(
            title="系统设置",
            eyebrow="设置",
            subtitle="在统一的 Windows 11 页面结构中维护金蝶与 SQL Server 连接参数。",
            parent=parent,
        )
        self.setProperty("page", "settings")
        self.setup_ui()
        self.load_config()

    def setup_ui(self) -> None:
        self._init_editors()
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.btn_test)
        self.add_primary_action(self.btn_save)
        self.set_content(self._create_scroll_content())
        self._apply_responsive_rows()

    def _build_hero(self) -> None:
        meta_widget = QWidget()
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self.hero_badge = QLabel("连接配置")
        self.hero_badge.setProperty("ui", "win11-status-chip")
        self.hero_badge.setProperty("tone", "info")

        self.hero_source = QLabel("配置来源：加载中...")
        self.hero_source.setProperty("ui", "win11-meta-text")
        self.hero_source.setWordWrap(True)

        meta_layout.addWidget(self.hero_badge, 0, Qt.AlignmentFlag.AlignLeft)
        meta_layout.addWidget(self.hero_source)

        self.btn_test = LoadingButton(ButtonText.TEST_CONNECTION)
        self.btn_test.setProperty("class", "secondary")
        self.btn_test.setFixedHeight(36)
        self.btn_test.clicked.connect(self.test_connections)

        self.btn_save = LoadingButton(ButtonText.SAVE_SETTINGS)
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setFixedHeight(36)
        self.btn_save.clicked.connect(self.save_settings)

        self.add_hero_widget(meta_widget)

    def _build_summary_strip(self) -> None:
        self.summary_source = SettingsSummaryCard("配置来源", "--", "当前正在使用的配置文件来源。")
        self.summary_db = SettingsSummaryCard("目标数据库", "--", "当前保存的目标数据库类型。")
        self.summary_flow = SettingsSummaryCard("推荐流程", "先保存后测试", "执行同步前请先验证两个连接。")

        for card in (self.summary_source, self.summary_db, self.summary_flow):
            self.add_summary_card(card)

    def _create_scroll_content(self) -> QScrollArea:
        scroll = self.create_scroll_container("settings_scroll")

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(
            self._create_group_card(
                "金蝶 API",
                "维护用于 WebAPI 访问的登录地址、查询地址与账号凭据。",
                [
                    self._create_setting_row("登录地址", "用于身份认证的接口地址。", self.login_url),
                    self._create_setting_row("查询地址", "用于业务数据查询的接口地址。", self.query_url),
                    self._create_setting_row("账套 ID", "金蝶账套标识。", self.acct_id),
                    self._create_setting_row("用户名", "用于金蝶 WebAPI 登录的账号。", self.username),
                    self._create_setting_row("密码", "留空将保持已保存密码不变。", self.password, last=True),
                ],
            )
        )
        layout.addWidget(
            self._create_group_card(
                "SQL Server 数据库",
                "维护同步流程使用的目标数据库连接信息。",
                [
                    self._create_setting_row("主机", "数据库主机地址或实例名。", self.db_host),
                    self._create_setting_row("端口", "SQL Server 默认端口为 1433。", self.db_port),
                    self._create_setting_row("数据库名", "目标业务数据库名称。", self.db_name),
                    self._create_setting_row("用户名", "数据库登录账号。", self.db_user),
                    self._create_setting_row(
                        "密码",
                        "留空将保持已保存数据库密码不变。",
                        self.db_password,
                        last=True,
                    ),
                ],
            )
        )
        layout.addWidget(self._create_note_card())
        layout.addStretch(1)

        scroll.setWidget(page)
        return scroll

    def _init_editors(self) -> None:
        self.login_url = QLineEdit()
        self.query_url = QLineEdit()
        self.acct_id = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.db_host = QLineEdit()
        self.db_port = QSpinBox()
        self.db_port.setRange(1, 65535)
        self.db_name = QLineEdit()
        self.db_user = QLineEdit()
        self.db_password = QLineEdit()
        self.db_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.login_url.setPlaceholderText("例如：https://api.example.com/K3Cloud/Kingdee.BOS.WebApi.ServicesStub.AuthService.ValidateUser.common.kdsvc")
        self.query_url.setPlaceholderText("例如：https://api.example.com/K3Cloud/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc")
        self.acct_id.setPlaceholderText("请输入账套 ID")
        self.username.setPlaceholderText("请输入 WebAPI 用户名")
        self.password.setPlaceholderText("如需更新密码请填写；留空则保持不变")
        self.db_host.setPlaceholderText("例如：127.0.0.1 或 localhost\\SQLEXPRESS")
        self.db_name.setPlaceholderText("请输入数据库名")
        self.db_user.setPlaceholderText("请输入数据库用户名")
        self.db_password.setPlaceholderText("如需更新数据库密码请填写；留空则保持不变")

        widgets: tuple[QWidget, ...] = (
            self.login_url,
            self.query_url,
            self.acct_id,
            self.username,
            self.password,
            self.db_host,
            self.db_port,
            self.db_name,
            self.db_user,
            self.db_password,
        )
        for widget in widgets:
            widget.setProperty("td", "win11-input")

    def _create_group_card(self, title_text: str, subtitle_text: str, rows: list[QWidget]) -> Win11SectionCard:
        card = Win11SectionCard(title_text, subtitle_text)
        for row in rows:
            card.content_layout.addWidget(row)
        return card

    def _create_setting_row(self, title_text: str, note_text: str, editor: QWidget, *, last: bool = False) -> QFrame:
        row = QFrame()
        row.setProperty("ui", "win11-setting-row")
        row.setProperty("last", last)

        layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, row)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(14)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(3)

        title = QLabel(title_text)
        title.setProperty("ui", "win11-row-title")

        note = QLabel(note_text)
        note.setProperty("ui", "win11-row-note")
        note.setWordWrap(True)

        text_wrap.addWidget(title)
        text_wrap.addWidget(note)

        layout.addLayout(text_wrap, 1)

        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if isinstance(editor, QSpinBox):
            editor.setFixedWidth(140)
        else:
            editor.setMinimumWidth(0)
        layout.addWidget(editor, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._setting_rows.append((row, layout, editor))
        return row

    def _create_note_card(self) -> Win11SectionCard:
        card = Win11SectionCard(
            "操作说明",
            "请先保存设置，再测试两个连接，最后到“同步”页面发起任务。",
        )
        note = QLabel(
            "本页仅更新界面文案与布局呈现，配置加载、保存与连接测试行为保持不变。"
        )
        note.setProperty("ui", "win11-helper-text")
        note.setWordWrap(True)
        card.content_layout.addWidget(note)
        return card

    def _apply_responsive_rows(self) -> None:
        compact = self.width() <= 1366
        self.setProperty("layoutMode", "compact" if compact else "wide")
        for row, layout, editor in self._setting_rows:
            layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
            if isinstance(editor, QSpinBox):
                editor.setFixedWidth(120 if compact else 140)
            else:
                editor.setMinimumWidth(0)
                editor.setMaximumWidth(16777215 if compact else 420)
            row_style = row.style()
            if row_style is not None:
                row_style.unpolish(row)
                row_style.polish(row)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_responsive_rows()
        super().resizeEvent(event)

    def _collect_payload(self):
        return {
            "kingdee": {
                "login_url": self.login_url.text().strip(),
                "query_url": self.query_url.text().strip(),
                "acct_id": self.acct_id.text().strip(),
                "username": self.username.text().strip(),
                "password": self.password.text().strip(),
            },
            "database": {
                "host": self.db_host.text().strip(),
                "port": self.db_port.value(),
                "database": self.db_name.text().strip(),
                "user": self.db_user.text().strip(),
                "password": self.db_password.text().strip(),
            },
        }

    def load_config(self) -> None:
        try:
            snapshot = settings_service.get_settings_snapshot()
            kd_cfg = snapshot.get("kingdee", {})
            self.login_url.setText(str(kd_cfg.get("login_url", "")))
            self.query_url.setText(str(kd_cfg.get("query_url", "")))
            self.acct_id.setText(str(kd_cfg.get("acct_id", "")))
            self.username.setText(str(kd_cfg.get("username", "")))
            self.password.clear()
            self.password.setPlaceholderText("如需更新密码请填写；留空则保持不变")

            db_cfg = snapshot.get("database", {})
            self.db_host.setText(str(db_cfg.get("host", "")))
            self.db_port.setValue(int(db_cfg.get("port", 1433) or 1433))
            self.db_name.setText(str(db_cfg.get("database", "")))
            self.db_user.setText(str(db_cfg.get("user", "")))
            self.db_password.clear()
            self.db_password.setPlaceholderText("如需更新数据库密码请填写；留空则保持不变")

            config_source_name = settings_service.get_config_source_name()
            config_source = settings_service.get_config_source()
            database_type = settings_service.get_database_type()

            self.hero_source.setText(f"配置来源：{config_source}")
            self.summary_source.set_data(config_source_name, f"当前来源路径：{config_source}")
            self.summary_db.set_data(database_type, "当前默认业务数据库仍为 SQL Server。")
        except Exception as exc:
            logger.error("Load settings failed: %s", exc)
            UiFeedback.error(self, "加载失败", f"无法加载设置：\n{exc}")

    def load_settings(self) -> None:
        """Compatibility with shell switch callback."""
        self.load_config()

    def save_settings(self, show_feedback: bool = True) -> None:
        self.btn_save.set_loading(True, LoadingText.SAVE)
        try:
            settings_service.save_settings(self._collect_payload())
            self.load_config()
            if show_feedback:
                UiFeedback.success(self, "保存成功", "系统设置已成功保存。")
        except Exception as exc:
            logger.error("Save settings failed: %s", exc)
            if show_feedback:
                UiFeedback.error(self, "保存失败", f"无法保存设置：\n{exc}")
                return
            raise
        finally:
            self.btn_save.set_loading(False)

    def test_connections(self) -> None:
        self.btn_test.set_loading(True, LoadingText.TEST)
        try:
            kd_ok, db_ok, message = settings_service.test_connections(self._collect_payload())

            if hasattr(self.gui, "_update_status_display"):
                self.gui._update_status_display(True, kd_ok)
                self.gui._update_status_display(False, db_ok)

            self.summary_flow.set_data(
                "连接就绪" if kd_ok and db_ok else "需要处理",
                "两个连接测试均通过。" if kd_ok and db_ok else "请先修复失败连接，再执行同步。",
            )
            self.hero_badge.setText("连接正常" if kd_ok and db_ok else "连接异常")
            self.hero_badge.setProperty("tone", "success" if kd_ok and db_ok else "danger")
            style = self.hero_badge.style()
            if style is not None:
                style.unpolish(self.hero_badge)
                style.polish(self.hero_badge)
            UiFeedback.info(self, "连接测试结果", message)
        except Exception as exc:
            logger.error("Test connections failed: %s", exc)
            UiFeedback.error(self, "测试失败", f"无法测试连接：\n{exc}")
        finally:
            self.btn_test.set_loading(False)
