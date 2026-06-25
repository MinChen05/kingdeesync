#!/usr/bin/env python
import json
import logging
import os
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

# Must be set before importing Qt to allow headless CI execution.
# Use `offscreen` explicitly per Task 1 requirements.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Helps reduce GPU/driver flakiness in Windows CI in some environments.
os.environ.setdefault("QT_OPENGL", "software")

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        # Qt attributes must be set before constructing QApplication.
        QApplication.setAttribute(Qt.AA_Use96Dpi, True)
        app = QApplication(["kingdee-unittests"])
    app.setQuitOnLastWindowClosed(False)
    return app


def cleanup_widget(widget) -> None:
    widget.close()
    widget.deleteLater()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


class QtAppTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = get_qapp()


class Win11PageScaffoldSmokeTests(QtAppTestCase):

    def test_scaffold_exposes_required_structural_markers(self) -> None:
        from src.gui.components.page_shell import Win11PageScaffold

        scaffold = Win11PageScaffold(title="Demo")

        self.assertEqual(scaffold.property("ui"), "win11-page")

        hero_card = scaffold.findChild(QObject, "page_hero_card")
        self.assertIsNotNone(hero_card)
        self.assertEqual(hero_card.property("ui"), "win11-hero-card")

        hero_title = scaffold.findChild(QObject, "page_hero_title")
        self.assertIsNotNone(hero_title)

        summary_strip = scaffold.findChild(QObject, "page_summary_strip")
        self.assertIsNotNone(summary_strip)
        self.assertEqual(summary_strip.property("ui"), "win11-summary-strip")

        content_host = scaffold.findChild(QObject, "page_content_host")
        self.assertIsNotNone(content_host)
        self.assertEqual(content_host.property("ui"), "win11-content-host")

    def test_scaffold_layout_spacing_uses_tokens(self) -> None:
        from src.gui.components.page_shell import Win11PageScaffold, Win11SectionCard, Win11SummaryCard
        from src.gui.design_tokens import SpacingTokens

        scaffold = Win11PageScaffold(title="Demo")
        self.addCleanup(cleanup_widget, scaffold)
        self.assertEqual(scaffold.layout().spacing(), SpacingTokens.MD)

        section = Win11SectionCard("Title", "Sub")
        self.addCleanup(cleanup_widget, section)
        self.assertEqual(section.layout().spacing(), SpacingTokens.MD)

        summary = Win11SummaryCard("T", "V")
        self.addCleanup(cleanup_widget, summary)
        self.assertEqual(summary.layout().spacing(), SpacingTokens.XS)

    def test_set_content_clears_existing_layout_items(self) -> None:
        from src.gui.components.page_shell import Win11PageScaffold

        scaffold = Win11PageScaffold(title="Demo")
        layout = scaffold.content_host.layout()
        self.assertIsNotNone(layout)

        # Include a nested layout item to ensure set_content clears non-widget items too.
        old_label = QLabel("old")
        sublayout = QVBoxLayout()
        sublayout.addWidget(old_label)
        layout.addLayout(sublayout)
        layout.addStretch(1)

        new_widget = QLabel("new")
        scaffold.set_content(new_widget)

        self.assertEqual(layout.count(), 1)
        self.assertIs(layout.itemAt(0).widget(), new_widget)
        self.assertIsNone(old_label.parent())


class Win11SummaryCardSmokeTests(QtAppTestCase):
    def test_summary_card_exposes_ui_property(self) -> None:
        from src.gui.components.page_shell import Win11SummaryCard

        card = Win11SummaryCard(title="Total", value="122")
        self.assertEqual(card.property("ui"), "win11-summary-card")


