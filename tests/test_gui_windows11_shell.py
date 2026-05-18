#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

# Must be set before importing Qt to allow headless CI execution.
# Use `offscreen` explicitly per Task 1 requirements.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# Helps reduce GPU/driver flakiness in Windows CI in some environments.
os.environ.setdefault("QT_OPENGL", "software")

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


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

        card = Win11SummaryCard(title="Total", value="123")
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

    def test_main_shell_compacts_sidebar_at_1366x768(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        window.resize(1366, 768)
        window.show()
        self._app.processEvents()

        self.assertTrue(window.sidebar_compact)
        self.assertLessEqual(window.sidebar.maximumWidth(), 120)
        self.assertFalse(window.sidebar_status_card.isVisible())
        self.assertLessEqual(window.topbar_search.maximumWidth(), 200)


class Win11DashboardAndSyncResponsiveTests(QtAppTestCase):
    def test_dashboard_uses_primary_action_bar_and_compact_splitters(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertTrue(page.refresh_btn.isVisible())
        self.assertEqual(page.middle_splitter.orientation(), Qt.Orientation.Vertical)

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
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertTrue(page.test_conn_btn.isVisible())
        self.assertTrue(page.start_sync_btn.isVisible())
        self.assertEqual(page.workspace_splitter.orientation(), Qt.Orientation.Vertical)
        self.assertGreaterEqual(page.log_text.minimumHeight(), 180)

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
        self.assertEqual(page.exec_count_card.property("ui"), "win11-execution-metric-card")
        self.assertEqual(page.exec_time_card.property("ui"), "win11-execution-metric-card")
        self.assertEqual(page.exec_rate_card.property("ui"), "win11-execution-metric-card")
        self.assertGreaterEqual(page.exec_count_card.minimumHeight(), 84)


class Win11SettingsAndFormsResponsiveTests(QtAppTestCase):
    def test_settings_page_keeps_actions_visible_and_rows_compact_at_1366x768(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertTrue(page.btn_test.isVisible())
        self.assertTrue(page.btn_save.isVisible())
        self.assertEqual(page.property("layoutMode"), "compact")
        self.assertEqual(page.login_url.minimumWidth(), 0)

    def test_forms_page_prioritizes_list_height_and_top_actions_at_1366x768(self) -> None:
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
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertTrue(page.search_box.isVisible())
        self.assertTrue(page.btn_select_all.isVisible())
        self.assertTrue(page.btn_reset.isVisible())
        self.assertTrue(page.btn_save.isVisible())
        self.assertTrue(page.scroll.isVisible())


class Win11ScheduleAndHistoryResponsiveTests(QtAppTestCase):
    def test_schedule_page_stacks_workspace_and_keeps_actions_visible(self) -> None:
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

        self.addCleanup(cleanup_widget, page)
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertTrue(page.btn_toggle_task.isVisible())
        self.assertTrue(page.btn_save.isVisible())
        self.assertEqual(page.workspace_splitter.orientation(), Qt.Orientation.Vertical)

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
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        primary_actions = page.findChild(QObject, "page_primary_actions")
        self.assertIsNotNone(primary_actions)
        self.assertTrue(primary_actions.isVisible())
        self.assertEqual(page.filter_grid.property("compact"), True)
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
                    "port": 1433,
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
                    {"Customers": "t_customer", "Orders": "t_order"},
                    {"Invoices": "t_invoice"},
                ],
            ),
            patch(
                "src.gui.pages.forms_page.config_manager.get_sync_config",
                side_effect=[
                    {"default_forms": ["Customers"]},
                    {"default_forms": ["Invoices"]},
                ],
            ),
        ):
            page = FormConfigPage(gui)
            page.load_forms()

        self.addCleanup(cleanup_widget, page)

        self.assertEqual(len(page.form_widgets), 1)
        self.assertEqual(page.scroll_layout.count(), 2)
        self.assertEqual(page.scroll_layout.itemAt(0).widget(), page.form_widgets[0][1])
        self.assertEqual(page.form_widgets[0][0], "Invoices")
        self.assertTrue(page.form_widgets[0][1].property("last"))
        self.assertEqual(
            len([row for _name, row, _cb in page.form_widgets if row.property("last")]),
            1,
        )

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

        log_text = page.log_text.toPlainText()
        self.assertIn("<b>unsafe</b>", log_text)
        self.assertIn("{'status': 'ok'}", log_text)

    def test_schedule_page_append_log_escapes_html(self) -> None:
        with (
            patch("src.gui.pages.schedule_page.app_logger.add_log_handler"),
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_last_exec_time", return_value=None),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_next_exec_time", return_value=None),
        ):
            page = self.build_schedule_page()
        self.addCleanup(cleanup_widget, page)

        page.append_log("<i>scheduled</i>", "WARNING")
        self.assertIn("<i>scheduled</i>", page.log_text.toPlainText())

    def test_schedule_page_timer_runs_only_while_visible(self) -> None:
        with (
            patch("src.gui.pages.schedule_page.app_logger.add_log_handler"),
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_last_exec_time", return_value=None),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_next_exec_time", return_value=None),
        ):
            page = self.build_schedule_page()
        self.addCleanup(cleanup_widget, page)

        self.assertFalse(page.timer.isActive())

        page.show()
        self._app.processEvents()
        self.assertTrue(page.timer.isActive())

        page.hide()
        self._app.processEvents()
        self.assertFalse(page.timer.isActive())

    def test_schedule_page_removes_global_log_handler_on_destroy(self) -> None:
        root_logger = logging.getLogger()
        with (
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_last_exec_time", return_value=None),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_next_exec_time", return_value=None),
        ):
            page = self.build_schedule_page()

        handler = page.log_handler
        self.assertIn(handler, root_logger.handlers)

        cleanup_widget(page)
        self.assertNotIn(handler, root_logger.handlers)

    def test_schedule_page_load_config_resets_loading_flag_after_exception(self) -> None:
        with (
            patch("src.gui.pages.schedule_page.app_logger.add_log_handler"),
            patch("src.gui.pages.schedule_page.config_manager.get_sync_config", return_value={"auto_sync": False, "sync_interval": 60}),
            patch("src.gui.pages.schedule_page.auto_scheduler.is_running", return_value=False),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_last_exec_time", return_value=None),
            patch("src.gui.pages.schedule_page.auto_scheduler.get_next_exec_time", return_value=None),
        ):
            page = self.build_schedule_page()
        self.addCleanup(cleanup_widget, page)

        with patch("src.gui.pages.schedule_page.config_manager.get_sync_config", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                page.load_config()

        self.assertFalse(page._loading_config)

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

        status_card = window.findChild(QObject, "status_card")
        self.assertIsNotNone(status_card)
        self.assertEqual(status_card.property("ui"), "win11-sidebar-status")

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
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        self.assertEqual(window.btn_search.text(), "搜索")
        self.assertEqual(window.btn_notice.text(), "历史记录")
        self.assertEqual(window.btn_setting.text(), "系统设置")
        self.assertEqual(window.topbar_search.placeholderText(), "搜索页面、功能或关键字")
        self.assertEqual(window.topbar_user.text(), "金")


class Win11DashboardAndSyncCopyZhCnSmokeTests(QtAppTestCase):
    def test_dashboard_page_key_copy_is_simplified_chinese(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)

        self.addCleanup(cleanup_widget, page)

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "运营总览")

        self.assertEqual(page.refresh_btn.text(), "刷新数据")
        self.assertEqual(page.card_count.title_label.text(), "今日任务数")

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
            patch(
                "src.gui.pages.settings_page.settings_service.get_config_source_name",
                return_value="用户配置文件",
            ) as get_config_source_name,
            patch(
                "src.gui.pages.settings_page.settings_service.get_config_source",
                return_value="C:/Kingdee/config.ini",
            ) as get_config_source,
            patch(
                "src.gui.pages.settings_page.settings_service.get_database_type",
                return_value="SQL Server",
            ) as get_database_type,
            patch("src.gui.pages.settings_page.UiFeedback.error") as error_feedback,
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "系统设置")

        self.assertEqual(page.btn_test.text(), "测试连接")
        self.assertEqual(page.btn_save.text(), "保存设置")
        self.assertEqual(page.hero_source.text(), "配置来源：C:/Kingdee/config.ini")
        self.assertEqual(page.summary_source.value_label.text(), "用户配置文件")
        self.assertIn("当前来源路径：C:/Kingdee/config.ini", page.summary_source.subtitle_label.text())
        self.assertEqual(page.summary_db.value_label.text(), "SQL Server")

        get_config_source_name.assert_called_once()
        get_config_source.assert_called_once()
        get_database_type.assert_called_once()
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
        self.assertEqual(page.password.placeholderText(), "如需更新密码请填写；留空则保持不变")
        self.assertEqual(page.db_password.placeholderText(), "如需更新数据库密码请填写；留空则保持不变")

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

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "默认表单集")

        self.assertEqual(page.btn_reset.text(), "重置")
        self.assertEqual(page.btn_select_all.text(), "全选")


