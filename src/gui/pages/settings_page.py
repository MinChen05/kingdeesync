"""Settings page with real config reading and saving."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.buttons import LoadingButton
from src.gui.components.common import FieldRow, SvgIconLabel
from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard
from src.gui.design_tokens import ColorTokens, SizeTokens, SpacingTokens, qcolor
from src.gui.feedback import UiFeedback
from src.gui.ui_text import ButtonText, LoadingText
from src.services.settings_service import settings_service

logger = logging.getLogger(__name__)


class SettingsPage(Win11PageScaffold):
    """System settings page with real config reading and saving."""

    def __init__(self, parent_gui, parent=None):
        self.gui = parent_gui
        super().__init__(
            title="系统设置",
            eyebrow="",
            subtitle="管理金蝶 API 与 SQL Server 的连接配置",
            parent=parent,
        )
        self.setProperty("page", "settings")
        self.set_hero_visible(False)
        self.hero_card.setVisible(False)
        self.primary_action_host.setVisible(False)
        self.summary_strip.setVisible(False)
        self._build_ui()
        self.load_config()

    def _build_ui(self) -> None:
        self._init_editors()

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)

        self.page_title = QLabel("系统设置")
        self.page_title.setProperty("ui", "st-page-title")
        title_layout.addWidget(self.page_title)
        title_layout.addStretch()

        self.btn_test = LoadingButton("测试连接")
        self.btn_test.setProperty("class", "secondary")
        self.btn_test.setFixedHeight(38)
        self.btn_test.clicked.connect(self.test_connections)
        title_layout.addWidget(self.btn_test)

        self.btn_save = LoadingButton("保存设置")
        self.btn_save.setProperty("class", "primary")
        self.btn_save.setFixedHeight(38)
        self.btn_save.clicked.connect(self.save_settings)
        title_layout.addWidget(self.btn_save)
        content_layout.addWidget(title_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setProperty("ui", "settings-scroll")

        scroll_body = QWidget()
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        main_row = QWidget()
        main_layout = QHBoxLayout(main_row)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        basic_card = Win11SectionCard("基础设置", "用于识别当前客户端与配置来源")
        basic_rows = [
            self._create_setting_row("系统名称", "用于标识本系统的名称", self._make_info_label("金蝶数据同步工具")),
            self._create_setting_row("配置来源", "当前读写的配置文件", self._make_info_label(settings_service.get_config_source_name())),
            self._create_setting_row("数据库类型", "当前同步使用的数据库类型", self._make_info_label(settings_service.get_database_type())),
        ]
        for row in basic_rows:
            basic_card.content_layout.addWidget(row)
        left_col.addWidget(basic_card)

        db_card = Win11SectionCard("SQL Server 连接", "同步写入时使用的目标数据库")
        db_rows = [
            self._create_setting_row("服务器地址", "SQL Server 服务器地址", self.db_host),
            self._create_setting_row("端口", "SQL Server 连接端口", self.db_port),
            self._create_setting_row("数据库名", "要连接的数据库名称", self.db_name),
            self._create_setting_row("用户名", "SQL Server 用户名", self.db_user),
            self._create_setting_row("密码", "SQL Server 密码", self.db_password),
        ]
        for row in db_rows:
            db_card.content_layout.addWidget(row)
        left_col.addWidget(db_card)
        left_col.addStretch()

        main_layout.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        api_card = Win11SectionCard("金蝶 API 连接", "同步拉取时使用的接口地址与账号")
        api_rows = [
            self._create_setting_row("登录地址", "金蝶云星空登录接口地址", self.login_url),
            self._create_setting_row("查询地址", "金蝶云星空查询接口地址", self.query_url),
            self._create_setting_row("账套 ID", "金蝶云星空账套 ID", self.acct_id),
            self._create_setting_row("用户名", "金蝶云星空 API 用户名", self.username),
            self._create_setting_row("密码", "金蝶云星空 API 密码", self.password),
        ]
        for row in api_rows:
            api_card.content_layout.addWidget(row)
        right_col.addWidget(api_card)

        security_card = Win11SectionCard("日志与安全", "密码不会回显，留空保存时保留原值")
        sec_rows = [
            self._create_setting_row("密码显示", "加载配置时不会显示已保存的明文密码", self._make_info_label("已脱敏")),
            self._create_setting_row("空密码策略", "密码框留空保存时继续使用原配置", self._make_info_label("保留原值")),
            self._create_setting_row("连接测试", "仅测试当前输入，不会自动保存配置", self._make_info_label("不保存")),
        ]
        for row in sec_rows:
            security_card.content_layout.addWidget(row)
        right_col.addWidget(security_card)
        right_col.addStretch()

        main_layout.addLayout(right_col, 1)
        scroll_layout.addWidget(main_row)

        tip_widget = QWidget()
        tip_layout = QHBoxLayout(tip_widget)
        tip_layout.setContentsMargins(16, 12, 16, 12)
        tip_layout.setSpacing(8)
        tip_icon = SvgIconLabel("info.svg", size=20, icon_size=18, color=ColorTokens.ACCENT_600)
        tip_icon.setProperty("ui", "st-tip-icon")
        tip_layout.addWidget(tip_icon)
        tip_text = QLabel("安全提示：密码和密钥会按配置进行脱敏处理，不会在界面或日志中展示明文。")
        tip_text.setProperty("ui", "st-tip-text")
        tip_text.setWordWrap(True)
        tip_layout.addWidget(tip_text, 1)
        scroll_layout.addWidget(tip_widget)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_body)
        content_layout.addWidget(scroll, 1)

        self.set_content(content_widget)

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

        self.login_url.setPlaceholderText("填写金蝶 API 登录地址")
        self.query_url.setPlaceholderText("填写金蝶 API 查询地址")
        self.acct_id.setPlaceholderText("请输入账套 ID")
        self.username.setPlaceholderText("请输入 WebAPI 用户名")
        self.password.setPlaceholderText("留空保留原密码")
        self.db_host.setPlaceholderText("例如：192.168.1.50")
        self.db_name.setPlaceholderText("请输入数据库名")
        self.db_user.setPlaceholderText("请输入数据库用户名")
        self.db_password.setPlaceholderText("留空保留原密码")

        for widget in (self.login_url, self.query_url, self.acct_id, self.username,
                       self.password, self.db_host, self.db_name, self.db_user, self.db_password):
            widget.setProperty("td", "win11-input")

    def _make_info_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("ui", "st-info-label")
        return label

    def _make_spinbox(self, value: int, min_val: int, max_val: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(value)
        spin.setFixedHeight(34)
        spin.setProperty("td", "win11-input")
        return spin

    def _create_setting_row(self, title_text: str, note_text: str, editor: QWidget) -> QWidget:
        row = QWidget()
        row.setProperty("ui", "st-setting-row")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(title_text)
        title.setProperty("ui", "st-setting-title")
        note = QLabel(note_text)
        note.setProperty("ui", "st-setting-note")
        text_col.addWidget(title)
        text_col.addWidget(note)
        layout.addLayout(text_col, 1)

        editor.setFixedHeight(34)
        layout.addWidget(editor)

        return row

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
            self.password.setPlaceholderText("留空保留原密码")

            db_cfg = snapshot.get("database", {})
            self.db_host.setText(str(db_cfg.get("host", "")))
            self.db_port.setValue(int(db_cfg.get("port", 1433) or 1433))
            self.db_name.setText(str(db_cfg.get("database", "")))
            self.db_user.setText(str(db_cfg.get("user", "")))
            self.db_password.clear()
            self.db_password.setPlaceholderText("留空保留原密码")
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
                UiFeedback.success(self, "保存成功", "系统设置已保存。")
        except Exception as exc:
            logger.error("Save settings failed: %s", exc)
            if show_feedback:
                UiFeedback.error(self, "保存失败", f"系统设置保存失败：\n{exc}")
                return
            raise
        finally:
            self.btn_save.set_loading(False)

    def test_connections(self) -> None:
        self.btn_test.set_loading(True, LoadingText.TEST)
        try:
            kd_ok, db_ok, message = settings_service.test_connections(self._collect_payload(), persist=False)

            if hasattr(self.gui, "_update_status_display"):
                self.gui._update_status_display(True, kd_ok)
                self.gui._update_status_display(False, db_ok)

            UiFeedback.info(self, "连接测试结果", message)
        except Exception as exc:
            logger.error("Test connections failed: %s", exc)
            UiFeedback.error(self, "测试失败", f"连接测试未完成：\n{exc}")
        finally:
            self.btn_test.set_loading(False)