class Win11ResponsiveShellSmokeTests(QtAppTestCase):
    def test_scaffold_exposes_primary_action_bar_and_scroll_factory(self) -> None:
        from src.gui.components.page_shell import Win11PageScaffold

        scaffold = Win11PageScaffold(title="Demo")
        self.addCleanup(cleanup_widget, scaffold)

        primary_actions = scaffold.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertEqual(primary_actions.property("ui"), "win11-primary-action-bar")

        action = QLabel("Run")
        scaffold.add_primary_action(action)
        scaffold.show()
        self._app.processEvents()
        self.assertTrue(primary_actions.isVisible())

        scroll = scaffold.create_scroll_container("demo_scroll")
        self.assertEqual(scroll.objectName(), "demo_scroll")
        self.assertEqual(scroll.property("ui"), "win11-page-scroll")

    def test_scaffold_hides_redundant_hero_card_by_default(self) -> None:
        from src.gui.components.page_shell import Win11PageScaffold

        scaffold = Win11PageScaffold(title="Demo")
        self.addCleanup(cleanup_widget, scaffold)

        hero_card = scaffold.findChild(QObject, "page_hero_card")
        self.assertIsNotNone(hero_card)

        scaffold.show()
        self._app.processEvents()

        self.assertFalse(hero_card.isVisible())

    def test_main_shell_compacts_sidebar_at_1266x768(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        window.resize(1266, 768)
        window.show()
        self._app.processEvents()

        self.assertFalse(window.sidebar_compact)
        # sidebar_status_card removed — sidebar now has brand + icon nav + footer

    def test_main_shell_sidebar_matches_target_geometry(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)
        window.resize(1440, 900)
        window.show()
        self._app.processEvents()

        self.assertEqual(window.sidebar_expanded_width, 240)
        self.assertEqual(window.sidebar.maximumWidth(), 240)
        self.assertEqual(window.sidebar.minimumWidth(), 240)
        self.assertTrue(window.sidebar_brand.isVisible())
        self.assertEqual(window.sidebar_brand.maximumHeight(), 88)
        self.assertEqual(window.sidebar_nav_container.layout().contentsMargins().top(), 20)
        self.assertEqual(window.sidebar_nav_container.layout().contentsMargins().left(), 18)
        self.assertEqual(window.sidebar_nav_container.layout().spacing(), 9)
        self.assertEqual(window.nav_buttons["dashboard"].height(), 48)
        self.assertEqual(window.nav_buttons["dashboard"].iconSize().width(), 20)
        self.assertEqual(window.sidebar_collapse_btn.objectName(), "sidebar_collapse_btn")
        self.assertEqual(window.sidebar_collapse_btn.property("icon-source"), "menu_fold.svg")
        self.assertFalse(window.sidebar_collapse_btn.icon().isNull())

    def test_main_shell_compacts_sidebar_below_1024(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        window.resize(1024, 768)
        window.show()
        self._app.processEvents()

        self.assertTrue(window.sidebar_compact)
        self.assertLessEqual(window.sidebar.maximumWidth(), 120)
        # sidebar_status_card removed


class Win11DashboardAndSyncResponsiveTests(QtAppTestCase):
    def test_dashboard_uses_primary_action_bar_and_target_structure(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        # 目标稿核心区域存在性断言（无独立 action bar，刷新按钮在 hero 右侧）
        self.assertTrue(page.refresh_btn.isVisible())
        self.assertEqual(page.refresh_btn.width(), 96)

        # 5 个指标卡
        cards = page._status_cards
        self.assertEqual(cards.card_count.title_label.text(), "今日同步次数")
        self.assertEqual(cards.card_rate.title_label.text(), "成功率")
        self.assertEqual(cards.card_fail.title_label.text(), "失败任务")
        self.assertEqual(cards.card_pending.title_label.text(), "待处理异常")
        self.assertEqual(cards.card_duration.title_label.text(), "平均耗时")

        # 同步趋势折线图
        self.assertIsNotNone(page.trend_chart)
        self.assertIsNotNone(page.trend_card)

        # 系统健康卡
        self.assertIsNotNone(page.health_card)

        # 最近同步记录表格
        self.assertIsNotNone(page.recent_table)
        self.assertIsNotNone(page.recent_card)

        # 风险提醒
        self.assertIsNotNone(page.risk_card)
        self.assertIsNotNone(page.risk_items)

    def test_sync_page_keeps_primary_actions_visible_and_stacks_workspace(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertTrue(page.test_conn_btn.isVisible())
        self.assertTrue(page.start_sync_btn.isVisible())
        self.assertEqual(page.start_sync_btn.height(), 28)
        self.assertGreaterEqual(primary_actions.minimumHeight(), 58)
        self.assertEqual(page.launchpad_core.layout().direction(), QHBoxLayout.Direction.LeftToRight)
        self.assertFalse(hasattr(page, "log_card"))

    def test_sync_page_uses_compact_execution_metric_cards(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.exec_count_card.property("ui"), "win11-metric-card")
        self.assertEqual(page.exec_time_card.property("ui"), "win11-metric-card")
        self.assertEqual(page.exec_rate_card.property("ui"), "win11-metric-card")
        self.assertGreaterEqual(page.exec_count_card.minimumHeight(), 120)
        self.assertIsNotNone(page.exec_count_card.findChild(QFrame))
        self.assertEqual(page.exec_count_card.title_label.text(), "已同步记录")
        self.assertEqual(page.exec_count_card.value_label.text(), "0")

        page.exec_count_card.set_data("42", "test note")
        self.assertEqual(page.exec_count_card.value_label.text(), "42")
        self.assertEqual(page.exec_count_card.note_label.text(), "test note")
        self.assertIs(page.exec_count_card.note_label.parent(), page.exec_count_card)
        self.assertFalse(page.exec_count_card.note_label.isVisible())

        page.reset_stats()
        self.assertEqual(page.exec_rate_card.value_label.text(), "运行中")
        self.assertFalse(page.exec_count_card.note_label.isVisible())

    def test_sync_page_uses_setting_rows_for_config(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        field_rows = [row for row in page.findChildren(QFrame) if row.property("ui") == "win11-setting-row"]
        self.assertGreaterEqual(len(field_rows), 2)
        for row in field_rows:
            self.assertEqual(row.property("ui"), "win11-setting-row")

        last_rows = [r for r in field_rows if r.property("last")]
        self.assertEqual(len(last_rows), 1)

    def test_sync_page_visual_alignment_structure(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.objectName(), "sync_execution_page")
        self.assertTrue(page.hero_card.isVisible())
        self.assertEqual(page.hero_title.text(), "同步执行")
        self.assertEqual(page.hero_card.maximumHeight(), 88)
        self.assertGreaterEqual(page.hero_title.minimumHeight(), 42)
        self.assertGreaterEqual(page.summary_strip.minimumHeight(), 80)
        self.assertEqual(page.config_container.objectName(), "sync_config_column")
        self.assertEqual(page.monitor_container.objectName(), "sync_monitor_column")

        sections = page.findChildren(QFrame)
        section_markers = {section.property("sync-section") for section in sections}
        self.assertIn("config", section_markers)
        self.assertIn("execution", section_markers)
        self.assertIn("preflight", section_markers)
        self.assertNotIn("log", section_markers)
        self.assertGreaterEqual(page._progress_card.minimumHeight(), 76)


class Win11SettingsAndFormsResponsiveTests(QtAppTestCase):
    def test_settings_page_keeps_actions_visible_and_rows_compact_at_1266x768(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.btn_test.isVisible())
        self.assertTrue(page.btn_save.isVisible())

    def test_settings_page_uses_field_rows(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertIsNotNone(page.login_url)
        self.assertIsNotNone(page.query_url)
        self.assertIsNotNone(page.acct_id)
        self.assertIsNotNone(page.username)
        self.assertIsNotNone(page.password)
        self.assertIsNotNone(page.db_host)
        self.assertIsNotNone(page.db_name)
        self.assertIsNotNone(page.db_user)
        self.assertIsNotNone(page.db_password)

    def test_settings_page_sync_mode_options_do_not_show_legacy_full_text(self) -> None:
        from PySide6.QtWidgets import QComboBox

        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        combo_texts = [
            combo.itemText(index)
            for combo in page.findChildren(QComboBox)
            for index in range(combo.count())
        ]
        self.assertNotIn("全量同步", combo_texts)
        self.assertNotIn("完全同步", combo_texts)
        self.assertNotIn("增量同步", combo_texts)

    def test_settings_page_only_shows_persisted_editors(self) -> None:
        from PySide6.QtWidgets import QComboBox

        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.findChildren(QComboBox), [])
        self.assertFalse(page.login_url.isHidden())
        self.assertFalse(page.query_url.isHidden())
        self.assertFalse(page.db_port.isHidden())

    def test_settings_page_layout_uses_tokens(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.btn_test.height(), 28)
        self.assertEqual(page.btn_save.height(), 28)

    def test_settings_page_1266x768_integration(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.btn_test.isVisible())
        self.assertTrue(page.btn_save.isVisible())
        self.assertIsNotNone(page.login_url)
        self.assertIsNotNone(page.db_host)

    def test_settings_page_query_url_and_db_port_visible_and_in_payload(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={
                "kingdee": {"login_url": "https://api.test.com", "query_url": "https://query.test.com", "acct_id": "100"},
                "database": {"host": "192.168.1.1", "port": 1422, "database": "TestDB"},
            },
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertIsNotNone(page.query_url)
        self.assertIsNotNone(page.db_port)
        self.assertEqual(page.query_url.text(), "https://query.test.com")
        self.assertEqual(page.db_port.value(), 1422)

        payload = page._collect_payload()
        self.assertEqual(payload["kingdee"]["login_url"], "https://api.test.com")
        self.assertEqual(payload["kingdee"]["query_url"], "https://query.test.com")
        self.assertEqual(payload["database"]["port"], 1422)

    def test_settings_page_test_connection_does_not_save_settings(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        with (
            patch("src.gui.pages.settings_page.settings_service.test_connections", return_value=(True, True, "ok")) as test_connections,
            patch("src.gui.pages.settings_page.settings_service.save_settings") as save_settings,
            patch("src.gui.pages.settings_page.UiFeedback.info"),
        ):
            page.test_connections()

        test_connections.assert_called_once_with(page._collect_payload(), persist=False)
        save_settings.assert_not_called()

    def test_settings_page_test_connection_updates_shell_without_legacy_status_widgets(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)
        page = window.pages["settings"]

        self.assertFalse(hasattr(window, "kd_status_icon"))
        with (
            patch(
                "src.gui.pages.settings_page.settings_service.test_connections",
                return_value=(True, False, "金蝶连接成功，数据库连接失败"),
            ),
            patch("src.gui.pages.settings_page.UiFeedback.info"),
        ):
            page.test_connections()

        self.assertTrue(window.kd_connected)
        self.assertFalse(window.db_connected)
        self.assertEqual(window.topbar_conn_value.text(), "部分连接")
        self.assertTrue(page.btn_test.isEnabled())

    def test_forms_page_prioritizes_list_height_and_top_actions_at_1266x768(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertFalse(hasattr(page, "btn_save"))
        self.assertFalse(hasattr(page, "btn_import"))
        self.assertTrue(page.btn_refresh_config.isVisible())
        self.assertTrue(page.search_box.isVisible())

    def test_forms_page_uses_only_form_search_and_status_filters(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        filter_labels = [
            w.text()
            for w in page.findChildren(QLabel)
            if w.property("ui") == "fm-filter-label"
        ]
        self.assertEqual(filter_labels, ["表单名称：", "映射状态："])

    def test_forms_page_shows_validation_as_summary_not_full_card(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        validation_cards = [w for w in page.findChildren(QFrame) if w.property("ui") == "fm-validation-summary"]
        self.assertEqual(len(validation_cards), 1)
        self.assertLessEqual(validation_cards[0].height(), 56)

    def test_forms_page_final_spacing_is_compact(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        content = page.findChild(QWidget, "forms_content")
        self.assertIsNotNone(content)
        self.assertEqual(content.layout().spacing(), 10)
        self.assertEqual(page.search_box.minimumWidth(), 260)
        self.assertEqual(page.search_box.maximumWidth(), 16777215)

        validation_cards = [w for w in page.findChildren(QFrame) if w.property("ui") == "fm-validation-summary"]
        self.assertEqual(len(validation_cards), 1)
        self.assertEqual(validation_cards[0].height(), 48)

    def test_forms_page_filter_bar_is_compact_and_integrated(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        filter_bar = next(w for w in page.findChildren(QFrame) if w.property("ui") == "fm-filter-bar")
        labels = [w for w in page.findChildren(QLabel) if w.property("ui") == "fm-filter-label"]

        self.assertEqual(filter_bar.height(), 76)
        self.assertEqual([label.text() for label in labels], ["表单名称：", "映射状态："])
        self.assertEqual(page.combo_form.height(), 40)
        self.assertEqual(page.combo_status.height(), 40)
        self.assertEqual(page.search_box.height(), 40)
        combo_frames = [w for w in page.findChildren(QFrame) if w.property("ui") == "fm-filter-combo-frame"]
        self.assertEqual(len(combo_frames), 2)
        combo_bottom_lines = [w for w in page.findChildren(QFrame) if w.property("ui") == "fm-filter-combo-bottom-line"]
        self.assertEqual(len(combo_bottom_lines), 2)
        self.assertEqual(combo_frames[0].width(), 240)
        self.assertEqual(combo_frames[1].width(), 200)
        self.assertEqual(page.combo_form.width(), 228)
        self.assertEqual(page.combo_status.width(), 198)
        self.assertTrue(all(frame.height() >= 44 for frame in combo_frames))
        self.assertEqual(combo_frames[0].layout().contentsMargins().bottom(), 1)
        self.assertLess(page.combo_form.height(), combo_frames[0].height())
        self.assertLess(page.combo_status.height(), combo_frames[1].height())
        self.assertGreaterEqual(page.search_box.minimumWidth(), 260)
        self.assertEqual(page.search_box.property("ui"), "fm-filter-search")
        self.assertEqual(page.btn_reset_filter.text(), "重置")
        self.assertEqual(page.btn_apply_filter.text(), "筛选")

        css = Path("assets/styles.css").read_text(encoding="utf-8")
        self.assertIn('QWidget[page="forms"] QComboBox[ui="fm-filter-input"]', css)
        self.assertIn('QWidget[page="forms"] QLineEdit[ui="fm-filter-search"]', css)

    def test_forms_page_filter_reset_button_clears_controls(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": []}),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        page.combo_form.setCurrentText("Customers")
        page.combo_status.setCurrentText("未映射")
        page.search_box.setText("customer")
        page.btn_reset_filter.click()

        self.assertEqual(page.combo_form.currentText(), "请选择表单")
        self.assertEqual(page.combo_status.currentText(), "全部状态")
        self.assertEqual(page.search_box.text(), "")

    def test_forms_page_validation_action_fits_copy(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={"Customers": "t_customer"}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": ["Customers"]}),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        text_width = page.btn_view_diagnostics.fontMetrics().horizontalAdvance(page.btn_view_diagnostics.text())
        self.assertGreaterEqual(page.btn_view_diagnostics.width(), text_width + 28)
        self.assertGreaterEqual(page.btn_view_diagnostics.height(), 22)

    def test_forms_page_populates_real_forms_and_filters_list(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.combo_form.itemText(1), "Customers")
        self.assertEqual(page.combo_form.itemText(2), "Orders")

        page.combo_status.setCurrentText("未映射")
        self._app.processEvents()
        self.assertEqual([item.form_name for item in page._visible_form_items], ["Orders"])

        page.search_box.setText("customer")
        page.combo_status.setCurrentText("全部状态")
        self._app.processEvents()
        self.assertEqual([item.form_name for item in page._visible_form_items], ["Customers"])

    def test_forms_page_empty_table_mapping_shows_empty_list_without_static_forms(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": []}),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.combo_form.count(), 1)
        self.assertEqual(page.combo_form.itemText(0), "请选择表单")
        self.assertEqual(page._visible_form_items, [])
        self.assertEqual(page.field_table.table.rowCount(), 0)
        self.assertNotIn("销售订单", [page.combo_form.itemText(index) for index in range(page.combo_form.count())])
        self.assertEqual(page.detail_title.text(), "字段映射详情")

    def test_forms_page_selecting_form_updates_title_and_real_field_rows(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        field_mappings = {
            "t_customer": {
                "CustomerName": {"sources": ["FCustomerName"], "type": "varchar(80)", "default": ""},
            },
            "t_order": {
                "BillNo": {"sources": ["FBillNo"], "type": "varchar(50)", "default": "required"},
            },
        }
        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers", "Orders"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value=field_mappings),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.detail_title.text(), "字段映射详情（Customers）")
        self.assertEqual(page.field_table.table.item(0, 0).text(), "FCustomerName")

        page.select_form("Orders")
        self._app.processEvents()

        self.assertEqual(page.detail_title.text(), "字段映射详情（Orders）")
        self.assertEqual(page.field_table.table.item(0, 0).text(), "FBillNo")

    def test_forms_page_empty_field_mapping_shows_empty_state_without_static_rows(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Warehouse": "bd_stock"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Warehouse"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.detail_title.text(), "字段映射详情（Warehouse）")
        self.assertEqual(page.field_table.table.rowCount(), 0)
        self.assertTrue(page.field_table._empty_label.isVisible())
        self.assertEqual(page.field_table._empty_label.text(), "当前表单还没有字段映射配置")

    def test_forms_page_stats_and_validation_summary_use_real_config_data(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        field_mappings = {
            "t_customer": {
                "CustomerName": {"sources": ["FCustomerName"], "type": "varchar(80)", "default": ""},
                "CustomerId": {"sources": ["FCustomerID"], "type": "int", "default": "required"},
            },
            "t_order": {
                "BillNo": {"sources": ["FBillNo"], "type": "varchar(50)", "default": "required"},
            },
        }
        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value=field_mappings),
            patch("src.gui.pages.forms_page._latest_config_mtime", return_value="2026-06-24"),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.stat_values["forms"].text(), "2")
        self.assertEqual(page.stat_values["fields"].text(), "2")
        self.assertEqual(page.stat_values["missing"].text(), "1")
        self.assertEqual(page.stat_values["updated"].text(), "2026-06-24")
        self.assertEqual(page.validation_summary_text.text(), "字段缺失 1 · 类型不匹配 0 · 可自动修复 0")

    def test_forms_page_refresh_config_button_reloads_without_saving(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer"},
            ) as get_mapping,
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
            patch("src.gui.pages.forms_page.UiFeedback.info") as info_feedback,
        ):
            page = FormConfigPage(gui)
            self.addCleanup(cleanup_widget, page)
            page.btn_refresh_config.click()

        self.assertGreaterEqual(get_mapping.call_count, 2)
        messages = [call.args[2] for call in info_feedback.call_args_list]
        self.assertIn("已重新加载最新表单映射配置。", messages)

    def test_forms_page_diagnostics_link_navigates_to_diagnostics(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        calls = []
        gui = SimpleNamespace(switch_to_page=lambda page_id: calls.append(page_id))
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.btn_view_diagnostics.click()

        self.assertEqual(calls, ["diagnostics"])


class Win11ScheduleAndHistoryResponsiveTests(QtAppTestCase):
    def test_schedule_page_stacks_workspace_and_keeps_actions_visible(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.btn_stop.isVisible())
        self.assertTrue(page.btn_save.isVisible())

    def test_history_page_reflows_filters_and_keeps_pagination_visible(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertFalse(primary_actions.isVisible())
        self.assertEqual(page._filter_panel._grid.property("compact"), False)
        self.assertTrue(page.btn_query.isVisible())
        self.assertTrue(page.btn_prev.isVisible())
        self.assertTrue(page.btn_next.isVisible())


class Win11PrimaryPagesSmokeTests(QtAppTestCase):
    def build_schedule_page(self):
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        return SchedulePage(gui)

    def assert_uses_win11_scaffold(self, page) -> None:
        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("ui"), "win11-page")

        hero_card = page.findChild(QObject, "page_hero_card")
        self.assertIsNotNone(hero_card)

        summary_strip = page.findChild(QObject, "page_summary_strip")
        self.assertIsNotNone(summary_strip)

    def test_dashboard_page_uses_win11_scaffold(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.assert_uses_win11_scaffold(page)

    def test_sync_page_uses_win11_scaffold(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.assert_uses_win11_scaffold(page)

    def test_sync_page_accepts_optional_parent(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        parent = QWidget()
        self.addCleanup(cleanup_widget, parent)
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui, parent=parent)

        self.assertIs(page.parentWidget(), parent)
        self.assert_uses_win11_scaffold(page)

    def test_settings_page_uses_win11_scaffold(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={
                "kingdee": {
                    "login_url": "https://login.example.com",
                    "query_url": "https://query.example.com",
                    "acct_id": "acct-001",
                    "username": "demo",
                    "password": "secret",
                },
                "database": {
                    "host": "db.example.com",
                    "port": 1422,
                    "database": "kingdee",
                    "user": "sa",
                    "password": "secret",
                },
            },
        ):
            page = SettingsPage(gui)

        self.assert_uses_win11_scaffold(page)

    def test_settings_page_save_settings_handles_ui_errors_without_reraising(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={
                "kingdee": {},
                "database": {},
            },
        ):
            page = SettingsPage(gui)
        self.addCleanup(cleanup_widget, page)

        with (
            patch("src.gui.pages.settings_page.settings_service.save_settings", side_effect=RuntimeError("boom")),
            patch("src.gui.pages.settings_page.UiFeedback.error") as error_feedback,
        ):
            page.save_settings()

        error_feedback.assert_called_once()
        self.assertFalse(page.btn_save._is_loading)

    def test_forms_page_uses_win11_scaffold(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.assert_uses_win11_scaffold(page)

    def test_forms_page_load_forms_rebuilds_rows_without_stale_layout_items(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                side_effect=[
                    {"Customers": "t_customer"},
                    {"Customers": "t_customer", "Orders": "t_order"},
                ],
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers", "Orders"]},
            ),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
            patch("src.gui.pages.forms_page.UiFeedback.info"),
        ):
            page = FormConfigPage(gui)
            self.addCleanup(cleanup_widget, page)
            page.refresh_data()

        self.assertEqual([item.form_name for item in page._visible_form_items], ["Customers", "Orders"])

    def test_schedule_page_uses_win11_scaffold(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.app_logger.add_log_handler"),
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_last_exec_time", return_value=None),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_next_exec_time", return_value=None),
        ):
            page = SchedulePage(gui)

        self.assert_uses_win11_scaffold(page)

    def test_sync_page_append_log_escapes_html_and_accepts_non_string_messages(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        page.append_log("<b>unsafe</b>", "INFO")
        page.append_log({"status": "ok"}, "INFO")

        log_text = "\n".join(page.log_entries)
        self.assertIn("<b>unsafe</b>", log_text)
        self.assertIn("{'status': 'ok'}", log_text)

    def test_schedule_page_instantiates_with_win11_page_property(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("page"), "schedule")

    def test_schedule_page_has_title_and_buttons(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertIsNotNone(page.page_title)
        self.assertEqual(page.page_title.text(), "调度管理")
        self.assertEqual(page.btn_stop.text(), "启动调度")
        self.assertEqual(page.btn_save.text(), "保存设置")

    def test_schedule_page_has_five_stat_cards(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        stat_cards = [w for w in page.findChildren(QFrame) if w.property("ui") == "sc-stat-card"]
        self.assertEqual(len(stat_cards), 5)

    def test_schedule_page_scheduler_running_displays_correctly(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": True, "sync_interval": 20}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=True),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()
        self.assertIsNotNone(page.btn_stop)

    def test_schedule_page_scheduler_stopped_displays_correctly(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()
        self.assertIsNotNone(page.btn_stop)

    def test_schedule_page_config_interval_from_settings(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": True, "sync_interval": 45}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsNotNone(page.btn_stop)

    def test_schedule_page_has_config_controls(self) -> None:
        from PySide6.QtWidgets import QAbstractSpinBox, QLabel, QPushButton, QSpinBox

        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.schedule_page.config_manager.get_sync_config",
                return_value={"auto_sync": False, "sync_interval": 60, "default_forms": ["物料", "客户"]},
            ),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        toggles = [w for w in page.findChildren(QPushButton) if w.isCheckable()]
        self.assertEqual(len(toggles), 1)
        spin_boxes = page.findChildren(QSpinBox)
        self.assertEqual(len(spin_boxes), 1)
        for spin_box in spin_boxes:
            self.assertEqual(spin_box.buttonSymbols(), QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.assertGreaterEqual(spin_box.width(), 96)
            self.assertGreaterEqual(spin_box.height(), 26)
        labels = [label.text() for label in page.findChildren(QLabel)]
        self.assertIn("同步范围", labels)
        self.assertIn("同步模式", labels)
        self.assertIn("启动说明", labels)
        self.assertIn("2 个表单", labels)
        self.assertIn("增量同步", labels)
        self.assertFalse(any("运行时间窗口" in text for text in labels))
        self.assertFalse(any("失败重试次数" in text for text in labels))
        self.assertFalse(any("并发任务数" in text for text in labels))

    def test_schedule_page_has_status_items(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        status_items = [w for w in page.findChildren(QFrame) if w.property("ui") == "sc-status-item"]
        self.assertEqual(len(status_items), 4)

    def test_schedule_page_has_log_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        tables = page.findChildren(DataTable)
        self.assertGreaterEqual(len(tables), 1)

    def test_schedule_page_controls_visible_at_1440x900(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.btn_stop.isVisible())
        self.assertTrue(page.btn_save.isVisible())
        self.assertTrue(page.page_title.isVisible())

    def test_schedule_page_final_visual_structure(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.gui.pages.schedule_page.app_logger.get_log_dir", return_value=tmpdir),
                patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": True, "sync_interval": 20}),
                patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=True),
            ):
                page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.property("page"), "schedule")
        self.assertEqual(page.btn_stop.height(), 26)
        self.assertEqual(page.btn_save.height(), 26)
        self.assertEqual(page.findChild(QWidget, "schedule_middle_row").height(), 292)
        self.assertEqual(page.page_subtitle.text(), "启动自动调度后会先执行一次增量同步，随后按间隔重复执行")
        self.assertEqual(page.sync_table.table.verticalHeader().defaultSectionSize(), 24)
        self.assertEqual(page.sync_table.table.horizontalHeader().height(), 28)
        self.assertEqual(page.sync_table.table.height(), 224)
        self.assertEqual(page.sync_table.table.rowCount(), 0)
        self.assertFalse(page.sync_table._empty_label.isHidden())
        self.assertEqual(page.sync_table._empty_label.text(), "暂无调度日志，启动自动调度后将在此显示执行记录。")
        self.assertEqual(page.lbl_total.text(), "共 0 条")
        self.assertEqual(page.pagination_row.count(), 2)

        markers = {frame.property("ui") for frame in page.findChildren(QFrame)}
        self.assertIn("sc-config-card", markers)
        self.assertIn("sc-status-card", markers)
        self.assertIn("sc-log-card", markers)

    def test_schedule_page_save_does_not_write_sql(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.config_manager.update_config"),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.UiFeedback"),
        ):
            page = SchedulePage(gui)

            self.addCleanup(cleanup_widget, page)

            from src.core.mysql_manager import mysql_manager
            spy_insert = MagicMock()
            spy_execute = MagicMock()
            original_insert = mysql_manager.insert_generic_data
            original_execute = mysql_manager.execute_writer
            mysql_manager.insert_generic_data = spy_insert
            mysql_manager.execute_writer = spy_execute

            page.resize(1440, 900)
            page.show()
            self._app.processEvents()

            page.btn_save.click()
            self._app.processEvents()

            mysql_manager.insert_generic_data = original_insert
            mysql_manager.execute_writer = original_execute

        spy_insert.assert_not_called()
        spy_execute.assert_not_called()

    def test_schedule_page_save_updates_config_only(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        config = {"auto_sync": False, "sync_interval": 60}

        def get_sync_config():
            return dict(config)

        def update_config(_section, key, value):
            config[key] = int(value) if key == "sync_interval" else value == "True"

        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", side_effect=get_sync_config),
            patch("src.gui.pages.schedule_page.config_manager.update_config", side_effect=update_config) as update_config_mock,
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.UiFeedback"),
        ):
            page = SchedulePage(gui)
            self.addCleanup(cleanup_widget, page)

            page.auto_toggle.setChecked(True)
            page.interval_spin.setValue(120)
            page._load_real_data()
            self.assertEqual(page.interval_spin.value(), 120)
            page.btn_save.click()
            self.assertTrue(page.auto_toggle.isChecked())
            self.assertEqual(page.auto_toggle.text(), "开")
            self.assertEqual(page.interval_spin.value(), 120)
            self.assertEqual(page._stat_cards["执行间隔"].value_label.text(), "120 分钟")

        update_config_mock.assert_any_call("SYNC", "auto_sync", "True")
        update_config_mock.assert_any_call("SYNC", "sync_interval", "120")
        self.assertEqual(config["sync_interval"], 120)
        updated_keys = [call.args[1] for call in update_config_mock.call_args_list]
        self.assertNotIn("schedule_retry_count", updated_keys)
        self.assertNotIn("schedule_concurrency", updated_keys)

    def test_schedule_page_reloads_saved_interval_when_reentered(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.schedule_page.config_manager.get_sync_config",
                return_value={"auto_sync": True, "sync_interval": 120, "default_forms": ["物料"]},
            ),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertTrue(page.auto_toggle.isChecked())
        self.assertEqual(page.auto_toggle.text(), "开")
        self.assertEqual(page.interval_spin.value(), 120)
        self.assertEqual(page._stat_cards["执行间隔"].value_label.text(), "120 分钟")
        self.assertEqual(page.scope_value.text(), "1 个表单")

    def test_schedule_page_toggle_scheduler_calls_existing_scheduler(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", side_effect=[False, False, True, True, False]),
            patch("src.gui.pages.schedule_page.auto_scheduler.start") as start,
            patch("src.gui.pages.schedule_page.auto_scheduler.stop") as stop,
            patch("src.gui.pages.schedule_page.UiFeedback"),
        ):
            page = SchedulePage(gui)
            self.addCleanup(cleanup_widget, page)
            page.interval_spin.setValue(25)
            page.toggle_scheduler()
            page.toggle_scheduler()

        start.assert_called_once_with(25)
        stop.assert_called_once()

    def test_schedule_page_log_filter_updates_table_and_total(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "app.jsonl"
            entries = [
                {
                    "asctime": "2026-06-24 10:01:02",
                    "name": "src.core.scheduler",
                    "levelname": "INFO",
                    "message": "定时同步已启动",
                },
                {
                    "asctime": "2026-06-24 10:02:04",
                    "name": "src.core.scheduler",
                    "levelname": "ERROR",
                    "message": "调度器运行异常: boom",
                },
            ]
            log_path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")

            with (
                patch("src.gui.pages.schedule_page.app_logger.get_log_dir", return_value=tmpdir),
                patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
                patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            ):
                page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page.log_level_combo.setCurrentText("ERROR")
        self.assertEqual(page.sync_table.table.rowCount(), 1)
        self.assertEqual(page.lbl_total.text(), "共 1 条")

    def test_schedule_page_empty_scheduler_logs_show_empty_state_without_static_rows(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.gui.pages.schedule_page.app_logger.get_log_dir", return_value=tmpdir),
                patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
                patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            ):
                page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.sync_table.table.rowCount(), 0)
        self.assertFalse(page.sync_table._empty_label.isHidden())
        self.assertEqual(page.sync_table._empty_label.text(), "暂无调度日志，启动自动调度后将在此显示执行记录。")
        self.assertEqual(page.lbl_total.text(), "共 0 条")
        self.assertEqual(page.pagination_row.count(), 2)

    def test_schedule_page_status_copy_uses_control_console_terms(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertNotIn("当前队列", page._status_items)
        self.assertNotIn("服务心跳", page._status_items)
        self.assertEqual(page._status_items["当前状态"].action_label.text(), "查看任务管理")
        self.assertEqual(page._status_items["服务日志"].value_label.text(), "读取日志中心")

    def test_schedule_page_reads_real_scheduler_logs_from_jsonl(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "app.jsonl"
            entries = [
                {
                    "asctime": "2026-06-24 10:01:02",
                    "name": "src.core.scheduler",
                    "levelname": "INFO",
                    "message": "定时同步已启动",
                },
                {
                    "asctime": "2026-06-24 10:02:02",
                    "name": "src.core.data_sync",
                    "levelname": "INFO",
                    "message": "普通同步日志，不应进入当前页面",
                },
                {
                    "asctime": "2026-06-24 10:02:04",
                    "name": "src.core.scheduler",
                    "levelname": "ERROR",
                    "message": "调度器运行异常: boom",
                },
            ]
            log_path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")

            with (
                patch("src.gui.pages.schedule_page.app_logger.get_log_dir", return_value=tmpdir),
                patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
                patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            ):
                page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.sync_table.table.rowCount(), 2)
        self.assertEqual(page.lbl_total.text(), "共 2 条")
        self.assertIn("定时同步已启动", page.sync_table.table.item(0, 2).text())

    def test_schedule_page_status_actions_navigate_to_related_pages(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace(switch_to_page=MagicMock())
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        page._navigate_to("task_management")
        page._navigate_to("history")
        page._navigate_to("log_center")

        self.assertEqual(
            gui.switch_to_page.call_args_list,
            [unittest.mock.call("task_management"), unittest.mock.call("history"), unittest.mock.call("log_center")],
        )

    def test_schedule_page_stat_cards_show_real_last_and_next_times(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        last_time = datetime(2026, 6, 24, 9, 20, 0)
        next_time = datetime(2026, 6, 24, 10, 0, 0)
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": True, "sync_interval": 20}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=True),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_last_exec_time", return_value=last_time),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_next_exec_time", return_value=next_time),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page._stat_cards["上次执行"].value_label.text(), "09:20")
        self.assertEqual(page._stat_cards["下次执行"].value_label.text(), "10:00")

    def test_history_page_uses_win11_scaffold(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.assert_uses_win11_scaffold(page)


class Win11ShellSmokeTests(QtAppTestCase):
    def test_main_shell_exposes_required_win11_markers(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        main_content_shell = window.findChild(QObject, "main_content_shell")
        self.assertIsNotNone(main_content_shell)
        self.assertEqual(main_content_shell.property("ui"), "win11-shell")

        top_status_bar = window.findChild(QObject, "top_status_bar")
        self.assertIsNotNone(top_status_bar)
        self.assertEqual(top_status_bar.property("ui"), "win11-command-bar")

        sidebar = window.findChild(QObject, "sidebar")
        self.assertIsNotNone(sidebar)
        self.assertEqual(sidebar.property("ui"), "win11-nav-panel")

        sidebar_brand = window.findChild(QObject, "sidebar_brand")
        self.assertIsNotNone(sidebar_brand)
        sidebar_footer = window.findChild(QObject, "sidebar_footer")
        self.assertIsNotNone(sidebar_footer)
        statusbar_dot = window.findChild(QLabel, "statusbar_dot")
        self.assertIsNotNone(statusbar_dot)
        self.assertFalse(statusbar_dot.pixmap().isNull())

    def test_shell_timer_does_not_force_schedule_page_status_refresh(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        schedule_page = SimpleNamespace(check_status=unittest.mock.Mock())
        shell = SimpleNamespace(
            _refresh_top_status_bar=unittest.mock.Mock(),
            pages={"schedule": schedule_page},
        )

        KingdeeSyncGUI.check_scheduler_status(shell)

        shell._refresh_top_status_bar.assert_called_once()
        schedule_page.check_status.assert_not_called()


class Win11ShellCopyZhCnSmokeTests(QtAppTestCase):
    def test_shell_topbar_copy_is_simplified_chinese(self) -> None:
        from PySide6.QtCore import QPoint

        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)
        window.resize(1440, 900)
        window.show()
        self._app.processEvents()

        self.assertEqual(window.btn_setting.text(), "设置")
        self.assertEqual(window.btn_help.text(), "帮助")
        self.assertEqual(window.topbar_conn_value.text(), "未连接")
        self.assertTrue(window.topbar_kingdee_value.text())
        self.assertTrue(window.topbar_database_value.text())
        # 操作区与窗口控制按钮存在性
        self.assertIsNotNone(window.btn_setting)
        self.assertIsNotNone(window.btn_help)

    def test_shell_topbar_uses_real_readonly_config_values(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        with (
            patch(
                "src.gui.kingdee_sync_gui.config_manager.get_kingdee_config",
                return_value={"query_url": "https://real.kingdee.example/k2cloud/"},
            ),
            patch(
                "src.gui.kingdee_sync_gui.config_manager.get_db_config",
                return_value={
                    "type": "sqlserver",
                    "sqlserver": {"host": "10.88.1.22", "port": "1422", "database": "real_db"},
                },
            ),
        ):
            window = KingdeeSyncGUI()
            self.addCleanup(cleanup_widget, window)
            window.kd_connected = True
            window.db_connected = True
            window._refresh_top_status_bar()

        self.assertEqual(window.topbar_conn_value.text(), "已连接")
        self.assertEqual(window.topbar_kingdee_value.text(), "https://real.kingdee.example")
        self.assertEqual(window.topbar_kingdee_value.toolTip(), "https://real.kingdee.example")
        self.assertEqual(window.topbar_database_value.text(), "SQL Server (10.88.1.22)")
        self.assertEqual(window.topbar_database_value.toolTip(), "SQL Server (10.88.1.22)")

        window.db_connected = False
        window._refresh_top_status_bar()
        self.assertEqual(window.topbar_conn_value.text(), "部分连接")

        window.kd_connected = False
        window._refresh_top_status_bar()
        self.assertEqual(window.topbar_conn_value.text(), "未连接")


class Win11DashboardAndSyncCopyZhCnSmokeTests(QtAppTestCase):
    def test_dashboard_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "概览")

        self.assertEqual(page.refresh_btn.text(), "刷新")
        self.assertEqual(page._status_cards.card_count.title_label.text(), "今日同步次数")
        # trend_card is TrendChartWidget with header label inside it
        health_card = page.health_card
        self.assertEqual(health_card.property("ui"), "win11-section-card")
        self.assertEqual(page.recent_card.title_label.text(), "最近同步记录")
        self.assertEqual(page.risk_card.title_label.text(), "风险提醒")

    def test_sync_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "同步执行")

        self.assertEqual(page.start_sync_btn.text(), "开始同步")
        self.assertEqual(page.test_conn_btn.text(), "测试连接")


class Win11SettingsAndFormsCopyZhCnSmokeTests(QtAppTestCase):
    def test_settings_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
                return_value={
                    "kingdee": {},
                    "database": {},
                },
            ),
            patch("src.gui.pages.settings_page.UiFeedback.error") as error_feedback,
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.btn_test.text(), "测试连接")
        self.assertEqual(page.btn_save.text(), "保存设置")
        error_feedback.assert_not_called()

    def test_settings_page_keeps_password_placeholders_when_no_stored_password(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
                return_value={
                    "kingdee": {
                        "password": "",
                    },
                    "database": {
                        "password": "",
                    },
                },
            ),
            patch(
                "src.gui.pages.settings_page.settings_service.get_config_source_name",
                return_value="用户配置文件",
            ),
            patch(
                "src.gui.pages.settings_page.settings_service.get_config_source",
                return_value="C:/Kingdee/config.ini",
            ),
            patch(
                "src.gui.pages.settings_page.settings_service.get_database_type",
                return_value="SQL Server",
            ),
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.password.placeholderText(), "留空保留原密码")
        self.assertEqual(page.db_password.placeholderText(), "留空保留原密码")

    def test_forms_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.btn_refresh_config.text(), "刷新配置")
        self.assertEqual(page.btn_view_diagnostics.text(), "查看诊断")


class Win11ScheduleAndHistoryCopyZhCnSmokeTests(QtAppTestCase):
    def test_schedule_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
        ):
            page = SchedulePage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.btn_stop.text(), "启动调度")
        self.assertEqual(page.btn_save.text(), "保存设置")

    def test_history_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "同步历史")
        self.assertEqual(page.btn_export.text(), "导出")
        self.assertEqual(page.btn_prev.property("icon-source"), "chevron_left.svg")
        self.assertEqual(page.btn_next.property("icon-source"), "chevron_right.svg")
        self.assertFalse(page.btn_prev.icon().isNull())
        self.assertFalse(page.btn_next.icon().isNull())

    def test_history_page_filter_fields_use_clean_chinese(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)

        filter_labels = [w.text() for w in page._filter_panel._grid.findChildren(QLabel)]
        self.assertIn("时间范围", filter_labels)
        self.assertIn("表单类型", filter_labels)
        self.assertIn("状态", filter_labels)
        self.assertIn("任务名称", filter_labels)

        self.assertIsNotNone(page.btn_query)
        self.assertEqual(page.btn_query.text(), "查询")
        self.assertEqual(page.btn_reset.text(), "重置")

    def test_history_page_build_tag_uses_status_mark(self) -> None:
        from src.gui.pages.history_page import HistoryPage, HistoryStatusTag

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)

        tag = page._build_tag("成功", "success")
        self.assertIsInstance(tag, HistoryStatusTag)
        self.assertEqual(tag.label.text(), "成功")
        self.assertEqual(tag.property("tone"), "success")

    def test_forms_page_hero_badge_is_status_chip(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={"Customers": "t_customer"}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": ["Customers"]}),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertFalse(hasattr(page, "hero_badge"))
        self.assertFalse(page.hero_card.isVisible())

    def test_forms_page_build_form_row_returns_checked_row(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={"Customers": "t_customer"}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": ["Customers"]}),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertFalse(hasattr(page, "_build_form_row"))
        self.assertEqual(page._visible_form_items[0].form_name, "Customers")
        self.assertEqual(page._visible_form_items[0].property("selected"), True)

    def test_forms_page_search_box_width_uses_tokens(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={"Customers": "t_customer"}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": ["Customers"]}),
            patch("src.gui.pages.forms_page.config_manager.get_field_mappings", return_value={}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.search_box.minimumWidth(), 260)
        self.assertEqual(page.search_box.maximumWidth(), 16777215)

    def test_forms_page_1266x768_integration(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.forms_page.config_manager.get_table_mapping",
                return_value={"Customers": "t_customer", "Orders": "t_order"},
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                return_value={"default_forms": ["Customers"]},
            ),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.btn_refresh_config.isVisible())
        self.assertFalse(hasattr(page, "btn_save"))
        self.assertFalse(hasattr(page, "btn_import"))
        self.assertTrue(page.search_box.isVisible())
        self.assertIsNotNone(page.field_table)

    def test_history_page_hero_badge_is_status_chip(self) -> None:
        from src.gui.components.common import StatusChip
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page.hero_badge, StatusChip)
        self.assertEqual(page.hero_badge.text(), "历史浏览")
        self.assertEqual(page.hero_badge.property("tone"), "info")
        self.assertEqual(page.hero_badge.property("ui"), "win11-status-chip")


class Win11SyncPageLocalizationSafeBehaviorTests(QtAppTestCase):
    def _resolve_combo_data(self, combo) -> str | None:
        # Prefer the widget's selected payload (stable), then index/data fallback.
        current_data = getattr(combo, "_current_data", None)
        if current_data is not None:
            return current_data

        items = getattr(combo, "items_data", []) or []
        current_index = combo.currentIndex()
        if 0 <= current_index < len(items):
            return items[current_index][2]
        return None

    def _set_combo_by_data(self, combo, target_data: str) -> None:
        for idx, (_text, _icon, data) in enumerate(getattr(combo, "items_data", []) or []):
            if data == target_data:
                combo.setCurrentIndex(idx)
                return
        raise AssertionError(f"Target data not found in combo items: {target_data!r}")

    def test_load_smart_defaults_selects_default_form_set_by_stable_data(self) -> None:
        from src.gui.pages.sync_page import FORM_DEFAULT_DATA, SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders", "Invoices"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers", "Orders"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        # Assert selection via stable data, not display text / index order.
        self.assertEqual(self._resolve_combo_data(page.form_selector), FORM_DEFAULT_DATA)

    def test_sync_mode_mapping_uses_stable_internal_values(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "complete"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(self._resolve_combo_data(page.sync_type_combo), "complete")
        self.assertEqual(
            [item[2] for item in page.sync_type_combo.items_data],
            ["incremental", "complete"],
        )

    def test_start_sync_uses_mode_data_for_sync_type_and_default_set_for_forms(self) -> None:
        from src.gui.pages.sync_page import FORM_DEFAULT_DATA, SyncPage

        captured = {}

        class DummyWorker:
            def __init__(self, forms, sync_type, service=None):
                captured["forms"] = forms
                captured["sync_type"] = sync_type

                class _Sig:
                    def connect(self, *_args, **_kwargs):
                        return None

                self.progress = _Sig()
                self.finished = _Sig()

            def isRunning(self):
                return False

            def start(self):
                return None

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers", "Orders"], "sync_type": "incremental"},
            ),
            patch("src.gui.pages.sync_page.sync_service.save_sync_preferences"),
            patch("src.gui.pages.sync_page.SyncWorker", DummyWorker),
        ):
            page = SyncPage(gui)
            self.addCleanup(cleanup_widget, page)

            # Choose "default set" via stable data and choose complete mode via stable data.
            self._set_combo_by_data(page.form_selector, FORM_DEFAULT_DATA)
            self._set_combo_by_data(page.sync_type_combo, "complete")

            page.start_sync()

            self.assertEqual(captured.get("forms"), ["Customers", "Orders"])
            self.assertEqual(getattr(captured.get("sync_type"), "name", ""), "COMPLETE")

    def test_preflight_bar_tracks_current_manual_selection(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        self._set_combo_by_data(page.form_selector, "Orders")
        self._set_combo_by_data(page.sync_type_combo, "complete")

        self.assertEqual(page.preflight_api_value.text(), "未检测")
        self.assertEqual(page.preflight_db_value.text(), "未检测")
        self.assertEqual(page.preflight_scope_value.text(), "Orders")
        self.assertEqual(page.preflight_mode_value.text(), "完全同步")

    def test_sync_page_uses_launchpad_layout_without_floating_preflight_bar(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.stepper_strip.objectName(), "sync_launchpad_steps")
        self.assertEqual(page.launchpad_core.property("ui"), "sync-launchpad-core")
        self.assertEqual(page.preflight_card.property("sync-section"), "preflight")
        self.assertLessEqual(page.launchpad_core.maximumHeight(), 420)
        self.assertFalse(hasattr(page, "log_card"))
        self.assertFalse(hasattr(page, "workspace_splitter"))
        self.assertFalse(hasattr(page, "cockpit_row"))
        self.assertIsNone(page.findChild(QFrame, "sync_preflight_bar"))
        self.assertFalse(page.cancel_sync_btn.isEnabled())

    def test_connection_result_updates_preflight_status_and_time(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
            patch("src.gui.pages.sync_page.UiFeedback"),
        ):
            page = SyncPage(gui)
            self.addCleanup(cleanup_widget, page)
            page.on_test_finished(True, False, "数据库连接失败")

        self.assertEqual(page.preflight_api_value.text(), "正常")
        self.assertEqual(page.preflight_db_value.text(), "异常")
        self.assertNotEqual(page.preflight_test_time_value.text(), "--")
        self.assertIn("数据库连接失败", page.test_status_lbl.text())

    def test_running_state_disables_start_and_cancel_shows_unsupported_feedback(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        class DummyWorker:
            def __init__(self, *_args, **_kwargs):
                class _Sig:
                    def connect(self, *_args, **_kwargs):
                        return None

                self.progress = _Sig()
                self.finished = _Sig()

            def isRunning(self):
                return True

            def start(self):
                return None

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
            patch("src.gui.pages.sync_page.sync_service.save_sync_preferences"),
            patch("src.gui.pages.sync_page.SyncWorker", DummyWorker),
            patch("src.gui.pages.sync_page.UiFeedback") as mock_feedback,
        ):
            page = SyncPage(gui)
            self.addCleanup(cleanup_widget, page)

            page.start_sync()
            self.assertFalse(page.start_sync_btn.isEnabled())
            self.assertTrue(page.cancel_sync_btn.isEnabled())

            page.cancel_sync_btn.click()

        mock_feedback.info.assert_called()
        self.assertIn("暂不支持中途取消", "\n".join(page.log_entries))

    def test_sync_finished_uses_total_records_fallback_when_details_missing(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.start_sync_btn.set_loading(True)
        page.cancel_sync_btn.setEnabled(True)
        page.on_sync_finished({"status": "success", "message": "OK", "total_records": 128, "details": {}})

        self.assertEqual(page.exec_count_card.value_label.text(), "128")
        self.assertIn("128", page.summary_result.value_label.text())
        self.assertFalse(page.cancel_sync_btn.isEnabled())

    def test_load_smart_defaults_single_form_prefers_data_when_text_collides(self) -> None:
        from src.gui.pages.sync_page import FORM_ALL_DATA, FORM_ALL_TEXT, SyncPage

        gui = SimpleNamespace()
        with (
            patch(
                "src.gui.pages.sync_page.sync_service.get_available_forms",
                return_value=[FORM_ALL_TEXT, "Orders"],
            ),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": [FORM_ALL_TEXT], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        # Must select the actual form payload, not the special "__ALL__" option.
        self.assertEqual(self._resolve_combo_data(page.form_selector), FORM_ALL_TEXT)
        self.assertNotEqual(self._resolve_combo_data(page.form_selector), FORM_ALL_DATA)


class Win11ShellStylesheetTests(unittest.TestCase):
    def test_stylesheet_does_not_keep_global_apple_shell_pass(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        apple_shell_block = re.search(
            r"/\* Apple-like visual pass \*/\s*QMainWindow\s*\{.*?\}\s*QWidget\s*\{",
            css,
            re.DOTALL,
        )
        self.assertIsNone(apple_shell_block)

    def test_stylesheet_does_not_use_global_scrollarea_transparency_for_shell(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertNotRegex(css, r"(?m)^QScrollArea,\s*$")
        self.assertNotRegex(css, r"(?m)^QScrollArea\s*>\s*QWidget\s*>\s*QWidget\s*\{")

    def test_stylesheet_includes_win11_page_specific_text_and_table_selectors(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertIn('QLabel[ui="win11-status-chip"]', css)
        self.assertIn('QLabel[ui="win11-meta-text"]', css)
        self.assertIn('QLabel[ui="win11-helper-text"]', css)
        self.assertIn('QTableWidget[ui="win11-data-table"]', css)
        self.assertIn('QLabel[ui="win11-table-tag"]', css)
        self.assertIn('QFrame[ui="win11-pagination-card"]', css)
        self.assertIn('QLabel[ui="win11-page-badge"]', css)
        self.assertIn('QFrame[ui="win11-metric-card"]', css)

    def test_stylesheet_keeps_only_one_global_widget_base_pass(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertEqual(len(re.findall(r"(?m)^QMainWindow\s*\{", css)), 1)
        self.assertEqual(len(re.findall(r"(?m)^QWidget\s*\{", css)), 1)

    def test_stylesheet_reasserts_win11_progress_and_header_scoping(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertIn('QWidget[ui="win11-page"] QProgressBar', css)
        self.assertIn('QTableWidget[ui="win11-data-table"] QHeaderView::section', css)


class Win11TokenComplianceTests(QtAppTestCase):
    """Verify pages and components comply with frontend-guidelines.md token rules."""

    _SCAN_DIRS = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "gui", "pages"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "gui", "components"),
    ]
    _SKIP_FILES = {"design_tokens.py"}

    def _scan_files(self, pattern: str) -> list[tuple[str, int, str]]:
        """Return list of (relpath, lineno, line) matching pattern in scanned dirs."""
        hits = []
        for scan_dir in self._SCAN_DIRS:
            if not os.path.isdir(scan_dir):
                continue
            for fname in os.listdir(scan_dir):
                if not fname.endswith(".py") or fname.startswith("__") or fname in self._SKIP_FILES:
                    continue
                fpath = os.path.join(scan_dir, fname)
                rel = os.path.relpath(fpath, os.path.dirname(os.path.dirname(__file__)))
                with open(fpath, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        if re.search(pattern, line):
                            hits.append((rel, lineno, line.rstrip()))
        return hits

    def test_no_setstylesheet_calls(self) -> None:
        hits = self._scan_files(r"\.setStyleSheet\s*\(")
        self.assertEqual(hits, [], f"setStyleSheet found: {hits}")

    def test_no_hardcoded_hex_color_literals(self) -> None:
        hits = self._scan_files(r"#[0-9A-Fa-f]{2,8}")
        self.assertEqual(hits, [], f"Hardcoded hex found: {hits}")

    def test_no_garbled_chinese_text(self) -> None:
        garbled_patterns = ["鎼滅储", "鏃堕棿鑼冨洿", "鐘舵€?", "绫诲瀷"]
        for pattern in garbled_patterns:
            hits = self._scan_files(re.escape(pattern))
            self.assertEqual(hits, [], f"Garbled text {pattern!r} found: {hits}")


class Win11MainShellStylesheetTests(QtAppTestCase):
    def test_main_window_stylesheet_is_loaded(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        ss = window.styleSheet()
        self.assertTrue(len(ss) > 0, "Main window styleSheet() is empty")
        self.assertIn("QMainWindow", ss)


class Win11NewComponentSmokeTests(QtAppTestCase):
    def test_action_bar_instantiates(self) -> None:
        from src.gui.components.common import ActionBar

        bar = ActionBar()
        self.addCleanup(cleanup_widget, bar)
        self.assertEqual(bar.property("ui"), "win11-action-bar")

    def test_field_row_instantiates(self) -> None:
        from src.gui.components.common import FieldRow

        editor = QLabel("value")
        row = FieldRow("Title", "Note text", editor)
        self.addCleanup(cleanup_widget, row)
        self.assertEqual(row.property("ui"), "win11-setting-row")
        self.assertEqual(row.title_label.text(), "Title")

    def test_status_chip_instantiates_with_tone(self) -> None:
        from src.gui.components.common import StatusChip

        chip = StatusChip("OK", tone="success")
        self.assertEqual(chip.property("ui"), "win11-status-chip")
        self.assertEqual(chip.property("tone"), "success")

    def test_log_panel_instantiates(self) -> None:
        from src.gui.components.common import LogPanel

        panel = LogPanel()
        self.addCleanup(cleanup_widget, panel)
        self.assertEqual(panel.property("ui"), "win11-log-panel")

    def test_metric_card_instantiates(self) -> None:
        from src.gui.components.common import MetricCard

        card = MetricCard("Tasks", "42", "Running")
        self.addCleanup(cleanup_widget, card)
        self.assertEqual(card.property("ui"), "win11-metric-card")
        self.assertEqual(card.value_label.text(), "42")

    def test_metric_card_set_data(self) -> None:
        from src.gui.components.common import MetricCard

        card = MetricCard("Tasks")
        self.addCleanup(cleanup_widget, card)
        card.show()
        self._app.processEvents()
        card.set_data("100", "All done")
        self.assertEqual(card.value_label.text(), "100")
        self.assertEqual(card.note_label.text(), "All done")
        self.assertTrue(card.note_label.isVisible())


class Win11DesignTokenExpansionTests(unittest.TestCase):
    def test_spacing_tokens_exist(self) -> None:
        from src.gui.design_tokens import SpacingTokens

        self.assertEqual(SpacingTokens.XS, 4)
        self.assertEqual(SpacingTokens.SM, 8)
        self.assertEqual(SpacingTokens.MD, 12)
        self.assertEqual(SpacingTokens.LG, 16)
        self.assertEqual(SpacingTokens.XL, 20)
        self.assertEqual(SpacingTokens.XXL, 24)
        self.assertEqual(SpacingTokens.XXXL, 22)

    def test_css_text_color_tokens_exist(self) -> None:
        from src.gui.design_tokens import ColorTokens

        self.assertEqual(ColorTokens.TEXT_PRIMARY_DEEP, "#0F172A")
        self.assertEqual(ColorTokens.TEXT_PRIMARY_SOFT, "#1F2927")
        self.assertEqual(ColorTokens.TEXT_SECONDARY_DEEP, "#224155")

    def test_green_success_color_tokens_exist(self) -> None:
        from src.gui.design_tokens import ColorTokens

        self.assertEqual(ColorTokens.SUCCESS_GREEN, "#16A67D")
        self.assertEqual(ColorTokens.SUCCESS_GREEN_DARK, "#0F8A6B")
        self.assertEqual(ColorTokens.SUCCESS_GREEN_DEEP, "#0F7B42")
        self.assertEqual(ColorTokens.SUCCESS_GREEN_MEDIUM, "#178B68")
        self.assertEqual(ColorTokens.SUCCESS_GREEN_BG, "#F8FFFC")
        self.assertEqual(ColorTokens.SUCCESS_GREEN_BG_LIGHT, "#EAFBF5")
        self.assertEqual(ColorTokens.SUCCESS_GREEN_BORDER, "#D2E9E0")
        self.assertEqual(ColorTokens.SUCCESS, "#2E95D9")

    def test_phase5_color_tokens_exist(self) -> None:
        from src.gui.design_tokens import ColorTokens

        self.assertEqual(ColorTokens.INTERACTIVE_SURFACE, "#2562EB")
        self.assertEqual(ColorTokens.INTERACTIVE_PRESSED, "#1D4ED8")
        self.assertEqual(ColorTokens.INTERACTIVE_PRIMARY, "#0F6CBD")
        self.assertEqual(ColorTokens.STROKE_SOFT_BLUE, "#DBE2F0")
        self.assertEqual(ColorTokens.ACCENT_BG_SOFT, "#EDF6FF")
        self.assertEqual(ColorTokens.ACCENT_HOVER_BG, "#E8F0FF")
        self.assertEqual(ColorTokens.WARNING_ORANGE_DEEP, "#B14E24")
        self.assertEqual(ColorTokens.SUCCESS, "#2E95D9")

    def test_typography_tokens_exist(self) -> None:
        from src.gui.design_tokens import TypographyTokens

        self.assertEqual(TypographyTokens.FONT_SIZE_MD, 12)
        self.assertEqual(TypographyTokens.FONT_WEIGHT_MEDIUM, 600)

    def test_size_tokens_expanded(self) -> None:
        from src.gui.design_tokens import SizeTokens

        self.assertEqual(SizeTokens.ICON_SIZE_SM, 16)
        self.assertEqual(SizeTokens.ICON_SIZE_MD, 20)
        self.assertEqual(SizeTokens.SIDEBAR_EXPANDED, 256)
        self.assertEqual(SizeTokens.SIDEBAR_COMPACT, 96)
        self.assertEqual(SizeTokens.MIN_DESKTOP_WIDTH, 1266)
        self.assertEqual(SizeTokens.MIN_DESKTOP_HEIGHT, 768)

    def test_effect_tokens_exist(self) -> None:
        from src.gui.design_tokens import EffectTokens

        self.assertIn("rgba", EffectTokens.SHADOW_CARD)
        self.assertIn("rgba", EffectTokens.SHADOW_POPUP)

    def test_component_spacing_tokens_exist(self) -> None:
        from src.gui.design_tokens import SpacingTokens

        self.assertEqual(SpacingTokens.NONE, 0)
        self.assertEqual(SpacingTokens.XXS, 2)
        self.assertEqual(SpacingTokens.ACTION_BAR_GAP, 10)
        self.assertEqual(SpacingTokens.FIELD_ROW_VERTICAL, 12)
        self.assertEqual(SpacingTokens.FIELD_ROW_GAP, 14)
        self.assertEqual(SpacingTokens.LOG_TOOLBAR_H_PADDING, 10)
        self.assertEqual(SpacingTokens.LOG_TOOLBAR_V_PADDING, 8)
        self.assertEqual(SpacingTokens.FORM_ROW_VERTICAL, 14)
        self.assertEqual(SpacingTokens.FORM_ROW_GAP, 12)
        self.assertEqual(SpacingTokens.FORM_META_GAP, 6)
        self.assertEqual(SpacingTokens.FORM_PAGE_GAP, 16)
        self.assertEqual(SpacingTokens.FORM_FILTER_GAP, 12)
        self.assertEqual(SpacingTokens.FORM_LIST_VERTICAL_PADDING, 4)
        self.assertEqual(SpacingTokens.WORKSPACE_COLUMN_GAP, 14)
        self.assertEqual(SpacingTokens.PROGRESS_PANEL_PADDING, 14)
        self.assertEqual(SpacingTokens.SHELL_CARD_PADDING, 18)

    def test_component_size_tokens_exist(self) -> None:
        from src.gui.design_tokens import SizeTokens

        self.assertEqual(SizeTokens.FIELD_ROW_SPIN_WIDTH_COMPACT, 120)
        self.assertEqual(SizeTokens.FIELD_ROW_SPIN_WIDTH, 140)
        self.assertEqual(SizeTokens.FIELD_ROW_EDITOR_MAX_WIDTH, 420)
        self.assertEqual(SizeTokens.QT_MAX_WIDTH, 16777215)
        self.assertEqual(SizeTokens.LOG_ACTION_BUTTON_HEIGHT, 22)
        self.assertEqual(SizeTokens.METRIC_CARD_MIN_HEIGHT, 84)
        self.assertEqual(SizeTokens.FORM_ACTION_BUTTON_HEIGHT, 26)
        self.assertEqual(SizeTokens.FORM_SEARCH_WIDTH_COMPACT, 260)
        self.assertEqual(SizeTokens.FORM_SEARCH_WIDTH, 220)
        self.assertEqual(SizeTokens.FORM_SEARCH_MIN_WIDTH_COMPACT, 180)
        self.assertEqual(SizeTokens.FORM_SEARCH_MIN_WIDTH, 260)
        self.assertEqual(SizeTokens.SYNC_LOG_MIN_HEIGHT_COMPACT, 180)
        self.assertEqual(SizeTokens.SYNC_LOG_MIN_HEIGHT, 220)
        self.assertEqual(SizeTokens.SYNC_CONFIG_PANEL_WIDTH, 420)
        self.assertEqual(SizeTokens.SYNC_EXECUTION_CARD_MAX_HEIGHT_COMPACT, 220)
        self.assertEqual(SizeTokens.SYNC_SPLITTER_SIZES_WIDE, (540, 980))
        self.assertEqual(SizeTokens.SCHEDULE_LOG_MIN_HEIGHT_COMPACT, 180)
        self.assertEqual(SizeTokens.SCHEDULE_LOG_MIN_HEIGHT, 220)
        self.assertEqual(SizeTokens.SCHEDULE_LEFT_PANEL_MIN_WIDTH, 420)
        self.assertEqual(SizeTokens.SCHEDULE_LEFT_PANEL_MAX_WIDTH, 560)
        self.assertEqual(SizeTokens.SCHEDULE_SPLITTER_SIZES_WIDE, (560, 920))
        self.assertEqual(SizeTokens.PROGRESS_BAR_HEIGHT, 10)
        self.assertEqual(SizeTokens.SCHEDULE_STATUS_TEXT_MIN_HEIGHT, 28)
        self.assertEqual(SizeTokens.SCHEDULE_PRESET_BUTTON_HEIGHT, 22)
        self.assertEqual(SizeTokens.SCHEDULE_STATUS_CARD_MIN_HEIGHT, 220)
        self.assertEqual(SizeTokens.SCHEDULE_WORKSPACE_STATUS_EXTRA_HEIGHT, 180)
        self.assertEqual(SizeTokens.SCHEDULE_WORKSPACE_HEIGHT_RATIO, 0.58)
        self.assertEqual(SizeTokens.SCHEDULE_WORKSPACE_BOTTOM_MIN_HEIGHT, 260)
        self.assertEqual(SizeTokens.SYNC_WORKSPACE_HEIGHT_RATIO, 0.44)
        self.assertEqual(SizeTokens.SYNC_WORKSPACE_BOTTOM_MIN_HEIGHT, 260)
        self.assertEqual(SizeTokens.TOGGLE_WIDTH, 44)
        self.assertEqual(SizeTokens.TOGGLE_HEIGHT, 24)
        self.assertEqual(SizeTokens.COMBO_POPUP_ITEM_HEIGHT, 40)
        self.assertEqual(SizeTokens.COMBO_POPUP_EXTRA_HEIGHT, 60)
        self.assertEqual(SizeTokens.COMBO_POPUP_MAX_HEIGHT, 200)
        self.assertEqual(SizeTokens.CHART_MIN_HEIGHT, 200)
        self.assertEqual(SizeTokens.CHART_COMPACT_MIN_HEIGHT, 150)
        self.assertEqual(SizeTokens.CHART_BAR_HEIGHT, 24)
        self.assertEqual(SizeTokens.PAGINATION_BUTTON_HEIGHT, 24)
        self.assertEqual(SizeTokens.PAGINATION_LABEL_WIDTH, 52)
        self.assertEqual(SizeTokens.PAGINATION_JUMP_WIDTH, 86)
        self.assertEqual(SizeTokens.HISTORY_PAGINATION_LABEL_WIDTH, 42)
        self.assertEqual(SizeTokens.HISTORY_PAGINATION_COMBO_WIDTH, 96)
        self.assertEqual(SizeTokens.HISTORY_EXPORT_BUTTON_WIDTH, 108)
        self.assertEqual(SizeTokens.HISTORY_EXPORT_BUTTON_HEIGHT, 26)
        self.assertEqual(SizeTokens.HISTORY_FILTER_TIME_WIDTH, 260)
        self.assertEqual(SizeTokens.HISTORY_FILTER_SELECT_WIDTH, 176)
        self.assertEqual(SizeTokens.HISTORY_FILTER_SEARCH_MIN_WIDTH, 280)
        self.assertEqual(SizeTokens.HISTORY_FILTER_ACTION_WIDTH, 90)
        self.assertEqual(SizeTokens.DASHBOARD_STATUS_CARD_MIN_SIZE, 220)
        self.assertEqual(SizeTokens.DASHBOARD_TREND_CHART_MIN_HEIGHT, 200)
        self.assertEqual(SizeTokens.DASHBOARD_VOLUME_CHART_MIN_HEIGHT, 240)
        self.assertEqual(SizeTokens.DASHBOARD_TABLE_HEADER_HEIGHT, 24)
        self.assertEqual(SizeTokens.DASHBOARD_TABLE_ROW_HEIGHT, 28)
        self.assertEqual(SizeTokens.DASHBOARD_TABLE_MAX_HEIGHT, 220)
        self.assertEqual(SizeTokens.SCHEDULE_INTERVAL_SPIN_WIDTH, 160)
        self.assertEqual(SizeTokens.DATA_TABLE_MIN_SECTION_WIDTH, 60)
        self.assertEqual(SizeTokens.DATA_TABLE_ROW_HEIGHT, 42)
        self.assertEqual(SizeTokens.HISTORY_TABLE_ROW_HEIGHT, 22)
        self.assertEqual(SizeTokens.HISTORY_TABLE_HEADER_HEIGHT, 26)


class Win11CssTokenGovernanceGuardTests(unittest.TestCase):
    """Static guards to prevent QSS token governance regression."""

    _CSS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css")

    def _get_css_token_set(self) -> set[str]:
        from src.gui.design_tokens import ColorTokens

        token_set = set()
        for attr in dir(ColorTokens):
            if attr.startswith("_"):
                continue
            val = getattr(ColorTokens, attr)
            if isinstance(val, str) and val.startswith("#"):
                token_set.add(val.upper())
        return token_set

    def _count_css_hexes(self) -> tuple[int, int, int, int]:
        import re
        from collections import Counter

        with open(self._CSS_PATH, encoding="utf-8-sig") as f:
            css = f.read()
        hexes = re.findall(r"#[0-9a-fA-F]{2,8}\b", css)
        counts = Counter(h.upper() for h in hexes)
        token_set = self._get_css_token_set()
        exact = sum(c for h, c in counts.items() if h in token_set)
        ungoverned_4plus = sum(1 for h, c in counts.items() if c >= 4 and h not in token_set)
        return len(hexes), len(counts), exact, ungoverned_4plus

    def test_css_total_hex_occurrences_stable(self) -> None:
        total, _, _, _ = self._count_css_hexes()
        self.assertEqual(total, 1526)

    def test_css_unique_hex_count_stable(self) -> None:
        _, unique, _, _ = self._count_css_hexes()
        self.assertEqual(unique, 671)

    def test_css_token_match_count_not_regressed(self) -> None:
        _, _, exact, _ = self._count_css_hexes()
        self.assertGreaterEqual(exact, 229)

    def test_css_ungoverned_high_freq_colors_not_increased(self) -> None:
        _, _, _, ungoverned = self._count_css_hexes()
        self.assertLessEqual(ungoverned, 22)


class Win11DashboardNoInlineStylesheetTests(QtAppTestCase):
    def test_field_row_spin_width_uses_tokens(self) -> None:
        from PySide6.QtWidgets import QSpinBox

        from src.gui.components.common import FieldRow
        from src.gui.design_tokens import SizeTokens

        spin = QSpinBox()
        row = FieldRow("Title", "Note", spin)
        self.addCleanup(cleanup_widget, row)

        row.set_compact(True)
        self.assertEqual(spin.width(), SizeTokens.FIELD_ROW_SPIN_WIDTH_COMPACT)

        row.set_compact(False)
        self.assertEqual(spin.width(), SizeTokens.FIELD_ROW_SPIN_WIDTH)

    def test_metric_card_min_height_uses_token(self) -> None:
        from src.gui.components.common import MetricCard
        from src.gui.design_tokens import SizeTokens

        card = MetricCard("T", "V")
        self.addCleanup(cleanup_widget, card)
        self.assertEqual(card.minimumHeight(), SizeTokens.METRIC_CARD_MIN_HEIGHT)

    def test_log_panel_button_height_uses_token(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.components.common import LogPanel
        from src.gui.design_tokens import SizeTokens

        panel = LogPanel()
        self.addCleanup(cleanup_widget, panel)
        buttons = panel.findChildren(QPushButton)
        for btn in buttons:
            self.assertEqual(btn.minimumHeight(), SizeTokens.LOG_ACTION_BUTTON_HEIGHT)
            self.assertEqual(btn.maximumHeight(), SizeTokens.LOG_ACTION_BUTTON_HEIGHT)

    def test_log_panel_export_button_emits_signal(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.components.common import LogPanel

        panel = LogPanel(show_export=True)
        self.addCleanup(cleanup_widget, panel)

        buttons = panel.findChildren(QPushButton)
        export_btns = [b for b in buttons if b.text() == "导出"]
        self.assertEqual(len(export_btns), 1)

        emitted = []
        panel.export_requested.connect(lambda: emitted.append(True))
        export_btns[0].click()
        self.assertEqual(emitted, [True])

    def test_log_panel_no_export_button_by_default(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.components.common import LogPanel

        panel = LogPanel()
        self.addCleanup(cleanup_widget, panel)

        buttons = panel.findChildren(QPushButton)
        export_btns = [b for b in buttons if b.text() == "导出"]
        self.assertEqual(len(export_btns), 0)

    def test_log_panel_no_filter_input_by_default(self) -> None:
        from PySide6.QtWidgets import QLineEdit

        from src.gui.components.common import LogPanel

        panel = LogPanel()
        self.addCleanup(cleanup_widget, panel)

        filters = [w for w in panel.findChildren(QLineEdit) if w.property("ui") == "win11-log-filter"]
        self.assertEqual(len(filters), 0)

    def test_log_panel_show_filter_creates_input(self) -> None:
        from PySide6.QtWidgets import QLineEdit

        from src.gui.components.common import LogPanel

        panel = LogPanel(show_filter=True, placeholder="搜索日志...")
        self.addCleanup(cleanup_widget, panel)

        filters = [w for w in panel.findChildren(QLineEdit) if w.property("ui") == "win11-log-filter"]
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].placeholderText(), "搜索日志...")

    def test_switch_button_size_uses_tokens(self) -> None:
        from src.gui.components.buttons import SwitchButton
        from src.gui.design_tokens import SizeTokens

        btn = SwitchButton()
        self.addCleanup(cleanup_widget, btn)
        self.assertEqual(btn.width(), SizeTokens.TOGGLE_WIDTH)
        self.assertEqual(btn.height(), SizeTokens.TOGGLE_HEIGHT)

    def test_combo_popup_height_capped_at_max_token(self) -> None:
        from src.gui.components.combobox import SearchableComboBox
        from src.gui.design_tokens import SizeTokens

        items = [(f"Item {i}", "", f"data_{i}") for i in range(50)]
        combo = SearchableComboBox(items=items)
        self.addCleanup(cleanup_widget, combo)
        combo.show()
        self._app.processEvents()

        combo.show_popup()
        self._app.processEvents()
        self.assertEqual(combo.popup.height(), SizeTokens.COMBO_POPUP_MAX_HEIGHT)

    def test_combo_popup_height_scales_for_few_items(self) -> None:
        from src.gui.components.combobox import SearchableComboBox
        from src.gui.design_tokens import SizeTokens

        items = [(f"Item {i}", "", f"data_{i}") for i in range(2)]
        combo = SearchableComboBox(items=items)
        self.addCleanup(cleanup_widget, combo)
        combo.show()
        self._app.processEvents()

        combo.show_popup()
        self._app.processEvents()
        expected = min(2 * SizeTokens.COMBO_POPUP_ITEM_HEIGHT + SizeTokens.COMBO_POPUP_EXTRA_HEIGHT, SizeTokens.COMBO_POPUP_MAX_HEIGHT)
        self.assertEqual(combo.popup.height(), expected)

    def test_chart_sizes_use_tokens(self) -> None:
        from src.gui.components.charts import HorizontalBarChart, SimpleLineChart, SuccessRateBar
        from src.gui.design_tokens import SizeTokens

        bar_chart = HorizontalBarChart()
        self.addCleanup(cleanup_widget, bar_chart)
        self.assertEqual(bar_chart.minimumHeight(), SizeTokens.CHART_MIN_HEIGHT)

        line_chart = SimpleLineChart()
        self.addCleanup(cleanup_widget, line_chart)
        self.assertEqual(line_chart.minimumHeight(), SizeTokens.CHART_COMPACT_MIN_HEIGHT)

        rate_bar = SuccessRateBar(0.95)
        self.addCleanup(cleanup_widget, rate_bar)
        self.assertEqual(rate_bar.height(), SizeTokens.CHART_BAR_HEIGHT)

    def test_state_widget_layout_uses_tokens(self) -> None:
        from src.gui.components.states import StateWidget
        from src.gui.design_tokens import SpacingTokens

        widget = StateWidget()
        self.addCleanup(cleanup_widget, widget)
        layout = widget.layout()
        margins = layout.contentsMargins()
        self.assertEqual(margins.left(), SpacingTokens.XXL)
        self.assertEqual(margins.top(), SpacingTokens.XXL)
        self.assertEqual(layout.spacing(), SpacingTokens.SM)

    def test_dashboard_page_layout_uses_tokens(self) -> None:
        from src.gui.design_tokens import SizeTokens, SpacingTokens
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.refresh_btn.height(), 40)
        self.assertEqual(page.refresh_btn.width(), 96)
        self.assertEqual(page.dashboard_title_label.font().pointSize(), 24)
        self.assertEqual(page.dashboard_content_layout.spacing(), 9)
        self.assertEqual(page.summary_strip.layout().spacing(), 12)
        self.assertEqual(page.trend_chart.minimumHeight(), 180)
        trend_title = page.trend_card.findChild(QLabel, "dashboard_trend_title")
        self.assertIsNotNone(trend_title)
        self.assertEqual(trend_title.font().pointSize(), 12)
        self.assertEqual(page.trend_card.range_btn.text(), "近7天")
        self.assertEqual(page.trend_card.range_btn.width(), 80)
        self.assertEqual(page.trend_card.range_btn.height(), 28)
        self.assertEqual(page.trend_card.range_btn.property("icon-source"), "chevron_down.svg")
        self.assertFalse(page.trend_card.range_btn.icon().isNull())
        self.assertEqual(len(page.trend_card.legend_swatches), 2)
        self.assertFalse(page.trend_card.legend_swatches[0].pixmap().isNull())
        self.assertFalse(page.trend_card.legend_swatches[1].pixmap().isNull())

    def test_dashboard_table_height_formula_uses_tokens(self) -> None:
        from src.gui.design_tokens import SizeTokens

        rows = 5
        expected = min(SizeTokens.DASHBOARD_TABLE_HEADER_HEIGHT + rows * SizeTokens.DASHBOARD_TABLE_ROW_HEIGHT, SizeTokens.DASHBOARD_TABLE_MAX_HEIGHT)
        self.assertEqual(expected, 24 + 5 * 28)

        rows = 100
        expected = min(SizeTokens.DASHBOARD_TABLE_HEADER_HEIGHT + rows * SizeTokens.DASHBOARD_TABLE_ROW_HEIGHT, SizeTokens.DASHBOARD_TABLE_MAX_HEIGHT)
        self.assertEqual(expected, 220)

    def test_dashboard_status_cards_instantiates(self) -> None:
        from src.gui.pages._dashboard_status_cards import DashboardStatusCards

        cards = DashboardStatusCards()
        self.assertEqual(cards.card_count.title_label.text(), "今日同步次数")
        self.assertEqual(cards.card_rate.title_label.text(), "成功率")
        self.assertEqual(cards.card_fail.title_label.text(), "失败任务")
        self.assertEqual(cards.card_pending.title_label.text(), "待处理异常")
        self.assertEqual(cards.card_duration.title_label.text(), "平均耗时")
        self.assertEqual(cards.card_count.minimumHeight(), 96)
        self.assertEqual(cards.card_count.maximumHeight(), 96)
        self.assertEqual(cards.card_count._icon.width(), 48)
        self.assertEqual(cards.card_count._icon.height(), 48)
        self.assertEqual(cards.card_duration._icon.property("icon-color"), "#2578DA")

    def test_dashboard_status_cards_update_changes_values(self) -> None:
        from src.gui.pages._dashboard_status_cards import DashboardStatusCards

        cards = DashboardStatusCards()
        cards.update(
            task_count="42",
            task_count_sub="较昨日上升",
            task_count_tone="positive",
            rate="98.5%",
            rate_sub="稳定",
            rate_tone="neutral",
            fail_count="2",
            fail_count_sub="较昨日下降",
            fail_count_tone="negative",
            pending_count="1",
            pending_count_sub="需关注",
            pending_count_tone="neutral",
            avg_duration="2.25 秒",
            avg_duration_sub="基于成功执行计算",
            avg_duration_tone="neutral",
        )
        self.assertEqual(cards.card_count.value_label.text(), "42")
        self.assertEqual(cards.card_rate.value_label.text(), "98.5%")
        self.assertEqual(cards.card_fail.value_label.text(), "2")
        self.assertEqual(cards.card_pending.value_label.text(), "1")
        self.assertEqual(cards.card_duration.value_label.text(), "2.25 秒")

    def test_dashboard_page_uses_status_cards_component(self) -> None:
        from src.gui.pages._dashboard_status_cards import DashboardStatusCards
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page._status_cards, DashboardStatusCards)

    def test_dashboard_refresh_uses_real_readonly_sources(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(
            sync_running=False,
            pages={},
            kd_connected=True,
            db_connected=True,
            switch_to_page=lambda *_args, **_kwargs: None,
        )
        today_stats = {
            "sync_count": 7,
            "sync_records": 12245,
            "success_rate": 87.5,
            "fail_count": 2,
            "pending_count": 1,
            "avg_duration": 92.0,
            "yday_count": 5,
            "yday_rate": 80.0,
            "yday_fail_count": 4,
            "yday_pending_count": 2,
            "yday_avg_duration": 120.0,
            "last_sync_time": "2026-06-18 10:20:20",
        }
        trend_rows = [
            {"day": "2026-06-17", "count": 2, "volume": 1000, "rate": 90.0},
            {"day": "2026-06-18", "count": 4, "volume": 2000, "rate": 91.0},
        ]
        history_rows = [
            {
                "start_time_str": "2026-06-18 10:20:20",
                "task_name": "真实物料同步",
                "form_name": "物料",
                "table_name": "T_BD_Material",
                "status": "success",
                "record_count": 221,
                "duration_seconds": 12.4,
            },
            {
                "start_time_str": "2026-06-18 10:00:00",
                "sync_type": "incremental",
                "form_name": "客户",
                "table_name": "T_BD_Customer",
                "status": "failed",
                "message": "接口超时",
                "record_count": 0,
                "duration_seconds": 5,
            },
        ]

        with (
            patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None),
            patch("src.gui.pages.dashboard_page.get_dashboard_today_stats", return_value=today_stats),
            patch("src.gui.pages.dashboard_page.get_trend_days", return_value=trend_rows),
            patch("src.gui.pages.dashboard_page.history_manager.get_history", return_value=(history_rows, 2)),
            patch(
                "src.gui.pages.dashboard_page.history_manager.get_stats",
                return_value={"today_success_rate": "87%", "avg_duration": "92s", "top_failures": ["客户"]},
            ),
        ):
            page = DashboardPage(gui)
            page.refresh_dashboard()

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page._status_cards.card_count.value_label.text(), "7")
        self.assertEqual(page._status_cards.card_rate.value_label.text(), "87.5%")
        self.assertEqual(page._status_cards.card_fail.value_label.text(), "2")
        self.assertEqual(page._status_cards.card_pending.value_label.text(), "1")
        self.assertEqual(page._status_cards.card_duration.value_label.text(), "1 分 22 秒")
        self.assertEqual(page.last_refresh_label.text(), "上次同步：2026-06-18 10:20")

        self.assertEqual(page.trend_chart.data[0]["count"], 1000)
        self.assertEqual(page.trend_chart.data[1]["rate"], 91.0)

        table = page.recent_table.table
        self.assertEqual(table.rowCount(), 2)
        self.assertEqual(table.item(0, 1).text(), "真实物料同步")
        self.assertEqual(table.item(0, 2).text(), "成功")
        self.assertEqual(table.item(0, 4).text(), "221")
        self.assertEqual(table.item(0, 5).text(), "00:00:12")
        self.assertEqual(table.item(1, 2).text(), "失败")

        self.assertEqual(page.risk_items[0]._title.text(), "客户")
        self.assertIn("接口超时", page.risk_items[1]._desc.text())

    def test_dashboard_recent_records_use_markers_and_tooltips(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage, DashboardStatusCell

        gui = SimpleNamespace(
            sync_running=False,
            pages={},
            kd_connected=True,
            db_connected=True,
            switch_to_page=lambda *_args, **_kwargs: None,
        )
        history_rows = [
            {
                "start_time_str": "2026-06-18 10:20:20",
                "task_name": "生产用料清单明细表同步任务",
                "forms_summary": "销售订单, 销售出库单, 生产用料清单明细表",
                "status": "warning",
                "message": "近期失败次数较多，请检查该表单同步日志和字段映射配置",
                "record_count": 112146,
                "duration_seconds": 672,
            }
        ]
        with (
            patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None),
            patch("src.gui.pages.dashboard_page.get_dashboard_today_stats", return_value={"sync_count": 1}),
            patch("src.gui.pages.dashboard_page.get_trend_days", return_value=[]),
            patch("src.gui.pages.dashboard_page.history_manager.get_history", return_value=(history_rows, 1)),
            patch("src.gui.pages.dashboard_page.history_manager.get_stats", return_value={"top_failures": []}),
        ):
            page = DashboardPage(gui)
            page.refresh_dashboard()

        self.addCleanup(cleanup_widget, page)
        table = page.recent_table.table
        self.assertEqual(page.recent_table.height(), 218)
        self.assertEqual(table.horizontalHeader().height(), 26)
        self.assertEqual(table.verticalHeader().defaultSectionSize(), 26)
        self.assertEqual(table.item(0, 0).text(), "2026-06-18 10:20")
        self.assertEqual(table.item(0, 0).toolTip(), "2026-06-18 10:20:20")
        self.assertTrue(table.item(0, 1).text().endswith("..."))
        self.assertEqual(table.item(0, 1).toolTip(), "生产用料清单明细表同步任务")
        self.assertTrue(table.item(0, 2).text().endswith("..."))
        self.assertIn("销售出库单", table.item(0, 2).toolTip())
        status_cell = table.cellWidget(0, 2)
        self.assertIsInstance(status_cell, DashboardStatusCell)
        self.assertEqual(status_cell.mark_label.property("icon-source"), "metric_pending_warning.svg")
        self.assertEqual(status_cell.text_label.property("tone"), "warning")
        self.assertEqual(page.recent_view_all_label.text(), "查看全部记录")
        self.assertEqual(page.recent_view_all_icon.property("icon-source"), "chevron_right.svg")
        self.assertFalse(page.recent_view_all_icon.pixmap().isNull())
        self.assertEqual(page.risk_items[0]._title.toolTip(), "生产用料清单明细表同步任务")
        self.assertIn("字段映射配置", page.risk_items[0]._desc.toolTip())
        self.assertEqual(page.risk_list.height(), 188)
        self.assertEqual(page.risk_items[0].height(), 62)
        self.assertEqual(page.risk_items[0]._icon.property("tone"), "danger")
        self.assertEqual(page.risk_items[1]._icon.property("tone"), "warning")
        self.assertEqual(page.risk_items[0]._icon.width(), 26)
        self.assertEqual(page.risk_view_all_label.text(), "查看全部提醒")
        self.assertEqual(page.risk_view_all_icon.property("icon-source"), "chevron_right.svg")
        self.assertFalse(page.risk_view_all_icon.pixmap().isNull())

    def test_dashboard_view_all_links_navigate_to_target_pages(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        switch_to_page = MagicMock()
        gui = SimpleNamespace(
            sync_running=False,
            pages={},
            kd_connected=True,
            db_connected=True,
            switch_to_page=switch_to_page,
        )
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.recent_view_all_label.mousePressEvent(None)
        page.risk_view_all_label.mousePressEvent(None)

        self.assertEqual(switch_to_page.call_args_list[0].args, ("history",))
        self.assertEqual(switch_to_page.call_args_list[1].args, ("diagnostics",))

    def test_dashboard_empty_sources_do_not_show_static_trend_or_recent_records(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(
            sync_running=False,
            pages={},
            kd_connected=True,
            db_connected=True,
            switch_to_page=lambda *_args, **_kwargs: None,
        )

        with (
            patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None),
            patch("src.gui.pages.dashboard_page.get_dashboard_today_stats", return_value={}),
            patch("src.gui.pages.dashboard_page.get_trend_days", return_value=[]),
            patch("src.gui.pages.dashboard_page.history_manager.get_history", return_value=([], 0)),
            patch("src.gui.pages.dashboard_page.history_manager.get_stats", return_value={}),
        ):
            page = DashboardPage(gui)
            page.refresh_dashboard()

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page._status_cards.card_count.value_label.text(), "0")
        self.assertEqual(page._status_cards.card_rate.value_label.text(), "--")
        self.assertEqual(page._status_cards.card_fail.value_label.text(), "0")
        self.assertEqual(page._status_cards.card_pending.value_label.text(), "0")
        self.assertEqual(page._status_cards.card_duration.value_label.text(), "--")

        self.assertEqual(page.trend_chart.data, [])
        self.assertEqual(page.recent_table.table.rowCount(), 0)
        self.assertFalse(page.recent_table._empty_label.isHidden())
        self.assertEqual(page.recent_table._empty_label.text(), "暂无同步记录")
        self.assertEqual(page.last_refresh_label.text(), "上次同步：--")
        self.assertFalse(page.risk_items[0].isVisible())
        self.assertEqual(page.health_card._rows["kingdee"]["m1_val"].text(), "142 ms")
        self.assertEqual(page.health_card._rows["log"]["m2_val"].text(), "1.2 GB")

    def test_system_health_card_shows_four_services(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage, SystemHealthCard

        gui = SimpleNamespace(sync_running=False, pages={}, kd_connected=True, db_connected=True,
                              switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)
        self.addCleanup(cleanup_widget, page)

        hc = page.health_card
        self.assertIsInstance(hc, SystemHealthCard)
        self.assertEqual(hc.property("ui"), "win11-section-card")
        self.assertEqual(hc._ROW_HEIGHT, 60)
        health_title = hc.findChild(QLabel, "dashboard_health_title")
        self.assertIsNotNone(health_title)
        self.assertEqual(health_title.font().pointSize(), 15)
        self.assertIn("kingdee", hc._rows)
        self.assertIn("database", hc._rows)
        self.assertIn("scheduler", hc._rows)
        self.assertIn("log", hc._rows)
        self.assertEqual(hc._rows["kingdee"]["row_widget"].height(), 60)
        self.assertEqual(hc._rows["kingdee"]["icon"].width(), 26)
        self.assertEqual(hc._rows["kingdee"]["icon"].property("icon-source"), "health_api.svg")
        self.assertEqual(hc._rows["kingdee"]["dot"].property("ui"), "health-status-dot")
        self.assertEqual(hc._rows["kingdee"]["dot"].property("tone"), "success")
        self.assertEqual(hc._rows["kingdee"]["m1_val"].font().pointSize(), 12)
        self.assertEqual(hc._rows["kingdee"]["status_label"].text(), "在线")
        self.assertEqual(hc._rows["database"]["status_label"].text(), "在线")
        self.assertEqual(hc._rows["scheduler"]["status_label"].text(), "在线")
        self.assertEqual(hc._rows["log"]["status_label"].text(), "在线")

    def test_system_health_card_metrics_show_empty_state_without_live_sources(self) -> None:
        from src.gui.pages.dashboard_page import SystemHealthCard

        hc = SystemHealthCard("系统健康")
        self.addCleanup(cleanup_widget, hc)
        hc.set_kingdee(True)
        hc.set_database(True)
        hc.set_scheduler(True, next_time="2026-06-22 10:20:00")
        hc.set_log_service(True)

        self.assertEqual(hc._rows["kingdee"]["m1_title"].text(), "响应时间")
        self.assertEqual(hc._rows["kingdee"]["m1_val"].text(), "--")
        self.assertEqual(hc._rows["kingdee"]["m2_title"].text(), "今日调用")
        self.assertEqual(hc._rows["kingdee"]["m2_val"].text(), "--")

        self.assertEqual(hc._rows["database"]["m1_title"].text(), "响应时间")
        self.assertEqual(hc._rows["database"]["m1_val"].text(), "--")
        self.assertEqual(hc._rows["database"]["m2_title"].text(), "连接数")
        self.assertEqual(hc._rows["database"]["m2_val"].text(), "--")

        self.assertEqual(hc._rows["scheduler"]["m1_title"].text(), "运行时长")
        self.assertEqual(hc._rows["scheduler"]["m1_val"].text(), "--")
        self.assertEqual(hc._rows["scheduler"]["m2_title"].text(), "下次执行")
        self.assertEqual(hc._rows["scheduler"]["m2_val"].text(), "2026-06-22 10:20:00")

        self.assertEqual(hc._rows["log"]["m1_title"].text(), "写入速度")
        self.assertEqual(hc._rows["log"]["m1_val"].text(), "--")
        self.assertEqual(hc._rows["log"]["m2_title"].text(), "日志大小")
        self.assertEqual(hc._rows["log"]["m2_val"].text(), "--")

    def test_dashboard_charts_instantiates(self) -> None:
        from src.gui.pages._dashboard_charts import DashboardCharts

        charts = DashboardCharts()
        self.assertEqual(charts.trend_card.property("ui"), "win11-section-card")
        self.assertEqual(charts.volume_card.property("ui"), "win11-section-card")
        self.assertEqual(charts.trend_chart.minimumHeight(), 200)
        self.assertEqual(charts.volume_chart.minimumHeight(), 240)

    def test_dashboard_charts_range_button_calls_callback(self) -> None:
        from src.gui.pages._dashboard_charts import DashboardCharts

        called_with = []
        charts = DashboardCharts(on_window_days_changed=lambda d: called_with.append(d))
        charts.range_btn_20.click()
        self.assertEqual(called_with, [20])

    def test_dashboard_charts_range_button_same_day_no_callback(self) -> None:
        from src.gui.pages._dashboard_charts import DashboardCharts

        called_with = []
        charts = DashboardCharts(on_window_days_changed=lambda d: called_with.append(d))
        charts.range_btn_7.click()
        self.assertEqual(called_with, [])

    def test_dashboard_page_uses_trend_chart(self) -> None:
        from src.gui.components.charts import DashboardDualLineChart
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page.trend_chart, DashboardDualLineChart)

    def test_dashboard_dual_line_chart_renders_dual_series(self) -> None:
        from src.gui.components.charts import DashboardDualLineChart

        chart = DashboardDualLineChart()
        self.addCleanup(cleanup_widget, chart)
        data = [
            {"day": "2025-05-08", "count": 68000, "rate": 95.5},
            {"day": "2025-05-09", "count": 70000, "rate": 96.0},
            {"day": "2025-05-10", "count": 69000, "rate": 95.7},
            {"day": "2025-05-11", "count": 68000, "rate": 95.8},
            {"day": "2025-05-12", "count": 76000, "rate": 96.5},
            {"day": "2025-05-12", "count": 77000, "rate": 95.2},
            {"day": "2025-05-14", "count": 40000, "rate": 94.8},
        ]
        chart.set_data(data)
        chart.resize(800, 220)
        chart.show()
        self._app.processEvents()
        self.assertEqual(len(chart.data), 7)
        self.assertEqual(chart.data[0]["count"], 68000)
        self.assertEqual(chart.data[6]["rate"], 94.8)
        self.assertEqual(chart.PAD_LEFT, 48)
        self.assertEqual(chart.PAD_RIGHT, 44)
        self.assertEqual(chart.GRID_ALPHA, 78)
        self.assertEqual(chart.BLUE_FILL_TOP, (27, 120, 218, 28))
        self.assertAlmostEqual(chart.POINT_RADIUS, 2.4)

    def test_data_table_instantiates(self) -> None:
        from src.gui.components.data_table import DataTable

        table = DataTable(["Col A", "Col B"])
        self.addCleanup(cleanup_widget, table)
        self.assertEqual(table.table.columnCount(), 2)
        table.show()
        self._app.processEvents()
        self.assertTrue(table._empty_label.isVisible())

    def test_data_table_set_data_and_clear(self) -> None:
        from src.gui.components.data_table import DataTable

        table = DataTable(["Name", "Value"])
        self.addCleanup(cleanup_widget, table)
        table.show()
        self._app.processEvents()

        table.set_data([["A", "1"], ["B", "2"]])
        self.assertEqual(table.table.rowCount(), 2)
        self.assertFalse(table._empty_label.isVisible())

        table.clear()
        self.assertEqual(table.table.rowCount(), 0)
        self.assertTrue(table._empty_label.isVisible())

    def test_dashboard_fail_table_instantiates(self) -> None:
        from src.gui.pages._dashboard_fail_table import DashboardFailTable

        ft = DashboardFailTable()
        self.addCleanup(cleanup_widget, ft)
        self.assertEqual(ft.title_label.text(), "近期失败")

    def test_dashboard_fail_table_click_calls_callback(self) -> None:
        from src.gui.pages._dashboard_fail_table import DashboardFailTable

        clicked_rows = []
        ft = DashboardFailTable(on_row_clicked=lambda r: clicked_rows.append(r))
        self.addCleanup(cleanup_widget, ft)

        ft.set_fail_data(
            [["10:00", "FormA", "失败", "err"]],
            [{"form_name": "FormA", "status": "failed"}],
        )
        ft._handle_row_clicked(0, 0)
        self.assertEqual(clicked_rows, [0])

    def test_dashboard_page_has_target_structure(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsNotNone(page.trend_chart)
        self.assertIsNotNone(page.health_card)
        self.assertIsNotNone(page.recent_table)
        self.assertIsNotNone(page.risk_card)

    def test_data_table_uses_size_tokens(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.design_tokens import SizeTokens

        table = DataTable(["A", "B"])
        self.addCleanup(cleanup_widget, table)
        self.assertEqual(table.table.horizontalHeader().minimumSectionSize(), SizeTokens.DATA_TABLE_MIN_SECTION_WIDTH)
        self.assertEqual(table.table.verticalHeader().defaultSectionSize(), SizeTokens.DATA_TABLE_ROW_HEIGHT)

    def test_dashboard_recent_table_is_data_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page.recent_table, DataTable)

    def test_dashboard_1266x768_integration(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages._dashboard_status_cards import DashboardStatusCards
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        # 目标稿核心组件存在性断言
        self.assertIsInstance(page._status_cards, DashboardStatusCards)
        self.assertIsInstance(page.trend_chart, QWidget)
        self.assertIsInstance(page.recent_table, DataTable)
        self.assertIsNotNone(page.health_card)
        self.assertIsNotNone(page.risk_card)

        # 目标稿无独立 action bar，刷新按钮在 hero 右侧
        self.assertTrue(page.refresh_btn.isVisible())
        self.assertTrue(page.recent_table.isVisible())

    def test_history_page_pagination_uses_tokens(self) -> None:
        from src.gui.design_tokens import SizeTokens, SpacingTokens
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.btn_query.height(), SizeTokens.CONTROL_HEIGHT)
        self.assertEqual(page.btn_export.height(), SizeTokens.HISTORY_EXPORT_BUTTON_HEIGHT)
        self.assertEqual(page.btn_export.width(), SizeTokens.HISTORY_EXPORT_BUTTON_WIDTH)
        self.assertEqual(page.combo_time_range.width(), SizeTokens.HISTORY_FILTER_TIME_WIDTH)
        self.assertEqual(page.combo_type.width(), SizeTokens.HISTORY_FILTER_SELECT_WIDTH)
        self.assertEqual(page.combo_status.width(), SizeTokens.HISTORY_FILTER_SELECT_WIDTH)
        self.assertGreaterEqual(page.search_box.minimumWidth(), SizeTokens.HISTORY_FILTER_SEARCH_MIN_WIDTH)
        self.assertEqual(page.btn_prev.height(), SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.assertEqual(page.btn_next.height(), SizeTokens.PAGINATION_BUTTON_HEIGHT)
        self.assertEqual(page.lbl_curr_page.width(), SizeTokens.HISTORY_PAGINATION_LABEL_WIDTH)
        self.assertEqual(page.jump_box.width(), SizeTokens.PAGINATION_JUMP_WIDTH)
        self.assertEqual(page._filter_panel._grid_layout.horizontalSpacing(), SpacingTokens.LG)
        self.assertEqual(page._filter_panel._grid_layout.verticalSpacing(), SpacingTokens.MD)

    def test_history_page_load_history_calls_manager(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        mock_get = Mock(return_value=([], 0))
        mock_stats = Mock(return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []})
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", mock_get),
            patch("src.gui.pages.history_page.history_manager.get_stats", mock_stats),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.load_history(1)
        mock_get.assert_called()

    def test_history_page_prev_next_page(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        mock_get = Mock(return_value=([], 100))
        mock_stats = Mock(return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []})
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", mock_get),
            patch("src.gui.pages.history_page.history_manager.get_stats", mock_stats),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.current_page = 2
        page.total_records = 100
        page.update_pagination()

        page.next_page()
        self.assertEqual(page.current_page, 4)

        page.prev_page()
        self.assertEqual(page.current_page, 2)

    def test_history_page_apply_quick_filter_sets_controls(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.apply_quick_filter(days=7, status="failed", form_name="FormA")
        self.assertEqual(page.search_box.text(), "FormA")

    def test_history_page_uses_data_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page._data_table, DataTable)
        self.assertIs(page.table, page._data_table.table)

    def test_history_page_load_history_populates_data_table(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        records = [
            {"id": 1, "start_time_str": "10:00:00", "form_name": "FormA", "sync_type": "incremental",
             "record_count": 100, "duration_seconds": 5.0, "status": "success", "message": "OK"},
            {"id": 2, "start_time_str": "11:00:00", "form_name": "FormB", "sync_type": "full",
             "record_count": 200, "duration_seconds": 10.0, "status": "failed", "message": "Error"},
        ]
        mock_get = Mock(return_value=(records, 2))
        mock_stats = Mock(return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []})
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", mock_get),
            patch("src.gui.pages.history_page.history_manager.get_stats", mock_stats),
        ):
            page = HistoryPage(gui)
            self.addCleanup(cleanup_widget, page)
            self.assertEqual(page.table.rowCount(), 2)

    def test_history_page_matches_target_structure_and_real_data(self) -> None:
        from src.gui.pages.history_page import HistoryMetricCard, HistoryPage, HistoryRateCard, HistoryStatusTag

        records = [
            {
                "id": 1,
                "start_time_str": "2026-06-22 10:15:22",
                "task_name": "真实物料同步",
                "form_name": "T_BD_Material",
                "status": "success",
                "record_count": 8542,
                "duration_seconds": 92,
                "message": "",
            },
            {
                "id": 2,
                "start_time_str": "2026-06-22 10:05:18",
                "task_name": "真实销售同步",
                "form_name": "T_SAL_SaleOrder",
                "status": "failed",
                "record_count": 128,
                "duration_seconds": 45,
                "message": "字段映射错误：FNumber",
            },
        ]
        stats = {
            "today_success_rate": "82.45%",
            "avg_duration": "72s",
            "fail_count": 202,
            "total_records_synced": 1224567,
            "total_updated": 922456,
            "success_count": 1252,
            "not_run_count": 85,
            "duration_delta": "较昨日 ↓ 8.25%",
            "fail_delta": "较昨日 ↓ 12.76%",
            "rows_delta": "较昨日 ↑ 15.21%",
            "updates_delta": "较昨日 ↑ 11.47%",
        }
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=(records, 1640)),
            patch("src.gui.pages.history_page.history_manager.get_stats", return_value=stats),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.page_title.text(), "同步历史")
        self.assertEqual(page.btn_export.text(), "导出")
        self.assertEqual(page._filter_panel.property("ui"), "history-filter-bar")
        self.assertFalse(page._filter_panel.title_label.isVisible())
        self.assertEqual(page._filter_panel._grid_layout.rowCount(), 1)
        self.assertEqual(page.search_box.placeholderText(), "请输入任务名称")
        self.assertEqual(page.btn_reset.text(), "重置")

        self.assertIsInstance(page.card_rate, HistoryRateCard)
        for card in (page.card_duration, page.card_fail, page.card_rows, page.card_updates):
            self.assertIsInstance(card, HistoryMetricCard)
        self.assertEqual(page.card_rate.value_label.text(), "82.45%")
        self.assertIn("成功", page.card_rate.detail_label.text())
        self.assertEqual(page.card_duration.value_label.text(), "00:01:12")
        self.assertEqual(page.card_fail.value_label.text(), "202")
        self.assertEqual(page.card_rows.value_label.text(), "1,224,567")
        self.assertEqual(page.card_updates.value_label.text(), "922,456")

        self.assertEqual(page.table.rowCount(), 2)
        self.assertEqual(page.table.item(0, 1).text(), "真实物料同步")
        self.assertEqual(page.table.item(0, 4).text(), "8,542")
        self.assertEqual(page.table.item(0, 5).text(), "92")
        tag = page.table.cellWidget(0, 2)
        self.assertIsInstance(tag, HistoryStatusTag)
        self.assertEqual(tag.label.text(), "成功")
        self.assertEqual(tag.property("tone"), "success")

        self.assertEqual(page._pagination_card.page_size_combo.currentText(), "10")
        self.assertEqual(page._pagination_card.lbl_page_info.text(), "共 1,640 条")
        self.assertEqual(page._pagination_card.lbl_curr_page.text(), "1")

    def test_history_page_load_history_empty_shows_empty_state(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        mock_get = Mock(return_value=([], 0))
        mock_stats = Mock(return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []})
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", mock_get),
            patch("src.gui.pages.history_page.history_manager.get_stats", mock_stats),
        ):
            page = HistoryPage(gui)
            self.addCleanup(cleanup_widget, page)
            self.assertEqual(page.table.rowCount(), 0)
            self.assertEqual(page._data_table._empty_label.text(), "当前筛选条件下没有匹配的历史记录。")

    def test_history_page_table_row_height_uses_token(self) -> None:
        from src.gui.design_tokens import SizeTokens
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.table.verticalHeader().defaultSectionSize(), SizeTokens.HISTORY_TABLE_ROW_HEIGHT)
        self.assertEqual(page.table.horizontalHeader().height(), SizeTokens.HISTORY_TABLE_HEADER_HEIGHT)

    def test_history_filter_panel_responsive_compact(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()
        self.assertFalse(page._filter_panel._grid.property("compact"))

    def test_history_filter_panel_responsive_wide(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1600, 900)
        page.show()
        self._app.processEvents()
        self.assertFalse(page._filter_panel._grid.property("compact"))

    def test_history_filter_panel_properties(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        panel = HistoryFilterPanel()
        self.addCleanup(cleanup_widget, panel)
        panel.combo_time_range.setCurrentIndex(1)
        self.assertEqual(panel.selected_days, 7)
        self.assertEqual(panel.selected_status, None)
        self.assertEqual(panel.search_text, "")

    def test_history_filter_panel_sync_type_options_do_not_show_legacy_full_text(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        panel = HistoryFilterPanel()
        self.addCleanup(cleanup_widget, panel)

        type_labels = [panel.combo_type.itemText(index) for index in range(panel.combo_type.count())]
        type_values = [panel.combo_type.itemData(index) for index in range(panel.combo_type.count())]

        self.assertEqual(type_labels, ["全部", "增量", "完全"])
        self.assertEqual(type_values, [None, "incremental", "complete"])

    def test_history_filter_panel_set_quick_filter(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        panel = HistoryFilterPanel()
        self.addCleanup(cleanup_widget, panel)
        panel.set_quick_filter(days=20, status="failed", form_name="FormA")
        self.assertEqual(panel.selected_days, 20)
        self.assertEqual(panel.selected_status, "failed")
        self.assertEqual(panel.search_text, "FormA")

    def test_history_filter_panel_return_pressed_triggers_callback(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        called = []
        panel = HistoryFilterPanel(on_query=lambda: called.append(True))
        self.addCleanup(cleanup_widget, panel)
        panel.search_box.returnPressed.emit()
        self.assertEqual(called, [True])

    def test_history_filter_panel_editing_finished_triggers_query_once(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        called = []
        panel = HistoryFilterPanel(on_query=lambda: called.append(True))
        self.addCleanup(cleanup_widget, panel)

        panel.search_box.setText("物料")
        panel.search_box.editingFinished.emit()
        self.assertEqual(called, [True])

        panel.search_box.returnPressed.emit()
        panel.search_box.editingFinished.emit()
        self.assertEqual(called, [True])

    def test_history_filter_panel_combo_changes_trigger_query(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        called = []
        panel = HistoryFilterPanel(on_query=lambda: called.append(True))
        self.addCleanup(cleanup_widget, panel)

        panel.combo_time_range.setCurrentIndex(1)
        self.assertEqual(called, [True])

        panel._last_auto_query_at = 0
        panel.combo_type.setCurrentIndex(1)
        self.assertEqual(called, [True, True])

        panel._last_auto_query_at = 0
        panel.combo_status.setCurrentIndex(1)
        self.assertEqual(called, [True, True, True])

    def test_history_filter_panel_programmatic_updates_do_not_auto_query(self) -> None:
        from src.gui.pages._history_filter_panel import HistoryFilterPanel

        called = []
        panel = HistoryFilterPanel(on_query=lambda: called.append(True))
        self.addCleanup(cleanup_widget, panel)

        panel.set_quick_filter(days=20, status="failed", form_name="FormA")
        panel.reset_filters()

        self.assertEqual(called, [])

    def test_history_pagination_card_instantiates(self) -> None:
        from src.gui.pages._history_pagination_card import HistoryPaginationCard

        card = HistoryPaginationCard()
        self.addCleanup(cleanup_widget, card)
        self.assertEqual(card.property("ui"), "win11-pagination-card")
        self.assertEqual(card.btn_prev.property("icon-source"), "chevron_left.svg")
        self.assertEqual(card.btn_next.property("icon-source"), "chevron_right.svg")
        self.assertFalse(card.btn_prev.icon().isNull())
        self.assertFalse(card.btn_next.icon().isNull())
        self.assertEqual(card.page_size_combo.currentText(), "10")
        self.assertEqual(card.lbl_curr_page.property("ui"), "win11-page-badge")
        self.assertEqual(card.lbl_page_info.property("ui"), "history-page-info")
        self.assertEqual(card.jump_box.property("td"), "win11-input")
        self.assertEqual(card.height(), 46)

    def test_history_pagination_card_update_state_first_page(self) -> None:
        from src.gui.pages._history_pagination_card import HistoryPaginationCard

        card = HistoryPaginationCard()
        self.addCleanup(cleanup_widget, card)
        card.update_state(1, 0, 20)
        self.assertFalse(card.btn_prev.isEnabled())
        self.assertFalse(card.btn_next.isEnabled())
        self.assertEqual(card.lbl_curr_page.text(), "1")
        self.assertEqual(card.jump_box.maximum(), 1)

    def test_history_pagination_card_update_state_middle_page(self) -> None:
        from src.gui.pages._history_pagination_card import HistoryPaginationCard

        card = HistoryPaginationCard()
        self.addCleanup(cleanup_widget, card)
        card.update_state(2, 100, 20)
        self.assertTrue(card.btn_prev.isEnabled())
        self.assertTrue(card.btn_next.isEnabled())
        visible_pages = [button.text() for button in card._page_buttons if not button.isHidden()]
        self.assertEqual(visible_pages, ["1", "2", "2", "4", "5"])
        self.assertEqual(visible_pages.count("2"), 1)
        self.assertEqual(card._page_buttons[1].property("ui"), "win11-page-badge")
        self.assertFalse(card._page_buttons[1].isEnabled())
        self.assertEqual(card.jump_box.maximum(), 5)

    def test_history_pagination_card_number_buttons_jump_to_page(self) -> None:
        from src.gui.pages._history_pagination_card import HistoryPaginationCard

        jumped = []
        card = HistoryPaginationCard(on_jump=lambda page: jumped.append(page))
        self.addCleanup(cleanup_widget, card)
        card.update_state(1, 100, 20)

        card._page_buttons[1].click()
        self.assertEqual(jumped, [2])

        card.update_state(1, 217, 20)
        visible_pages = [button.text() for button in card._page_buttons if not button.isHidden()]
        self.assertEqual(visible_pages, ["1", "2", "2", "4", "5", "...", "11"])
        card._page_buttons[-1].click()
        self.assertEqual(jumped, [2, 11])

    def test_history_page_uses_pagination_card(self) -> None:
        from src.gui.pages._history_pagination_card import HistoryPaginationCard
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page._pagination_card, HistoryPaginationCard)
        self.assertIs(page.btn_prev, page._pagination_card.btn_prev)
        self.assertIs(page.btn_next, page._pagination_card.btn_next)

    def test_history_page_1266x768_integration(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages._history_filter_panel import HistoryFilterPanel
        from src.gui.pages._history_pagination_card import HistoryPaginationCard
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertIsInstance(page._filter_panel, HistoryFilterPanel)
        self.assertIsInstance(page._data_table, DataTable)
        self.assertIsInstance(page._pagination_card, HistoryPaginationCard)

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertFalse(primary_actions.isVisible())
        self.assertTrue(page.btn_query.isVisible())
        self.assertTrue(page.btn_export.isVisible())

    def test_history_page_prev_next_updates_current_page(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        mock_get = Mock(return_value=([], 100))
        mock_stats = Mock(return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []})
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", mock_get),
            patch("src.gui.pages.history_page.history_manager.get_stats", mock_stats),
        ):
            page = HistoryPage(gui)
            self.addCleanup(cleanup_widget, page)

            page.current_page = 2
            page.total_records = 100
            page.page_size = 20
            page.update_pagination()

            page.btn_prev.click()
            self.assertEqual(page.current_page, 2)

            page.btn_next.click()
            self.assertEqual(page.current_page, 2)

    def test_history_page_jump_box_triggers_load(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        mock_get = Mock(return_value=([], 100))
        mock_stats = Mock(return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []})
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", mock_get),
            patch("src.gui.pages.history_page.history_manager.get_stats", mock_stats),
        ):
            page = HistoryPage(gui)
            self.addCleanup(cleanup_widget, page)

            page.current_page = 1
            page.total_records = 100
            page.page_size = 20
            page.update_pagination()

            page.jump_box.setValue(2)
            page.jump_box.editingFinished.emit()
            self.assertEqual(page.current_page, 2)

    def test_history_page_export_data_copies_to_clipboard(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.current_records = [{"id": 1, "form_name": "FormA"}]
        page.table.setRowCount(1)
        page.table.setItem(0, 0, __import__("PySide6.QtWidgets", fromlist=["QTableWidgetItem"]).QTableWidgetItem("1"))
        page.table.setItem(0, 2, __import__("PySide6.QtWidgets", fromlist=["QTableWidgetItem"]).QTableWidgetItem("FormA"))

        with (
            patch("src.gui.pages.history_page.QApplication") as mock_app,
            patch("src.gui.pages.history_page.UiFeedback") as mock_fb,
        ):
            mock_clipboard = Mock()
            mock_app.clipboard.return_value = mock_clipboard
            page.export_data()
            mock_clipboard.setText.assert_called_once()
            mock_fb.success.assert_called_once()

    def test_history_page_export_data_shows_info_when_empty(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch(
                "src.gui.pages.history_page.history_manager.get_stats",
                return_value={"today_success_rate": "0%", "avg_duration": "0s", "top_failures": []},
            ),
        ):
            page = HistoryPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.current_records = []

        with patch("src.gui.pages.history_page.UiFeedback") as mock_fb:
            page.export_data()
            mock_fb.info.assert_called_once()
            mock_fb.success.assert_not_called()

    def test_log_panel_text_has_both_ui_and_class_properties(self) -> None:
        from src.gui.components.common import LogPanel

        panel = LogPanel()
        self.addCleanup(cleanup_widget, panel)
        self.assertEqual(panel.log_text.property("ui"), "win11-log-text")
        self.assertEqual(panel.log_text.property("class"), "win11-log")

    def test_log_panel_has_toolbar_host_frame(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.components.common import LogPanel

        panel = LogPanel()
        self.addCleanup(cleanup_widget, panel)
        toolbar_hosts = [w for w in panel.findChildren(QFrame) if w.property("ui") == "win11-log-toolbar"]
        self.assertEqual(len(toolbar_hosts), 1)

    def test_sync_page_no_longer_embeds_log_copy_button(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)

        self.assertFalse(hasattr(page, "_log_panel"))
        self.assertFalse(hasattr(page, "log_text"))

    def test_sync_page_does_not_embed_log_panel(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertFalse(hasattr(page, "_log_panel"))
        self.assertFalse(hasattr(page, "log_card"))

    def test_sync_page_append_log_uses_internal_buffer(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.append_log("test message", "INFO")
        self.assertIn("test message", "\n".join(page.log_entries))

    def test_sync_page_1266x768_integration(self) -> None:
        from PySide6.QtWidgets import QProgressBar

        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.start_sync_btn.isVisible())
        self.assertTrue(page.test_conn_btn.isVisible())
        self.assertIsNotNone(page.progress_bar)
        self.assertIsNotNone(page.progress_status_lbl)

    def test_sync_progress_card_instantiates(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages._sync_progress_card import SyncProgressCard

        card = SyncProgressCard()
        self.addCleanup(cleanup_widget, card)
        self.assertIsInstance(card, QFrame)
        self.assertEqual(card.property("ui"), "win11-progress-card")
        self.assertEqual(card.progress_bar.value(), 0)
        self.assertEqual(card.progress_status_lbl.text(), "等待中")

    def test_sync_progress_card_set_progress(self) -> None:
        from src.gui.pages._sync_progress_card import SyncProgressCard

        card = SyncProgressCard()
        self.addCleanup(cleanup_widget, card)
        card.set_progress(50, "50%")
        self.assertEqual(card.progress_bar.value(), 50)
        self.assertEqual(card.progress_status_lbl.text(), "50%")

    def test_sync_progress_card_set_status(self) -> None:
        from src.gui.pages._sync_progress_card import SyncProgressCard

        card = SyncProgressCard()
        self.addCleanup(cleanup_widget, card)
        card.set_status("运行中")
        self.assertEqual(card.progress_status_lbl.text(), "运行中")

    def test_sync_progress_card_reset(self) -> None:
        from src.gui.pages._sync_progress_card import SyncProgressCard

        card = SyncProgressCard()
        self.addCleanup(cleanup_widget, card)
        card.set_progress(80, "80%")
        card.reset()
        self.assertEqual(card.progress_bar.value(), 0)
        self.assertEqual(card.progress_status_lbl.text(), "等待中")

    def test_sync_page_uses_progress_card(self) -> None:
        from src.gui.pages._sync_progress_card import SyncProgressCard
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page._progress_card, SyncProgressCard)
        self.assertIs(page.progress_bar, page._progress_card.progress_bar)
        self.assertIs(page.progress_status_lbl, page._progress_card.progress_status_lbl)

    def test_sync_page_on_sync_progress_updates_progress(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.on_sync_progress("进度 50%", 50)
        self.assertEqual(page.progress_bar.value(), 50)
        self.assertEqual(page.progress_status_lbl.text(), "50%")

    def test_sync_page_on_sync_finished_sets_progress_full(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        result = {"status": "success", "message": "OK", "total_records": 100, "inserted": 100, "updated": 0, "failed": 0, "duration": 5.0, "details": {}}
        page.start_sync_btn.set_loading(True)
        page.on_sync_finished(result)
        self.assertEqual(page.progress_bar.value(), 100)
        self.assertFalse(page.start_sync_btn._is_loading)
        self.assertEqual(page.run_state_badge.text(), "成功")
        self.assertEqual(page.progress_status_lbl.text(), "成功")
        self.assertEqual(page.start_sync_btn.text(), "同步成功")

    def test_dashboard_progress_bar_uses_tone_property(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)

        from PySide6.QtWidgets import QProgressBar

        bars = page.findChildren(QProgressBar)
        for bar in bars:
            ss = bar.styleSheet()
            self.assertEqual(ss, "", f"QProgressBar still has inline setStyleSheet: {ss[:80]}")


class Win11TaskManagementPageTests(QtAppTestCase):
    def test_task_management_page_matches_target_structure_and_real_data(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.task_management_page import TaskDetailPanel, TaskManagementPage, TaskMetricCard

        tasks = [
            {
                "task_name": "真实物料任务",
                "form_name": "T_BD_Material",
                "sync_mode": "增量同步",
                "schedule": "每 5 分钟",
                "status": "enabled",
                "last_run": "2026-06-22 10:15:22",
                "success_rate": "98.75%",
                "task_id": "task-real-001",
                "created_at": "2026-06-20 14:20:22",
                "creator": "管理员",
                "updated_at": "2026-06-22 10:15:22",
                "scope": "物料基础资料",
                "increment_field": "FModifyDate",
                "target_table": "T_BD_Material",
                "retry_policy": "失败后重试 2 次，间隔 5 分钟",
                "last_error_time": "",
                "last_error_message": "",
                "error_count": "0/2",
            },
            {
                "task_name": "真实失败任务",
                "form_name": "T_AR_ReceiveBill",
                "sync_mode": "增量同步",
                "schedule": "每 10 分钟",
                "status": "failed",
                "last_run": "2026-06-22 09:45:12",
                "success_rate": "85.22%",
                "task_id": "task-real-002",
                "created_at": "2026-06-21 09:00:00",
                "creator": "管理员",
                "updated_at": "2026-06-22 09:45:12",
                "scope": "收款单",
                "increment_field": "FModifyDate",
                "target_table": "T_AR_ReceiveBill",
                "retry_policy": "失败后重试 2 次，间隔 5 分钟",
                "last_error_time": "2026-06-22 09:45:12",
                "last_error_message": "数据库连接超时",
                "error_count": "2/2",
            },
        ]
        stats = {
            "enabled": 12,
            "paused": 2,
            "executed_today": 28,
            "retry": 4,
            "enabled_delta": "较昨日 ↑ 10.24%",
            "paused_delta": "较昨日 ↓ 16.67%",
            "executed_delta": "较昨日 ↑ 27.27%",
            "retry_delta": "较昨日 ↓ 20.00%",
            "total": 27,
        }
        service = SimpleNamespace(get_tasks=Mock(return_value=tasks), get_task_stats=Mock(return_value=stats))
        gui = SimpleNamespace(task_service=service)

        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.property("page"), "task-management")
        self.assertEqual(page.page_title.text(), "任务管理")
        self.assertEqual(page.btn_new_task.text(), "+ 新建任务")
        self.assertEqual(page.btn_batch_enable.text(), "批量启用")
        self.assertEqual(page.filter_bar.property("ui"), "task-filter-bar")
        self.assertEqual(page.combo_status.currentText(), "全部状态")
        self.assertEqual(page.combo_type.currentText(), "全部类型")
        self.assertEqual(page.combo_mode.currentText(), "全部方式")
        self.assertEqual(
            [page.combo_mode.itemText(index) for index in range(page.combo_mode.count())],
            ["全部方式", "增量同步", "完全同步"],
        )
        self.assertEqual(page.search_box.placeholderText(), "搜索任务名称或表单")
        self.assertEqual(page.page_size_combo.property("td"), "win11-input")

        for card in (page.card_enabled, page.card_paused, page.card_executed, page.card_retry):
            self.assertIsInstance(card, TaskMetricCard)
        self.assertEqual(page.card_enabled.icon.property("icon-source"), "icons/schedule_running.svg")
        self.assertEqual(page.card_paused.icon.property("icon-source"), "icons/schedule_status.svg")
        self.assertEqual(page.card_executed.icon.property("icon-source"), "icons/data_source_database.svg")
        self.assertEqual(page.card_retry.icon.property("icon-source"), "icons/metric_pending_warning.svg")
        self.assertEqual(page.card_enabled.value_label.text(), "12")
        self.assertEqual(page.card_paused.value_label.text(), "2")
        self.assertEqual(page.card_executed.value_label.text(), "28")
        self.assertEqual(page.card_retry.value_label.text(), "4")

        self.assertIsInstance(page.task_table, DataTable)
        self.assertEqual(page.table.rowCount(), 2)
        self.assertEqual(page.table.item(0, 0).text(), "真实物料任务")
        self.assertEqual(page.table.item(0, 1).text(), "T_BD_Material")
        self.assertEqual(page.table.item(0, 6).text(), "98.75%")
        self.assertIsInstance(page.detail_panel, TaskDetailPanel)
        self.assertEqual(page.detail_panel.title_label.text(), "真实物料任务")
        self.assertIn("task-real-001", page.detail_panel.basic_info_value.text())
        self.assertEqual(page.lbl_total.text(), "共 27 条")

        service.get_tasks.assert_called_once()
        service.get_task_stats.assert_called_once()

    def test_task_management_filters_auto_query_and_pass_filters_when_supported(self) -> None:
        from src.gui.pages import task_management_page as module
        from src.gui.pages.task_management_page import TaskManagementPage, TaskStatusTag

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([], 0)),
            get_task_stats=Mock(return_value={"total": 0}),
        )
        gui = SimpleNamespace(task_service=service)
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)
        service.get_tasks.reset_mock()

        page.combo_status.setCurrentIndex(1)
        service.get_tasks.assert_called_once_with(filters={"status": "启用中"}, page=1, page_size=10)

        service.get_tasks.reset_mock()
        page.search_box.setText("物料")
        page.search_box.editingFinished.emit()
        service.get_tasks.assert_called_once()
        self.assertEqual(service.get_tasks.call_args.kwargs["filters"]["keyword"], "物料")

        service.get_tasks.reset_mock()
        page.btn_filter.click()
        self.assertEqual(service.get_tasks.call_args.kwargs["filters"]["status"], "启用中")
        self.assertEqual(service.get_tasks.call_args.kwargs["filters"]["keyword"], "物料")

    def test_task_management_title_actions_call_task_service(self) -> None:
        from src.gui.pages.task_management_page import TaskEditorDialog, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=[{"task_name": "真实待启用任务", "status": "paused"}]),
            get_task_stats=Mock(return_value={"total": 1}),
            get_form_options=Mock(return_value=[("真实待启用任务", "T_REAL")]),
            batch_enable_tasks=Mock(return_value=2),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        service.get_tasks.reset_mock()

        page.btn_new_task.click()
        self.assertIsInstance(page.task_editor_dialog, TaskEditorDialog)
        self.assertEqual(page.last_action_feedback, "新建任务：已打开任务配置")

        page.btn_batch_enable.click()
        service.batch_enable_tasks.assert_called_once()
        self.assertEqual(page.last_action_feedback, "批量启用：已启用 2 个任务")
        self.assertGreaterEqual(service.get_tasks.call_count, 1)

    def test_task_management_uses_default_task_service_when_gui_has_no_service(self) -> None:
        from src.gui.pages.task_management_page import TaskEditorDialog, TaskManagementPage

        task_service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "默认服务任务", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            get_form_options=Mock(return_value=[("默认服务任务", "T_DEFAULT")]),
        )
        with patch("src.gui.pages.task_management_page.default_task_service", task_service):
            page = TaskManagementPage(SimpleNamespace())

            self.assertEqual(page.table.item(0, 0).text(), "默认服务任务")
            page.btn_new_task.click()
        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page.task_editor_dialog, TaskEditorDialog)
        self.assertEqual(page.last_action_feedback, "新建任务：已打开任务配置")

    def test_task_management_renders_tasks_from_injected_task_service(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage, TaskStatusTag

        task_service = SimpleNamespace(
            get_tasks=Mock(
                return_value=(
                    [
                        {"task_name": "物料基础资料同步", "form_name": "T_BD_Material", "status": "enabled"},
                        {"task_name": "客户资料同步", "form_name": "T_BD_Customer", "status": "paused"},
                    ],
                    2,
                )
            ),
            get_task_stats=Mock(return_value={"total": 2}),
        )
        gui = SimpleNamespace(task_service=task_service)
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.table.rowCount(), 2)
        self.assertEqual(page.table.item(0, 0).text(), "物料基础资料同步")
        self.assertEqual(page.table.item(0, 1).text(), "T_BD_Material")
        self.assertEqual(page.table.item(1, 0).text(), "客户资料同步")
        self.assertEqual(page.table.item(1, 1).text(), "T_BD_Customer")
        self.assertEqual(page.lbl_total.text(), "共 2 条")
        task_service.get_tasks.assert_called()

    def test_task_management_filter_reset_queries_once_and_combo_arrow_uses_uploaded_icon(self) -> None:
        import os

        from src.gui.pages.task_management_page import TaskManagementPage

        service = SimpleNamespace(get_tasks=Mock(return_value=[]), get_task_stats=Mock(return_value={"total": 0}))
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        page.combo_status.setCurrentIndex(1)
        page.combo_type.setCurrentIndex(1)
        page.search_box.setText("物料")
        service.get_tasks.reset_mock()

        page.btn_reset.click()

        service.get_tasks.assert_called_once()
        self.assertEqual(page.combo_status.currentIndex(), 0)
        self.assertEqual(page.combo_type.currentIndex(), 0)
        self.assertEqual(page.combo_mode.currentIndex(), 0)
        self.assertEqual(page.search_box.text(), "")

        stylesheet_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css")
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()
        self.assertIn('QWidget[page="task-management"] QComboBox[td="win11-input"]::down-arrow', css)
        self.assertIn('image: url("assets/icons/下_down.svg")', css)
        self.assertIn("padding: 0px 22px 0px 14px", css)
        self.assertIn("width: 22px", css)
        self.assertIn("width: 10px", css)

        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons", "下_down.svg")
        with open(icon_path, encoding="utf-8") as icon_file:
            icon_svg = icon_file.read()
        self.assertIn('viewBox="0 0 20 20"', icon_svg)
        self.assertIn('fill="currentColor"', icon_svg)
        self.assertNotIn("stroke-linecap", icon_svg)

    def test_task_management_pagination_buttons_and_page_size_query_service(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage

        first_page = ([{"task_name": f"任务{i}", "status": "enabled"} for i in range(1, 11)], 22)
        second_page = ([{"task_name": f"任务{i}", "status": "enabled"} for i in range(11, 21)], 22)
        twenty_page = ([{"task_name": f"任务{i}", "status": "enabled"} for i in range(1, 21)], 22)
        service = SimpleNamespace(
            get_tasks=Mock(side_effect=[first_page, second_page, twenty_page]),
            get_task_stats=Mock(return_value={"total": 22}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.current_page, 1)
        self.assertEqual(page.total_pages, 2)
        self.assertFalse(page.btn_prev.isEnabled())
        self.assertTrue(page.btn_next.isEnabled())
        self.assertEqual(page.btn_page_1.text(), "1")
        self.assertEqual(page.btn_page_2.text(), "2")
        self.assertTrue(page.btn_page_1.isChecked())

        page.btn_next.click()
        self.assertEqual(page.current_page, 2)
        self.assertEqual(service.get_tasks.call_args.kwargs, {"filters": {}, "page": 2, "page_size": 10})
        self.assertTrue(page.btn_prev.isEnabled())
        self.assertTrue(page.btn_page_2.isChecked())
        self.assertEqual(page.table.item(0, 0).text(), "任务11")

        page.page_size_combo.setCurrentIndex(1)
        self.assertEqual(page.current_page, 1)
        self.assertEqual(service.get_tasks.call_args.kwargs, {"filters": {}, "page": 1, "page_size": 20})
        self.assertEqual(page.total_pages, 2)

    def test_task_management_page_instantiates(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage

        gui = SimpleNamespace()
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("ui"), "win11-page")

    def test_task_management_page_has_summary_cards(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage, TaskMetricCard

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "物料基础资料同步", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(return_value={"status": "success"}),
            pause_task=Mock(return_value=1),
        )
        gui = SimpleNamespace(task_service=service)
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)

        cards = page.findChildren(TaskMetricCard)
        self.assertGreaterEqual(len(cards), 4, "Expected at least 4 TaskMetricCard summary cards")

    def test_task_management_page_has_data_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.task_management_page import TaskManagementPage

        gui = SimpleNamespace()
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)

        tables = page.findChildren(DataTable)
        self.assertGreaterEqual(len(tables), 1, "Expected at least 1 DataTable")

    def test_task_management_page_has_action_buttons(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.pages.task_management_page import TaskManagementPage

        gui = SimpleNamespace()
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)

        buttons = page.findChildren(QPushButton)
        btn_texts = [b.text() for b in buttons]
        self.assertTrue(any("新建任务" in t for t in btn_texts), "Expected '新建任务' button")

    def test_task_management_page_1266x768(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage, TaskMetricCard

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "物料基础资料同步", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(return_value={"status": "success"}),
            pause_task=Mock(return_value=1),
        )
        gui = SimpleNamespace(task_service=service)
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        cards = page.findChildren(TaskMetricCard)
        self.assertGreaterEqual(len(cards), 4)
        for card in cards:
            self.assertTrue(card.isVisible())

    def test_task_management_pixel_refinement_guards(self) -> None:
        from PySide6.QtCore import QPoint, Qt

        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        gui = SimpleNamespace()
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.table.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertGreaterEqual(page.table.columnWidth(0), 170)
        self.assertGreaterEqual(page.table.columnWidth(1), 118)
        self.assertGreaterEqual(page.table.columnWidth(5), 120)
        self.assertLessEqual(page.detail_panel.width(), 212)
        self.assertIsInstance(page.table.cellWidget(0, 7), TaskActionCell)
        self.assertEqual(page.filter_bar.maximumHeight(), 64)
        self.assertEqual(page.pagination_card.height(), 46)
        self.assertEqual(page.btn_prev.text(), "←")
        self.assertEqual(page.btn_next.text(), "→")
        self.assertEqual(page.btn_page_1.width(), 42)
        self.assertEqual(page.btn_page_1.height(), 24)
        self.assertFalse(hasattr(page, "jump_box"))

        metric_top = page.card_enabled.mapTo(page, QPoint(0, 0)).y()
        detail_top = page.detail_panel.mapTo(page, QPoint(0, 0)).y()
        self.assertLessEqual(abs(detail_top - metric_top), 4)
        self.assertGreaterEqual(page.detail_panel.width(), 200)
        self.assertGreaterEqual(page.table.viewport().width(), 1080)
        self.assertFalse(hasattr(page.detail_panel, "btn_close"))
        self.assertIsNone(page.detail_panel.findChild(type(page.btn_reset), "task_detail_close"))

        detail_bottom = page.detail_panel.mapTo(page, page.detail_panel.rect().bottomRight()).y()
        pagination_bottom = page.pagination_card.mapTo(page, page.pagination_card.rect().bottomRight()).y()
        self.assertLessEqual(abs(detail_bottom - pagination_bottom), 4)

        visible_columns_width = sum(page.table.columnWidth(column) for column in range(page.table.columnCount()))
        self.assertLessEqual(abs(page.table.viewport().width() - visible_columns_width), 8)
        self.assertGreaterEqual(page.card_enabled.height(), 112)
        self.assertEqual(page.table.currentRow(), 0)

    def test_task_management_table_columns_preserve_target_text(self) -> None:
        from PySide6.QtCore import Qt

        from src.gui.pages.task_management_page import TaskManagementPage

        gui = SimpleNamespace()
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.table.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertTrue(page.table.item(0, 0).text())
        self.assertTrue(page.table.item(0, 1).text())
        self.assertTrue(page.table.item(0, 5).text())
        self.assertEqual(page.table.item(0, 7).text(), "")
        self.assertGreaterEqual(page.table.columnWidth(5), 154)
        self.assertLessEqual(page.table.columnWidth(7), 92)

    def test_task_management_tooltips_and_selected_row_highlight(self) -> None:
        from PySide6.QtWidgets import QAbstractItemView

        from src.gui.pages.task_management_page import TaskManagementPage

        gui = SimpleNamespace()
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.table.hasMouseTracking())
        self.assertEqual(page.table.selectionBehavior(), QAbstractItemView.SelectionBehavior.SelectRows)
        self.assertEqual(page.table.selectionMode(), QAbstractItemView.SelectionMode.ExtendedSelection)
        self.assertEqual(page.table.item(0, 2).toolTip(), page.table.item(0, 2).text())
        self.assertEqual(page.table.item(0, 2).toolTip(), page.table.item(0, 2).text())
        self.assertEqual(page.table.item(0, 6).toolTip(), page.table.item(0, 6).text())

        page.table.cellClicked.emit(1, 0)
        self.assertEqual(page.table.currentRow(), 1)
        self.assertEqual(page.detail_panel.title_label.text(), page.table.item(1, 0).text())

    def test_task_management_action_buttons_have_feedback_and_selected_qss(self) -> None:
        import os

        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "物料基础资料同步", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(return_value={"status": "success"}),
            pause_task=Mock(return_value=1),
        )
        gui = SimpleNamespace(task_service=service)
        page = TaskManagementPage(gui)
        self.addCleanup(cleanup_widget, page)

        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)
        self.assertEqual(action_cell.btn_run.toolTip(), "立即运行")
        self.assertEqual(action_cell.btn_pause.toolTip(), "暂停任务")
        self.assertEqual(action_cell.btn_edit.toolTip(), "编辑任务")
        self.assertEqual(action_cell.btn_more.toolTip(), "更多操作")
        self.assertEqual(action_cell.btn_run.property("icon-source"), "icons/schedule_running.svg")
        self.assertEqual(action_cell.btn_pause.property("icon-source"), "icons/schedule_status.svg")
        self.assertEqual(action_cell.btn_edit.property("icon-source"), "icons/settings.svg")
        self.assertFalse(action_cell.btn_run.icon().isNull())
        self.assertFalse(action_cell.btn_pause.icon().isNull())
        self.assertFalse(action_cell.btn_edit.icon().isNull())

        first_task_name = page.table.item(0, 0).text()
        action_cell.btn_run.click()
        self.assertEqual(page.last_action_feedback, f"立即运行：{first_task_name}")
        action_cell.btn_pause.click()
        self.assertEqual(page.last_action_feedback, f"暂停任务：{first_task_name}")

        stylesheet_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css")
        with open(stylesheet_path, encoding="utf-8") as stylesheet:
            css = stylesheet.read()
        self.assertIn('QWidget[page="task-management"] QTableWidget[ui="win11-data-table"]::item:selected', css)
        self.assertIn("selection-background-color: #EDF6FF", css)

    def test_task_management_row_actions_call_task_service_methods(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "真实任务", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(return_value=True),
            pause_task=Mock(return_value=1),
            get_form_options=Mock(return_value=[("真实任务", "T_REAL")]),
            get_task_editor_data=Mock(return_value={"form_name": "真实任务", "enabled": True}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)

        action_cell.btn_run.click()
        self.assertEqual(service.run_task.call_args.args, ("真实任务",))
        self.assertIn("progress_callback", service.run_task.call_args.kwargs)
        self.assertEqual(page.last_action_feedback, "立即运行：真实任务")

        action_cell.btn_pause.click()
        service.pause_task.assert_called_once_with("真实任务")
        self.assertEqual(page.last_action_feedback, "暂停任务：真实任务")

        action_cell.btn_edit.click()
        service.get_task_editor_data.assert_called_once_with("真实任务")
        self.assertEqual(page.last_action_feedback, "编辑任务：真实任务")

    def test_task_management_run_action_disables_button_refreshes_and_reports_errors(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        seen_disabled = []

        def run_task(_task_name):
            seen_disabled.append(not action_cell.btn_run.isEnabled())
            return {"status": "success"}

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "真实任务", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(side_effect=run_task),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)
        service.get_tasks.reset_mock()

        action_cell.btn_run.click()

        self.assertEqual(seen_disabled, [True])
        self.assertTrue(action_cell.btn_run.isEnabled())
        self.assertEqual(page.last_action_feedback, "立即运行：真实任务")
        self.assertGreaterEqual(service.get_tasks.call_count, 1)

        service.run_task.side_effect = RuntimeError("同步失败")
        service.get_tasks.reset_mock()
        action_cell = page.table.cellWidget(0, 7)
        action_cell.btn_run.click()

        self.assertTrue(action_cell.btn_run.isEnabled())
        self.assertEqual(page.last_action_feedback, "立即运行失败：同步失败")
        service.get_tasks.assert_not_called()

    def test_task_management_run_action_marks_row_running_during_call(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage, TaskStatusTag

        observed = []

        def run_task(_task_name, *, progress_callback=None):
            status_tag = page.table.cellWidget(0, 4)
            running_cell = page.table.cellWidget(0, 7)
            self.assertIsInstance(status_tag, TaskStatusTag)
            self.assertIsInstance(running_cell, TaskActionCell)
            progress_callback("正在拉取数据", 27)
            observed.append(
                (
                    page.operation_status_summary.text(),
                    status_tag.label.text(),
                    running_cell.btn_run.isEnabled(),
                    running_cell.btn_pause.toolTip(),
                    page.btn_batch_run.isEnabled(),
                )
            )
            return {"status": "success"}

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "真实任务", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(side_effect=run_task),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)

        action_cell.btn_run.click()

        self.assertEqual(observed, [("立即运行：真实任务，27%，正在拉取数据", "运行中", False, "中止运行", False)])
        self.assertEqual(page.last_action_feedback, "立即运行：真实任务")

    def test_task_management_progress_from_worker_thread_is_queued_to_gui_thread(self) -> None:
        import threading

        from src.gui.pages.task_management_page import TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "真实任务", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        callback = page._make_task_progress_callback("真实任务")

        worker = threading.Thread(target=lambda: callback("正在拉取数据", 27))
        worker.start()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

        self.assertEqual(page.operation_status_summary.text(), "最近操作：暂无记录")

        for _ in range(10):
            self._app.processEvents()

        self.assertEqual(page.operation_status_summary.text(), "立即运行：真实任务，27%，正在拉取数据")
        self.assertIn("当前阶段: 正在拉取数据", page.detail_panel.schedule_value.text())

    def test_task_management_detail_panel_shows_progress_and_final_result(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        tasks_state = [{"task_name": "真实任务", "status": "enabled"}]
        observed_progress_detail = []

        def get_tasks(*_args, **_kwargs):
            return ([dict(task) for task in tasks_state], len(tasks_state))

        def run_task(_task_name, *, progress_callback=None):
            progress_callback("正在拉取数据", 27)
            observed_progress_detail.append(page.detail_panel.schedule_value.text())
            tasks_state[:] = [
                {
                    "task_name": "真实任务",
                    "status": "success",
                    "record_count": 42,
                    "duration_seconds": 1.5,
                }
            ]
            return {"status": "success", "total_records": 42, "duration": 1.5}

        service = SimpleNamespace(
            get_tasks=Mock(side_effect=get_tasks),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(side_effect=run_task),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)

        action_cell.btn_run.click()

        self.assertIn("当前阶段: 正在拉取数据", observed_progress_detail[0])
        self.assertIn("当前进度: 27%", observed_progress_detail[0])
        self.assertIn("进度时间:", observed_progress_detail[0])
        final_detail = page.detail_panel.schedule_value.text()
        self.assertIn("最近结果: 成功", final_detail)
        self.assertIn("写入行数: 42", final_detail)
        self.assertIn("耗时: 1.5 秒", final_detail)

    def test_task_management_batch_progress_updates_selected_detail_panel(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from src.gui.pages import task_management_page as module
        from src.gui.pages.task_management_page import TaskManagementPage

        tasks_state = [
            {"task_name": "任务A", "status": "enabled"},
            {"task_name": "任务B", "status": "enabled"},
        ]
        observed_progress_detail = []

        def get_tasks(*_args, **_kwargs):
            return ([dict(task) for task in tasks_state], len(tasks_state))

        def run_tasks(_task_names, *, progress_callback=None):
            progress_callback("任务A 字段转换", 66)
            observed_progress_detail.append(page.detail_panel.schedule_value.text())
            tasks_state[0] = {
                "task_name": "任务A",
                "status": "success",
                "record_count": 88,
                "duration_seconds": 2.2,
            }
            return {"requested": 2, "succeeded": 2, "failed": 0, "errors": []}

        service = SimpleNamespace(
            get_tasks=Mock(side_effect=get_tasks),
            get_task_stats=Mock(return_value={"total": 2}),
            run_tasks=Mock(side_effect=run_tasks),
        )
        with patch.object(module, "confirm_task_action", return_value=True):
            page = TaskManagementPage(SimpleNamespace(task_service=service))
            self.addCleanup(cleanup_widget, page)
            page.table.selectRow(0)
            page.table.selectionModel().select(
                page.table.model().index(1, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._app.processEvents()

            page.btn_batch_run.click()

        self.assertIn("当前阶段: 任务A 字段转换", observed_progress_detail[0])
        self.assertIn("当前进度: 66%", observed_progress_detail[0])
        self.assertIn("进度时间:", observed_progress_detail[0])
        final_detail = page.detail_panel.schedule_value.text()
        self.assertIn("最近结果: 成功", final_detail)
        self.assertIn("写入行数: 88", final_detail)
        self.assertIn("耗时: 2.2 秒", final_detail)

    def test_task_management_running_row_exposes_cancel_entry_and_records_unsupported_feedback(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        audit = {
            "operation": "中止任务",
            "status": "warning",
            "summary": "中止任务：真实任务，当前同步任务暂不支持中止",
            "detail": "真实任务：当前同步任务暂不支持中止",
            "timestamp": "2026-06-24 11:20:00",
        }
        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "真实任务", "status": "running"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            cancel_task=Mock(
                return_value={
                    "cancelled": False,
                    "supported": False,
                    "message": "当前同步任务暂不支持中止",
                    "task_name": "真实任务",
                }
            ),
            get_latest_operation_audit=Mock(return_value=audit),
            get_operation_history=Mock(return_value=[audit]),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)
        self.assertEqual(action_cell.btn_pause.toolTip(), "中止运行")

        action_cell.btn_pause.click()

        service.cancel_task.assert_called_once_with("真实任务")
        self.assertEqual(page.last_action_feedback, "中止任务：真实任务，当前同步任务暂不支持中止")
        self.assertEqual(page.operation_status_summary.text(), audit["summary"])
        self.assertFalse(hasattr(page, "operation_history_panel"))

    def test_task_management_multi_select_batch_pause_and_run(self) -> None:
        from PySide6.QtCore import QItemSelectionModel
        from PySide6.QtWidgets import QAbstractItemView

        from src.gui.pages import task_management_page as module
        from src.gui.pages.task_management_page import TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(
                return_value=(
                    [
                        {"task_name": "任务A", "status": "enabled"},
                        {"task_name": "任务B", "status": "enabled"},
                    ],
                    2,
                )
            ),
            get_task_stats=Mock(return_value={"total": 2}),
            pause_tasks=Mock(return_value=2),
            run_tasks=Mock(return_value={"requested": 2, "succeeded": 2, "failed": 0, "errors": []}),
        )
        with patch.object(module, "confirm_task_action", return_value=True):
            page = TaskManagementPage(SimpleNamespace(task_service=service))
            self.addCleanup(cleanup_widget, page)

            self.assertEqual(page.table.selectionMode(), QAbstractItemView.SelectionMode.ExtendedSelection)
            self.assertFalse(page.btn_batch_pause.isEnabled())
            self.assertFalse(page.btn_batch_run.isEnabled())

            page.table.selectRow(0)
            page.table.selectionModel().select(
                page.table.model().index(1, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._app.processEvents()

            self.assertTrue(page.btn_batch_pause.isEnabled())
            self.assertTrue(page.btn_batch_run.isEnabled())

            page.btn_batch_pause.click()
            service.pause_tasks.assert_called_once_with(["任务A", "任务B"])
            self.assertEqual(page.last_action_feedback, "批量暂停：已暂停 2 个任务")

            page.table.selectRow(0)
            page.table.selectionModel().select(
                page.table.model().index(1, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._app.processEvents()
            page.btn_batch_run.click()
            self.assertEqual(service.run_tasks.call_args.args, (["任务A", "任务B"],))
            self.assertIn("progress_callback", service.run_tasks.call_args.kwargs)
            self.assertEqual(page.last_action_feedback, "批量运行：成功 2/2，失败 0")

    def test_task_management_batch_run_shows_running_feedback_and_disables_batch_buttons(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from src.gui.pages import task_management_page as module
        from src.gui.pages.task_management_page import TaskManagementPage, TaskStatusTag

        observed = []

        def run_tasks(_task_names, *, progress_callback=None):
            first_status = page.table.cellWidget(0, 4)
            second_status = page.table.cellWidget(1, 4)
            self.assertIsInstance(first_status, TaskStatusTag)
            self.assertIsInstance(second_status, TaskStatusTag)
            progress_callback("任务A 字段转换", 66)
            observed.append(
                (
                    page.operation_status_summary.text(),
                    page.btn_batch_run.isEnabled(),
                    page.btn_batch_pause.isEnabled(),
                    first_status.label.text(),
                    second_status.label.text(),
                )
            )
            return {"requested": 2, "succeeded": 2, "failed": 0, "errors": []}

        service = SimpleNamespace(
            get_tasks=Mock(
                return_value=(
                    [
                        {"task_name": "任务A", "status": "enabled"},
                        {"task_name": "任务B", "status": "enabled"},
                    ],
                    2,
                )
            ),
            get_task_stats=Mock(return_value={"total": 2}),
            run_tasks=Mock(side_effect=run_tasks),
        )
        with patch.object(module, "confirm_task_action", return_value=True):
            page = TaskManagementPage(SimpleNamespace(task_service=service))
            self.addCleanup(cleanup_widget, page)
            page.table.selectRow(0)
            page.table.selectionModel().select(
                page.table.model().index(1, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._app.processEvents()

            page.btn_batch_run.click()

        self.assertEqual(observed, [("批量运行：66%，任务A 字段转换", False, False, "运行中", "运行中")])
        self.assertEqual(page.last_action_feedback, "批量运行：成功 2/2，失败 0")

    def test_task_management_more_menu_triggers_row_actions(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "任务A", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            get_form_options=Mock(return_value=[("任务A", "T_A")]),
            get_task_editor_data=Mock(return_value={"form_name": "任务A", "enabled": True}),
            run_task=Mock(return_value={"status": "success"}),
            pause_task=Mock(return_value=1),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)

        action_cell.btn_more.click()

        self.assertIsNotNone(page.task_more_menu)
        action_texts = [action.text() for action in page.task_more_menu.actions()]
        self.assertEqual(action_texts, ["立即运行", "暂停任务", "编辑任务"])

        page.task_more_menu.actions()[0].trigger()
        self.assertEqual(service.run_task.call_args.args, ("任务A",))
        self.assertIn("progress_callback", service.run_task.call_args.kwargs)
        page.task_more_menu.actions()[1].trigger()
        service.pause_task.assert_called_once_with("任务A")
        page.task_more_menu.actions()[2].trigger()
        service.get_task_editor_data.assert_called_once_with("任务A")

    def test_task_management_batch_actions_confirm_and_show_failure_details(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from src.gui.pages import task_management_page as module
        from src.gui.pages.task_management_page import TaskManagementPage

        confirms = []

        def confirm(_parent, title, message):
            confirms.append((title, message))
            return True

        service = SimpleNamespace(
            get_tasks=Mock(
                return_value=(
                    [
                        {"task_name": "任务A", "status": "enabled"},
                        {"task_name": "任务B", "status": "enabled"},
                    ],
                    2,
                )
            ),
            get_task_stats=Mock(return_value={"total": 2}),
            pause_tasks=Mock(return_value=2),
            run_tasks=Mock(
                return_value={
                    "requested": 2,
                    "succeeded": 1,
                    "failed": 1,
                    "errors": [{"task_name": "任务B", "error": "API 超时"}],
                }
            ),
        )
        with patch.object(module, "confirm_task_action", confirm):
            page = TaskManagementPage(SimpleNamespace(task_service=service))
            self.addCleanup(cleanup_widget, page)
            page.table.selectRow(0)
            page.table.selectionModel().select(
                page.table.model().index(1, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._app.processEvents()

            page.btn_batch_pause.click()
            self.assertEqual(confirms[-1][0], "确认批量暂停")
            self.assertIn("任务A、任务B", confirms[-1][1])

            page.table.selectRow(0)
            page.table.selectionModel().select(
                page.table.model().index(1, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
            self._app.processEvents()
            page.btn_batch_run.click()

        self.assertEqual(confirms[-1][0], "确认批量运行")
        self.assertEqual(page.last_action_feedback, "批量运行：成功 1/2，失败 1；任务B：API 超时")

    def test_task_management_more_menu_failure_reports_visible_feedback(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "任务A", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            run_task=Mock(side_effect=RuntimeError("数据库断开")),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)

        action_cell.btn_more.click()
        page.task_more_menu.actions()[0].trigger()

        self.assertEqual(page.last_action_feedback, "立即运行失败：数据库断开")

    def test_task_management_operation_audit_status_shows_last_operation_only(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "任务A", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            get_latest_operation_audit=Mock(
                return_value={
                    "operation": "批量运行",
                    "status": "failed",
                    "summary": "批量运行：成功 1/2，失败 1",
                    "detail": "任务B：API 超时",
                    "timestamp": "2026-06-24 10:20:20",
                }
            ),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        page.show()
        self._app.processEvents()

        self.assertTrue(page.operation_status_bar.isVisible())
        self.assertEqual(page.operation_status_summary.text(), "批量运行：成功 1/2，失败 1")
        self.assertIn("10:20:20", page.operation_status_time.text())
        self.assertFalse(hasattr(page, "btn_copy_operation_detail"))

    def test_task_management_detail_panel_does_not_render_recent_run_section(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(
                return_value=(
                    [
                        {
                            "task_name": "任务A",
                            "status": "success",
                            "run_started_at": "2026-06-24 10:20:00",
                            "run_finished_at": "2026-06-24 10:20:05",
                            "final_status": "成功",
                            "record_count": 42,
                            "duration_seconds": 5,
                            "progress_summary": "20% 拉取数据；80% 写入 SQL Server",
                        }
                    ],
                    1,
                )
            ),
            get_task_stats=Mock(return_value={"total": 1}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        self.assertFalse(hasattr(page.detail_panel, "run_detail_value"))
        self.assertFalse(hasattr(page.detail_panel, "run_detail_summary_value"))
        self.assertFalse(hasattr(page.detail_panel, "btn_copy_run_detail"))
        self.assertFalse(hasattr(page.detail_panel, "btn_latest_run_detail"))
        self.assertNotIn("最近运行", page.detail_panel.findChildren(type(page.detail_panel.title_label))[0].text())
        self.assertIn("最近结果: 成功", page.detail_panel.schedule_value.text())
        self.assertIn("写入行数: 42", page.detail_panel.schedule_value.text())
        self.assertIn("耗时: 5 秒", page.detail_panel.schedule_value.text())

    def test_task_management_does_not_render_operation_history_panel(self) -> None:
        from src.gui.pages.task_management_page import TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "任务1", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            get_latest_operation_audit=Mock(return_value={}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        self.assertFalse(hasattr(page, "operation_history_panel"))
        self.assertFalse(hasattr(page, "operation_history_table"))
        self.assertFalse(hasattr(page, "history_status_combo"))
        self.assertFalse(hasattr(page, "history_search_box"))
        self.assertFalse(hasattr(page, "btn_copy_history_detail"))
        self.assertFalse(hasattr(page, "btn_clear_history"))
        self.assertFalse(hasattr(page, "btn_export_history_report"))
        self.assertFalse(hasattr(page, "history_page_size_combo"))
        self.assertFalse(hasattr(page, "history_total_label"))
        self.assertFalse(hasattr(page, "btn_history_prev"))
        self.assertFalse(hasattr(page, "history_page_label"))
        self.assertFalse(hasattr(page, "btn_history_next"))

    def test_task_management_run_validation_failure_updates_status_history_and_copy_detail(self) -> None:
        from PySide6.QtWidgets import QApplication

        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage

        audit = {
            "operation": "运行前校验",
            "status": "failed",
            "summary": "运行前校验失败：任务A同步",
            "detail": "任务A同步：任务未启用",
            "timestamp": "2026-06-24 10:20:00",
        }

        class FakeTaskService:
            def __init__(self) -> None:
                self.sync_called = False
                self._history: list[dict[str, str]] = []

            def get_tasks(self, *_args, **_kwargs):
                return ([{"task_name": "任务A同步", "status": "paused"}], 1)

            def get_task_stats(self):
                return {"total": 1}

            def get_latest_operation_audit(self):
                return audit if self._history else {}

            def get_operation_history(self, limit=6):
                return self._history[:limit]

            def run_task(self, _task_name):
                self._history.insert(0, dict(audit))
                raise ValueError("任务未启用")

        service = FakeTaskService()
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)
        action_cell.btn_run.click()

        self.assertFalse(service.sync_called)
        self.assertEqual(page.operation_status_summary.text(), "运行前校验失败：任务A同步")
        self.assertFalse(hasattr(page, "operation_history_table"))
        self.assertFalse(hasattr(page, "btn_copy_operation_detail"))

    def test_task_management_run_success_refreshes_result_summary_and_recent_columns(self) -> None:
        from types import SimpleNamespace

        from src.gui.pages.task_management_page import TaskActionCell, TaskManagementPage
        from src.services.task_service import TaskService

        config = SimpleNamespace(
            get_table_mapping=Mock(return_value={"销售订单": "T_SAL_SaleOrder"}),
            get_sync_config=Mock(return_value={"default_forms": ["销售订单"], "sync_type": "incremental"}),
            get_increment_field=Mock(return_value="FDate"),
            save_sync_preferences=Mock(),
        )
        history = SimpleNamespace(get_history=Mock(return_value=([], 0)))
        sync = SimpleNamespace(
            sync_data=Mock(
                return_value={
                    "status": "success",
                    "message": "OK",
                    "total_records": 221,
                    "duration": 6.5,
                }
            )
        )
        service = TaskService(config_manager=config, history_manager=history, sync_service=sync)
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)

        action_cell.btn_run.click()

        self.assertEqual(page.operation_status_summary.text(), "立即运行：销售订单同步，成功，写入 221 行，耗时 6.5 秒")
        self.assertFalse(hasattr(page, "operation_history_table"))
        self.assertNotEqual(page.table.item(0, 5).text(), "--")
        self.assertEqual(page.table.item(0, 6).text(), "100%")
        task = page.tasks[0]
        self.assertEqual(task["record_count"], 221)
        self.assertEqual(task["duration_seconds"], 6.5)

    def test_task_management_new_task_dialog_saves_via_task_service(self) -> None:
        from src.gui.pages.task_management_page import TaskEditorDialog, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([], 0)),
            get_task_stats=Mock(return_value={"total": 0}),
            get_form_options=Mock(return_value=[("物料基础资料", "T_BD_Material"), ("客户资料", "T_BD_Customer")]),
            get_task_editor_data=Mock(return_value={}),
            save_task=Mock(return_value={"saved": True, "form_name": "客户资料"}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)
        service.get_tasks.reset_mock()

        page.btn_new_task.click()

        self.assertIsInstance(page.task_editor_dialog, TaskEditorDialog)
        dialog = page.task_editor_dialog
        self.assertEqual(dialog.form_combo.count(), 2)
        dialog.form_combo.setCurrentText("客户资料")
        dialog.mode_combo.setCurrentText("完全同步")
        dialog.enabled_check.setChecked(True)
        dialog.increment_field_edit.setText("FModifyTime")
        dialog.btn_save.click()

        service.save_task.assert_called_once_with(
            {
                "form_name": "客户资料",
                "sync_mode": "complete",
                "enabled": True,
                "increment_field": "FModifyTime",
            }
        )
        self.assertEqual(page.last_action_feedback, "保存任务：客户资料")
        self.assertGreaterEqual(service.get_tasks.call_count, 1)

    def test_task_management_task_editor_exposes_complete_sync_mode(self) -> None:
        from src.gui.pages.task_management_page import TaskEditorDialog

        dialog = TaskEditorDialog(
            [("物料", "bd_material")],
            {"form_name": "物料", "sync_mode": "complete", "enabled": True},
        )
        self.addCleanup(cleanup_widget, dialog)

        mode_labels = [dialog.mode_combo.itemText(index) for index in range(dialog.mode_combo.count())]

        self.assertEqual(mode_labels, ["增量同步", "完全同步"])
        self.assertEqual(dialog.mode_combo.currentText(), "完全同步")
        self.assertEqual(dialog.payload()["sync_mode"], "complete")

    def test_task_management_task_editor_maps_legacy_full_mode_to_complete_sync_label(self) -> None:
        from src.gui.pages.task_management_page import TaskEditorDialog

        dialog = TaskEditorDialog(
            [("物料", "bd_material")],
            {"form_name": "物料", "sync_mode": "full", "enabled": True},
        )
        self.addCleanup(cleanup_widget, dialog)

        self.assertEqual(dialog.mode_combo.currentText(), "完全同步")
        self.assertEqual(dialog.payload()["sync_mode"], "complete")

    def test_task_management_edit_task_dialog_prefills_current_task(self) -> None:
        from src.gui.pages.task_management_page import TaskActionCell, TaskEditorDialog, TaskManagementPage

        service = SimpleNamespace(
            get_tasks=Mock(return_value=([{"task_name": "销售订单同步", "status": "enabled"}], 1)),
            get_task_stats=Mock(return_value={"total": 1}),
            get_form_options=Mock(return_value=[("销售订单", "T_SAL_SaleOrder")]),
            get_task_editor_data=Mock(
                return_value={
                    "form_name": "销售订单",
                    "sync_mode": "incremental",
                    "enabled": True,
                    "increment_field": "FDate",
                }
            ),
            save_task=Mock(return_value={"saved": True, "form_name": "销售订单"}),
        )
        page = TaskManagementPage(SimpleNamespace(task_service=service))
        self.addCleanup(cleanup_widget, page)

        action_cell = page.table.cellWidget(0, 7)
        self.assertIsInstance(action_cell, TaskActionCell)
        action_cell.btn_edit.click()

        service.get_task_editor_data.assert_called_once_with("销售订单同步")
        self.assertIsInstance(page.task_editor_dialog, TaskEditorDialog)
        dialog = page.task_editor_dialog
        self.assertEqual(dialog.form_combo.currentText(), "销售订单")
        self.assertEqual(dialog.mode_combo.currentText(), "增量同步")
        self.assertTrue(dialog.enabled_check.isChecked())
        self.assertEqual(dialog.increment_field_edit.text(), "FDate")


class Win11DataSourcePageTests(QtAppTestCase):
    def test_data_source_page_instantiates(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace()
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("ui"), "win11-page")

    def test_data_source_page_has_source_cards(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage, _SourceCard

        gui = SimpleNamespace()
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)

        cards = page.findChildren(_SourceCard)
        self.assertGreaterEqual(len(cards), 2, "Expected at least 2 data source cards")

    def test_data_source_page_has_data_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace()
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)

        tables = page.findChildren(DataTable)
        self.assertGreaterEqual(len(tables), 1, "Expected at least 1 health check DataTable")

    def test_data_source_page_has_action_buttons(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace()
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)

        buttons = page.findChildren(QPushButton)
        btn_texts = [b.text() for b in buttons]
        self.assertTrue(any("测试" in t for t in btn_texts), "Expected test connection button")
        self.assertTrue(any("配置数据源" in t for t in btn_texts), "Expected '配置数据源' button")

    def test_data_source_page_config_button_navigates_to_settings(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace(switch_to_page=Mock())
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.btn_add_source.text(), "配置数据源")
        page.btn_add_source.click()

        gui.switch_to_page.assert_called_once_with("settings")

    def test_data_source_page_test_all_uses_connection_service_without_saving(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace(kd_connected=False, db_connected=False)
        with (
            patch(
                "src.gui.pages.data_source_page.settings_service.test_connections",
                return_value=(True, False, "金蝶: 成功\n数据库: 失败"),
            ) as test_connections,
            patch("src.gui.pages.data_source_page.settings_service.save_settings") as save_settings,
        ):
            page = DataSourcePage(gui)
            self.addCleanup(cleanup_widget, page)
            page.btn_test_all.click()

        test_connections.assert_called_once_with()
        save_settings.assert_not_called()
        self.assertTrue(gui.kd_connected)
        self.assertFalse(gui.db_connected)
        self.assertEqual(page.health_table.table.item(0, 2).text(), "成功")
        self.assertEqual(page.health_table.table.item(1, 2).text(), "失败")
        self.assertEqual(page.health_table.table.item(1, 5).text(), "金蝶: 成功；数据库: 失败")

    def test_data_source_page_health_table_is_latest_result_not_fake_history_before_test(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace(kd_connected=False, db_connected=False)
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.health_card.title_label.text(), "最近一次检测结果")
        self.assertEqual(page.health_table.table.rowCount(), 2)
        self.assertEqual(page.health_table.table.item(0, 2).text(), "未检测")
        self.assertEqual(page.health_table.table.item(0, 4).text(), "--")
        self.assertEqual(page.health_table.table.item(1, 2).text(), "未检测")
        self.assertEqual(page.health_table.table.item(1, 4).text(), "--")

    def test_data_source_page_test_all_updates_latest_check_time_and_failure_reason(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace(kd_connected=False, db_connected=False)
        with patch(
            "src.gui.pages.data_source_page.settings_service.test_connections",
            return_value=(False, True, "金蝶: 登录失败\n数据库: 成功"),
        ):
            page = DataSourcePage(gui)
            self.addCleanup(cleanup_widget, page)
            page.btn_test_all.click()

        self.assertNotEqual(page.health_table.table.item(0, 0).text(), "--")
        self.assertEqual(page.health_table.table.item(0, 2).text(), "失败")
        self.assertEqual(page.health_table.table.item(0, 4).text(), "--")
        self.assertEqual(page.health_table.table.item(0, 5).text(), "金蝶: 登录失败；数据库: 成功")
        self.assertEqual(page.health_table.table.item(1, 2).text(), "成功")
        self.assertEqual(page.health_table.table.item(1, 4).text(), "2 ms")

    def test_data_source_page_chips_are_pill_shaped_not_square(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace(kd_connected=True, db_connected=True)
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)

        chips = [label for label in page.findChildren(QLabel) if label.property("ui") == "ds-chip"]

        self.assertGreaterEqual(len(chips), 6)
        for chip in chips:
            self.assertGreaterEqual(chip.width(), 68)
            self.assertLessEqual(chip.height(), 22)
            self.assertGreater(chip.width(), chip.height() * 2)

    def test_data_source_page_api_url_displays_domain_only(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage

        gui = SimpleNamespace(kd_connected=True, db_connected=True)
        with (
            patch(
                "src.gui.pages.data_source_page.config_manager.get_kingdee_config",
                return_value={
                    "query_url": "https://api.yunxingkong.com/k2cloud/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery.common.kdsvc",
                    "acct_id": "demo",
                    "username": "aps",
                },
            ),
            patch(
                "src.gui.pages.data_source_page.config_manager.get_db_config",
                return_value={"sqlserver": {"host": "10.1.1.9", "port": "1422", "database": "Kingdee", "user": "sa"}},
            ),
        ):
            page = DataSourcePage(gui)
            self.addCleanup(cleanup_widget, page)

        api_values = [
            label.text()
            for label in page.findChildren(QLabel)
            if label.property("config-key") == "API 地址"
        ]
        self.assertIn("https://api.yunxingkong.com", api_values)
        self.assertNotIn("ExecuteBillQuery", "".join(api_values))

    def test_data_source_page_1266x768(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage, _SourceCard

        gui = SimpleNamespace()
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        cards = page.findChildren(_SourceCard)
        self.assertGreaterEqual(len(cards), 2)
        for card in cards:
            self.assertTrue(card.isVisible())

    def test_data_source_page_final_visual_structure(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage, _SourceCard

        gui = SimpleNamespace(kd_connected=True, db_connected=True)
        page = DataSourcePage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1440, 900)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.property("page"), "data-source")
        self.assertEqual(page.btn_test_all.size().height(), 26)
        self.assertEqual(page.btn_add_source.size().height(), 26)

        cards = page.findChildren(_SourceCard)
        self.assertGreaterEqual(len(cards), 2)
        for card in cards:
            self.assertEqual(card.height(), 128)

        self.assertEqual(page.health_card.height(), 196)
        self.assertEqual(page.health_table.table.verticalHeader().defaultSectionSize(), 22)
        self.assertEqual(page.health_table.table.horizontalHeader().height(), 25)


class Win11DiagnosticsPageTests(QtAppTestCase):
    def test_diagnostics_page_instantiates(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("ui"), "win11-page")

    def test_diagnostics_page_has_summary_cards(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(len(page.stat_cards), 5, "Expected 5 diagnostic summary cards")

    def test_diagnostics_page_has_data_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)

        tables = page.findChildren(DataTable)
        self.assertGreaterEqual(len(tables), 1, "Expected at least 1 exception detail DataTable")

    def test_diagnostics_page_has_action_buttons(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)

        buttons = page.findChildren(QPushButton)
        btn_texts = [b.text() for b in buttons]
        self.assertTrue(any("刷新诊断" in t for t in btn_texts), "Expected '刷新诊断' button")
        self.assertTrue(any("导出报告" in t for t in btn_texts), "Expected '导出报告' button")

    def test_diagnostics_page_refresh_button_reloads_readonly_data(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        with patch("src.gui.pages.diagnostics_page.get_dashboard_today_stats", return_value={"pending_count": 0, "fail_count": 0}):
            page = DiagnosticsPage(gui)
            self.addCleanup(cleanup_widget, page)
            with patch.object(page, "_load_real_data") as load_real_data:
                page.btn_rediagnose.click()

        load_real_data.assert_called_once()

    def test_diagnostics_page_filters_and_searches_loaded_history_rows(self) -> None:
        from PySide6.QtWidgets import QComboBox, QLineEdit

        from src.gui.pages.diagnostics_page import DiagnosticsPage

        records = [
            {
                "start_time": "2026-06-24 10:00:00",
                "sync_type": "物料同步",
                "table_name": "bd_material",
                "status": "failed",
                "message": "字段 FNumber 转换失败",
            },
            {
                "start_time": "2026-06-24 10:05:00",
                "sync_type": "客户同步",
                "table_name": "bd_customer",
                "status": "partial",
                "message": "部分成功",
            },
        ]
        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.diagnostics_page.get_dashboard_today_stats", return_value={"pending_count": 1, "fail_count": 1}),
            patch("src.gui.pages.diagnostics_page.history_manager.get_history", return_value=(records, 2)),
            patch("src.gui.pages.diagnostics_page.history_manager.get_stats", return_value={"top_failures": []}),
        ):
            page = DiagnosticsPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertIsInstance(page.filter_combo, QComboBox)
        self.assertIsInstance(page.search_box, QLineEdit)
        self.assertEqual(page.detail_table.table.rowCount(), 2)

        page.filter_combo.setCurrentText("待处理")
        self.assertEqual(page.detail_table.table.rowCount(), 1)
        self.assertIn("物料同步", page.detail_table.table.item(0, 1).text())

        page.search_box.setText("客户")
        page.search_box.editingFinished.emit()
        self.assertEqual(page.detail_table.table.rowCount(), 0)

        page.filter_combo.setCurrentText("全部状态")
        self.assertEqual(page.detail_table.table.rowCount(), 1)
        self.assertIn("客户同步", page.detail_table.table.item(0, 1).text())

    def test_diagnostics_page_empty_history_uses_table_empty_state(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.diagnostics_page.get_dashboard_today_stats", return_value={"pending_count": 0, "fail_count": 0}),
            patch("src.gui.pages.diagnostics_page.history_manager.get_history", return_value=([], 0)),
            patch("src.gui.pages.diagnostics_page.history_manager.get_stats", return_value={"top_failures": []}),
        ):
            page = DiagnosticsPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.detail_table.table.rowCount(), 0)
        self.assertFalse(page.detail_table._empty_label.isHidden())
        self.assertEqual(page.detail_table._empty_label.text(), "当前筛选条件下没有异常记录")
        self.assertEqual(page.lbl_total.text(), "共 0 条")
        self.assertEqual(page.pie_chart.total, 0)
        self.assertEqual(page.pie_chart.empty_text, "暂无分类数据")
        self.assertFalse(hasattr(page, "chain_card"))

    def test_diagnostics_page_export_report_writes_current_view_without_sql_writes(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        records = [
            {
                "start_time": "2026-06-24 10:00:00",
                "sync_type": "物料同步",
                "table_name": "bd_material",
                "status": "failed",
                "message": "字段 FNumber 转换失败",
            }
        ]
        gui = SimpleNamespace()
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.gui.pages.diagnostics_page.get_dashboard_today_stats", return_value={"pending_count": 1, "fail_count": 1}),
                patch("src.gui.pages.diagnostics_page.history_manager.get_history", return_value=(records, 1)),
                patch("src.gui.pages.diagnostics_page.history_manager.get_stats", return_value={"top_failures": ["字段 FNumber 转换失败"]}),
                patch("src.gui.pages.diagnostics_page.app_logger.get_log_dir", return_value=tmpdir),
                patch("src.gui.pages.diagnostics_page.UiFeedback") as feedback,
            ):
                page = DiagnosticsPage(gui)
                self.addCleanup(cleanup_widget, page)
                page.btn_export.click()

            exported = list(Path(tmpdir).glob("diagnostics_report_*.txt"))
            self.assertEqual(len(exported), 1)
            text = exported[0].read_text(encoding="utf-8")

        self.assertIn("异常诊断报告", text)
        self.assertIn("物料同步", text)
        self.assertIn("字段 FNumber 转换失败", text)
        feedback.success.assert_called_once()

    def test_diagnostics_page_has_suggestions_section(self) -> None:
        from PySide6.QtWidgets import QLabel

        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)
        self.assertIsNotNone(page._suggestions_card)
        # 建议卡已替换为空态占位，不再包含 _SuggestionItem 实例
        empty_labels = [child for child in page._suggestions_card.findChildren(QLabel) if "暂无" in child.text()]
        self.assertGreaterEqual(len(empty_labels), 1)

    def test_diagnostics_page_weakens_static_page_size_text(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.page_label.text(), "筛选结果")

    def test_diagnostics_page_uses_scrollable_content_without_suggestion_clipping(self) -> None:
        from PySide6.QtWidgets import QScrollArea

        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)

        scroll_areas = page.findChildren(QScrollArea)
        self.assertTrue(any(area.objectName() == "diagnostics_scroll" for area in scroll_areas))

        self.assertIsNotNone(page._suggestions_card)
        self.assertFalse(page._suggestions_card.findChildren(type(page._suggestions_card)))

    def test_diagnostics_page_1266x768(self) -> None:
        from src.gui.pages.diagnostics_page import DiagnosticsPage

        gui = SimpleNamespace()
        page = DiagnosticsPage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        self.assertEqual(len(page.stat_cards), 5)
        for card in page.stat_cards:
            self.assertTrue(card.isVisible())


class Win11LogCenterPageTests(QtAppTestCase):

    def test_log_center_page_instantiates(self) -> None:
        from src.gui.pages.log_center_page import LogCenterPage

        gui = SimpleNamespace()
        page = LogCenterPage(gui)
        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("ui"), "win11-page")

    def test_log_center_page_has_summary_cards(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages.log_center_page import LogCenterPage

        gui = SimpleNamespace()
        page = LogCenterPage(gui)
        self.addCleanup(cleanup_widget, page)

        stat_cards = [w for w in page.findChildren(QFrame) if w.property("ui") == "sync-stat-card"]
        self.assertGreaterEqual(len(stat_cards), 5, "Expected at least 5 log summary cards")

    def test_log_center_page_has_log_table(self) -> None:
        from src.gui.components.data_table import DataTable
        from src.gui.pages.log_center_page import LogCenterPage

        gui = SimpleNamespace()
        page = LogCenterPage(gui)
        self.addCleanup(cleanup_widget, page)

        tables = page.findChildren(DataTable)
        self.assertGreaterEqual(len(tables), 1, "Expected at least 1 DataTable for sync records")

    def test_log_center_page_has_action_buttons(self) -> None:
        from PySide6.QtWidgets import QPushButton

        from src.gui.pages.log_center_page import LogCenterPage

        gui = SimpleNamespace()
        page = LogCenterPage(gui)
        self.addCleanup(cleanup_widget, page)

        buttons = page.findChildren(QPushButton)
        btn_texts = [b.text() for b in buttons]
        self.assertTrue(any("刷新" in t for t in btn_texts), "Expected refresh button")

    def test_log_center_page_has_filter_controls(self) -> None:
        from PySide6.QtWidgets import QComboBox, QLineEdit

        from src.gui.pages.log_center_page import LogCenterPage

        gui = SimpleNamespace()
        page = LogCenterPage(gui)
        self.addCleanup(cleanup_widget, page)

        combos = page.findChildren(QComboBox)
        self.assertGreaterEqual(len(combos), 2, "Expected at least 2 filter combo boxes")

    def test_log_center_page_1266x768(self) -> None:
        from PySide6.QtWidgets import QFrame

        from src.gui.pages.log_center_page import LogCenterPage

        gui = SimpleNamespace()
        page = LogCenterPage(gui)
        self.addCleanup(cleanup_widget, page)
        page.resize(1266, 768)
        page.show()
        self._app.processEvents()

        stat_cards = [w for w in page.findChildren(QFrame) if w.property("ui") == "sync-stat-card"]
        self.assertGreaterEqual(len(stat_cards), 5)
        for card in stat_cards:
            self.assertTrue(card.isVisible())












class Win11TenPageNavigationTests(QtAppTestCase):
    """Verify the 10-page navigation aligned to design assets."""

    EXPECTED_PAGES = [
        ("dashboard", "概览"),
        ("sync", "同步执行"),
        ("history", "同步历史"),
        ("task_management", "任务管理"),
        ("data_source", "数据源管理"),
        ("forms", "表单映射"),
        ("schedule", "调度管理"),
        ("diagnostics", "异常诊断"),
        ("log_center", "日志中心"),
        ("settings", "系统设置"),
    ]
    EXPECTED_ICON_FILES = {
        "dashboard": "icons/dashboard.svg",
        "sync": "icons/sync.svg",
        "history": "icons/history.svg",
        "task_management": "icons/task_management.svg",
        "data_source": "icons/data_source.svg",
        "forms": "icons/forms.svg",
        "schedule": "icons/schedule.svg",
        "diagnostics": "icons/diagnostics.svg",
        "log_center": "icons/log_center.svg",
        "settings": "icons/settings.svg",
    }

    def test_page_order_contains_ten_pages(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        self.assertEqual(len(window.page_order), 10)
        expected_ids = [pid for pid, _ in self.EXPECTED_PAGES]
        self.assertEqual(window.page_order, expected_ids)

    def test_all_page_ids_exist_in_pages_dict(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, _ in self.EXPECTED_PAGES:
            self.assertIn(page_id, window.pages, f"page_id {page_id!r} missing from pages dict")

    def test_all_pages_have_win11_page_property(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, _ in self.EXPECTED_PAGES:
            page = window.pages[page_id]
            self.assertEqual(
                page.property("ui"),
                "win11-page",
                f"Page {page_id!r} missing ui='win11-page' property",
            )

    def test_nav_labels_match_design_assets(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, expected_label in self.EXPECTED_PAGES:
            self.assertIn(page_id, window.page_meta, f"page_id {page_id!r} missing from page_meta")
            title, _subtitle = window.page_meta[page_id]
            self.assertEqual(title, expected_label, f"Nav label mismatch for {page_id!r}")

    def test_nav_tree_contains_all_ten_pages(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, _ in self.EXPECTED_PAGES:
            self.assertIn(page_id, window.nav_item_map, f"page_id {page_id!r} missing from nav tree")

    def test_nav_buttons_contain_all_ten_pages(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, expected_label in self.EXPECTED_PAGES:
            self.assertIn(page_id, window.nav_buttons, f"nav_buttons missing {page_id!r}")
            btn = window.nav_buttons[page_id]
            self.assertIn(expected_label, btn.text(), f"Nav button label mismatch for {page_id!r}")
            self.assertEqual(btn.property("icon-source"), self.EXPECTED_ICON_FILES[page_id])
            self.assertFalse(btn.icon().isNull(), f"Nav button icon missing for {page_id!r}")

    def test_switch_to_each_page_succeeds(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, _ in self.EXPECTED_PAGES:
            window.switch_to_page(page_id)
            self.assertEqual(window.current_page_id, page_id)

    def test_sync_page_navigation_does_not_auto_start_sync(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        window.switch_to_page("sync")

        self.assertEqual(window.current_page_id, "sync")
        self.assertEqual(window.topbar_title.text(), "同步执行")
        self.assertIsNone(window.pages["sync"].sync_worker)

    def test_all_new_pages_instantiate_with_scaffold(self) -> None:
        from src.gui.pages.data_source_page import DataSourcePage
        from src.gui.pages.diagnostics_page import DiagnosticsPage
        from src.gui.pages.log_center_page import LogCenterPage
        from src.gui.pages.task_management_page import TaskManagementPage

        gui = SimpleNamespace()
        new_pages = [
            TaskManagementPage(gui),
            DataSourcePage(gui),
            DiagnosticsPage(gui),
            LogCenterPage(gui),
        ]
        for page in new_pages:
            self.addCleanup(cleanup_widget, page)
            self.assertEqual(page.property("ui"), "win11-page")
            hero_title = page.findChild(QLabel, "page_hero_title")
            self.assertIsNotNone(hero_title)

    def test_topbar_title_updates_for_ten_pages(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        for page_id, expected_label in self.EXPECTED_PAGES:
            window.switch_to_page(page_id)
            self.assertEqual(window.topbar_title.text(), expected_label)

    def test_nav_item_map_keys_equal_page_order(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        self.assertEqual(set(window.nav_item_map.keys()), set(window.page_order))
        self.assertIn("sync", window.nav_item_map)


if __name__ == "__main__":
    unittest.main()