class Win11ScheduleAndHistoryCopyZhCnSmokeTests(QtAppTestCase):
    def test_schedule_page_key_copy_is_simplified_chinese(self) -> None:
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

        self.addCleanup(cleanup_widget, page)

        hero_title = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero_title)
        self.assertEqual(hero_title.text(), "调度管理")
        self.assertEqual(page.btn_toggle_task.text(), "启动任务")

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
        self.assertEqual(hero_title.text(), "历史记录")
        self.assertEqual(page.btn_export.text(), "导出")
        self.assertEqual(page.btn_prev.text(), "上一页")
        self.assertEqual(page.btn_next.text(), "下一页")


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

            # Choose "default set" via stable data and choose "full" mode via stable data.
            self._set_combo_by_data(page.form_selector, FORM_DEFAULT_DATA)
            self._set_combo_by_data(page.sync_type_combo, "full")

            page.start_sync()

            self.assertEqual(captured.get("forms"), ["Customers", "Orders"])
            # Just assert it's the FULL SyncType object (not derived from index order).
            self.assertEqual(getattr(captured.get("sync_type"), "name", ""), "FULL")

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
        with open(stylesheet_path, "r", encoding="utf-8") as stylesheet:
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
        with open(stylesheet_path, "r", encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertNotRegex(css, r"(?m)^QScrollArea,\s*$")
        self.assertNotRegex(css, r"(?m)^QScrollArea\s*>\s*QWidget\s*>\s*QWidget\s*\{")

    def test_stylesheet_includes_win11_page_specific_text_and_table_selectors(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, "r", encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertIn('QLabel[ui="win11-status-chip"]', css)
        self.assertIn('QLabel[ui="win11-meta-text"]', css)
        self.assertIn('QLabel[ui="win11-helper-text"]', css)
        self.assertIn('QTableWidget[ui="win11-data-table"]', css)
        self.assertIn('QLabel[ui="win11-table-tag"]', css)
        self.assertIn('QFrame[ui="win11-pagination-card"]', css)
        self.assertIn('QLabel[ui="win11-page-badge"]', css)

    def test_stylesheet_keeps_only_one_global_widget_base_pass(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, "r", encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertEqual(len(re.findall(r"(?m)^QMainWindow\s*\{", css)), 1)
        self.assertEqual(len(re.findall(r"(?m)^QWidget\s*\{", css)), 1)

    def test_stylesheet_reasserts_win11_progress_and_header_scoping(self) -> None:
        stylesheet_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "styles.css"
        )
        with open(stylesheet_path, "r", encoding="utf-8") as stylesheet:
            css = stylesheet.read()

        self.assertIn('QWidget[ui="win11-page"] QProgressBar', css)
        self.assertIn('QTableWidget[ui="win11-data-table"] QHeaderView::section', css)


if __name__ == "__main__":
    unittest.main()
