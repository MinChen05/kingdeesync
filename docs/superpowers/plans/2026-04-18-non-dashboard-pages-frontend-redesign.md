# Non-Dashboard Pages Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the five non-dashboard desktop pages (`sync`, `settings`, `forms`, `schedule`, `history`) into distinct Windows 11 workbench layouts that remain fully usable at `1366x768` and expand naturally at higher resolutions.

**Architecture:** Keep the current frameless shell and all service-layer behavior intact, but refactor the page scaffold, shell responsiveness, and per-page layouts so each page expresses a different task model. Implement the redesign in four slices: shared responsive primitives, sync cockpit, settings/forms management surfaces, and schedule/history control-and-query surfaces, then verify with offscreen rendering and the GUI smoke suite.

**Tech Stack:** Python 3.11, PySide6, Qt stylesheets, unittest, offscreen Qt smoke tests

---

## File Structure

- `src/gui/components/page_shell.py`
  Responsibility: shared page scaffold markers, page variant helpers, and resolution-mode state used by the redesigned pages.
- `src/gui/kingdee_sync_gui.py`
  Responsibility: shell-level responsive sizing and spacing that supports the redesigned non-dashboard pages.
- `src/gui/pages/sync_page.py`
  Responsibility: task-cockpit redesign for manual sync execution, with distinct configuration and monitoring zones.
- `src/gui/pages/settings_page.py`
  Responsibility: configuration-center redesign for API and database settings, with stronger field alignment and responsive form rows.
- `src/gui/pages/forms_page.py`
  Responsibility: list-management redesign for default form selection, with search, batch actions, and list-priority layout.
- `src/gui/pages/schedule_page.py`
  Responsibility: state-control redesign for scheduler configuration, runtime status, and log visibility.
- `src/gui/pages/history_page.py`
  Responsibility: query-results redesign for filtering, result browsing, exporting, and pagination.
- `assets/styles.css`
  Responsibility: page-variant-specific Windows 11 styles and responsive spacing rules.
- `tests/test_gui_windows11_shell.py`
  Responsibility: GUI smoke tests for layout markers, visibility, responsive stacking, and resolution behavior.

---

### Task 1: Add Shared Responsive Primitives For Non-Dashboard Workbench Pages

**Files:**
- Modify: `src/gui/components/page_shell.py`
- Modify: `src/gui/kingdee_sync_gui.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing shared primitive tests**

```python
class NonDashboardWorkbenchShellTests(QtAppTestCase):
    def test_scaffold_supports_page_variant_and_resolution_mode(self) -> None:
        from src.gui.components.page_shell import Win11PageScaffold

        page = Win11PageScaffold(title="Demo")
        self.addCleanup(cleanup_widget, page)

        page.setProperty("pageVariant", "control")
        page.setProperty("resolutionMode", "compact")

        self.assertEqual(page.property("pageVariant"), "control")
        self.assertEqual(page.property("resolutionMode"), "compact")

    def test_shell_compacts_search_and_main_splitter_at_1366x768(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        window.resize(1366, 768)
        window.show()
        self._app.processEvents()

        self.assertTrue(window.sidebar_compact)
        self.assertLessEqual(window.topbar_search.maximumWidth(), 200)
        self.assertLessEqual(window.main_splitter.sizes()[0], 120)
```

- [ ] **Step 2: Run the focused primitive tests to verify they fail**

Run: `python -m unittest tests.test_gui_windows11_shell.NonDashboardWorkbenchShellTests -q`

Expected: `FAIL` because the new test class does not exist yet.

- [ ] **Step 3: Add page variant and resolution mode helpers to the shared scaffold**

Insert these two lines immediately after `self.setProperty("ui", "win11-page")` inside `Win11PageScaffold.__init__`:

```python
self.setProperty("pageVariant", "default")
self.setProperty("resolutionMode", "wide")
```

Add these methods to `Win11PageScaffold`:

```python
def set_page_variant(self, value: str) -> None:
    self.setProperty("pageVariant", value or "default")
    style = self.style()
    if style is not None:
        style.unpolish(self)
        style.polish(self)

def set_resolution_mode(self, compact: bool) -> None:
    self.setProperty("resolutionMode", "compact" if compact else "wide")
    style = self.style()
    if style is not None:
        style.unpolish(self)
        style.polish(self)
```

- [ ] **Step 4: Reassert shell compact behavior as the shared baseline**

Keep `_apply_responsive_shell_layout()` in `src/gui/kingdee_sync_gui.py` in this form:

```python
def _apply_responsive_shell_layout(self):
    compact = self.width() <= 1366
    self.sidebar_compact = compact

    if self.sidebar is not None:
        self.sidebar.setProperty("compact", compact)
        self.sidebar.setMaximumWidth(self.sidebar_compact_width if compact else 320)
        sidebar_style = self.sidebar.style()
        if sidebar_style is not None:
            sidebar_style.unpolish(self.sidebar)
            sidebar_style.polish(self.sidebar)

    if self.sidebar_logo_subtitle is not None:
        self.sidebar_logo_subtitle.setVisible(not compact)
    if self.sidebar_section_title is not None:
        self.sidebar_section_title.setVisible(not compact)
    if self.sidebar_status_card is not None:
        self.sidebar_status_card.setVisible(not compact)

    if self.topbar_search is not None:
        self.topbar_search.setMaximumWidth(180 if compact else 280)

    if self.main_splitter is not None:
        sidebar_width = self.sidebar_compact_width if compact else self.sidebar_expanded_width
        content_width = max(960, self.width() - sidebar_width)
        self.main_splitter.setSizes([sidebar_width, content_width])
```

- [ ] **Step 5: Add shared CSS selectors for page variants and compact mode**

Append these selectors to `assets/styles.css`:

```css
QWidget[ui="win11-page"][pageVariant="control"] QFrame[ui="win11-section-card"] {
    border-radius: 20px;
}

QWidget[ui="win11-page"][pageVariant="records"] QFrame[ui="win11-section-card"] {
    border-radius: 16px;
}

QWidget[ui="win11-page"][resolutionMode="compact"] QFrame[ui="win11-primary-action-bar"] {
    padding: 8px;
}

QWidget[ui="win11-page"][resolutionMode="compact"] QLabel[ui="win11-section-subtitle"] {
    font-size: 12px;
}
```

- [ ] **Step 6: Run the focused primitive tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.NonDashboardWorkbenchShellTests -q`

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py assets/styles.css
git commit -m "feat: add non-dashboard shared workbench primitives"
```

### Task 2: Redesign Sync Page As A Task Cockpit

**Files:**
- Modify: `src/gui/pages/sync_page.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing sync cockpit tests**

```python
class SyncCockpitRedesignTests(QtAppTestCase):
    def test_sync_page_marks_itself_as_control_variant(self) -> None:
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
        self.assertEqual(page.property("pageVariant"), "control")

    def test_sync_page_compacts_to_vertical_monitor_stack_at_1366x768(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["Customers", "Orders"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["Customers"], "sync_type": "full"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1366, 768)
        page.show()
        self._app.processEvents()

        self.assertEqual(page.workspace_splitter.orientation(), Qt.Orientation.Vertical)
        self.assertEqual(page.property("resolutionMode"), "compact")
        self.assertTrue(page.log_card.isVisible())
```

- [ ] **Step 2: Run the focused sync tests to verify they fail**

Run: `python -m unittest tests.test_gui_windows11_shell.SyncCockpitRedesignTests -q`

Expected: `FAIL` because the page does not yet mark its variant or set its page-level `resolutionMode`.

- [ ] **Step 3: Mark `SyncPage` as the control workbench variant**

Inside `SyncPage.__init__`, add this line immediately after `self.setProperty("page", "sync")`:

```python
self.set_page_variant("control")
```

Use this `setup_ui()` body:

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.test_conn_btn)
    self.add_primary_action(self.start_sync_btn)
    self.set_content(self._create_workspace())
    self._apply_workspace_layout()
```

- [ ] **Step 4: Rebuild the sync page into a left-config / right-monitor cockpit**

Use this `def _create_workspace(self) -> QWidget:` body:

```python
def _create_workspace(self) -> QWidget:
    root = QWidget()
    root_layout = QVBoxLayout(root)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(0)

    self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
    self.workspace_splitter.setProperty("ui", "win11-page-splitter")
    self.workspace_splitter.setChildrenCollapsible(False)
    self.workspace_splitter.setHandleWidth(6)
    root_layout.addWidget(self.workspace_splitter, 1)

    self.config_container = QWidget()
    self.config_container.setProperty("ui", "sync-config-pane")
    config_layout = QVBoxLayout(self.config_container)
    config_layout.setContentsMargins(0, 0, 0, 0)
    config_layout.setSpacing(14)
    config_layout.addWidget(
        self._create_group_card(
            "同步配置",
            "选择范围和模式后再启动同步。",
            [
                self._create_setting_row("表单范围", "选择全量、单表或默认集合。", self._create_form_selector()),
                self._create_setting_row("同步模式", "根据场景选择增量、全量或完整同步。", self._create_mode_selector(), last=True),
            ],
        )
    )
    config_layout.addWidget(self._create_strategy_card())
    config_layout.addStretch(1)

    self.monitor_container = QWidget()
    self.monitor_container.setProperty("ui", "sync-monitor-pane")
    monitor_layout = QVBoxLayout(self.monitor_container)
    monitor_layout.setContentsMargins(0, 0, 0, 0)
    monitor_layout.setSpacing(14)
    monitor_layout.addWidget(self._create_execution_card())
    monitor_layout.addWidget(self._create_log_card(), 1)

    self.workspace_splitter.addWidget(self.config_container)
    self.workspace_splitter.addWidget(self.monitor_container)
    self.workspace_splitter.setStretchFactor(0, 2)
    self.workspace_splitter.setStretchFactor(1, 3)
    self.workspace_splitter.setSizes([520, 960])
    return root
```

- [ ] **Step 5: Make the sync page resolution-aware**

Use this `def _apply_workspace_layout(self) -> None:` body:

```python
def _apply_workspace_layout(self) -> None:
    if self.workspace_splitter is None:
        return

    compact = self.width() <= 1366
    self.set_resolution_mode(compact)
    self.workspace_splitter.setOrientation(Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal)
    self.config_container.setMinimumWidth(0 if compact else 360)
    self.config_container.setMaximumWidth(16777215 if compact else 420)
    self.log_text.setMinimumHeight(180 if compact else 220)
    if hasattr(self, "execution_card"):
        self.execution_card.setMaximumHeight(320 if compact else 16777215)
    self.workspace_splitter.setSizes([330, 390] if compact else [540, 980])
```

- [ ] **Step 6: Add sync-cockpit-specific styles**

Append these selectors to `assets/styles.css`:

```css
QWidget[ui="win11-page"][pageVariant="control"] QWidget[ui="sync-config-pane"] QFrame[ui="win11-section-card"] {
    border-radius: 20px;
}

QWidget[ui="win11-page"][pageVariant="control"] QWidget[ui="sync-monitor-pane"] QFrame[ui="win11-section-card"] {
    border-color: #d5e3f6;
}

QWidget[ui="win11-page"][pageVariant="control"][resolutionMode="compact"] QWidget[ui="sync-config-pane"] {
    margin-bottom: 8px;
}
```

- [ ] **Step 7: Run the focused sync tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.SyncCockpitRedesignTests -q`

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/pages/sync_page.py assets/styles.css
git commit -m "feat: redesign sync page as responsive task cockpit"
```

### Task 3: Redesign Settings And Forms As Distinct Management Surfaces

**Files:**
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing settings/forms redesign tests**

```python
class SettingsAndFormsWorkbenchTests(QtAppTestCase):
    def test_settings_page_marks_itself_as_configuration_variant(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch(
            "src.gui.pages.settings_page.settings_service.get_settings_snapshot",
            return_value={"kingdee": {}, "database": {}},
        ):
            page = SettingsPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("pageVariant"), "configuration")

    def test_forms_page_marks_itself_as_list_management_variant(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={"Customers": "t_customer"}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": ["Customers"]}),
        ):
            page = FormConfigPage(gui)

        self.addCleanup(cleanup_widget, page)
        self.assertEqual(page.property("pageVariant"), "list-management")

    def test_settings_page_switches_to_compact_row_layout_at_1366x768(self) -> None:
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

        self.assertEqual(page.property("resolutionMode"), "compact")
        self.assertEqual(page.property("layoutMode"), "compact")
```

- [ ] **Step 2: Run the focused settings/forms tests to verify they fail**

Run: `python -m unittest tests.test_gui_windows11_shell.SettingsAndFormsWorkbenchTests -q`

Expected: `FAIL` because neither page currently marks its variant and the new test class does not yet exist.

- [ ] **Step 3: Mark settings as the configuration-center variant**

Inside `SettingsPage.__init__`, add this line immediately after `self.setProperty("page", "settings")`:

```python
self.set_page_variant("configuration")
```

Use this `def _apply_responsive_rows(self) -> None:` body:

```python
def _apply_responsive_rows(self) -> None:
    compact = self.width() <= 1366
    self.set_resolution_mode(compact)
    self.setProperty("layoutMode", "compact" if compact else "wide")
    for row, layout, editor in self._setting_rows:
        layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        if isinstance(editor, QSpinBox):
            editor.setFixedWidth(120 if compact else 140)
        else:
            editor.setMinimumWidth(0)
            editor.setMaximumWidth(16777215 if compact else 420)
```

- [ ] **Step 4: Reframe settings as a stronger two-group configuration center**

Use this `def _create_scroll_content(self) -> QScrollArea:` body:

```python
def _create_scroll_content(self) -> QScrollArea:
    scroll = self.create_scroll_container("settings_scroll")

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(18)
    layout.addWidget(
        self._create_group_card(
            "金蝶 API",
            "维护登录、查询与账套参数。",
            [
                self._create_setting_row("登录地址", "用于身份认证的接口地址。", self.login_url),
                self._create_setting_row("查询地址", "用于业务查询的接口地址。", self.query_url),
                self._create_setting_row("账套 ID", "金蝶账套标识。", self.acct_id),
                self._create_setting_row("用户名", "用于 WebAPI 登录的账号。", self.username),
                self._create_setting_row("密码", "留空则沿用已保存密码。", self.password, last=True),
            ],
        )
    )
    layout.addWidget(
        self._create_group_card(
            "数据库连接",
            "维护目标数据库连接参数。",
            [
                self._create_setting_row("主机", "数据库主机或实例名称。", self.db_host),
                self._create_setting_row("端口", "SQL Server 默认端口为 1433。", self.db_port),
                self._create_setting_row("数据库名", "目标业务数据库名。", self.db_name),
                self._create_setting_row("用户名", "数据库登录账号。", self.db_user),
                self._create_setting_row("密码", "留空则沿用已保存数据库密码。", self.db_password, last=True),
            ],
        )
    )
    layout.addWidget(self._create_note_card())
    layout.addStretch(1)

    scroll.setWidget(page)
    return scroll
```

- [ ] **Step 5: Mark forms as the list-management variant and keep the list dominant**

Inside `FormConfigPage.__init__`, add this line immediately after `self.setProperty("page", "forms")`:

```python
self.set_page_variant("list-management")
```

Use this `def _apply_action_sizing(self) -> None:` body:

```python
def _apply_action_sizing(self) -> None:
    compact = self.width() <= 1366
    self.set_resolution_mode(compact)
    self.search_box.setMinimumWidth(180 if compact else 260)
    self.search_box.setMaximumWidth(260 if compact else 320)
```

Use this `def _create_scroll_content(self) -> QScrollArea:` body:

```python
def _create_scroll_content(self) -> QScrollArea:
    scroll = self.create_scroll_container("forms_page_scroll")

    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    layout.addWidget(self._create_filter_card())
    layout.addWidget(self._create_form_list_card(), 1)
    layout.addWidget(self._create_footer_card())

    scroll.setWidget(page)
    return scroll
```

- [ ] **Step 6: Add configuration and list-management styles**

Append these selectors to `assets/styles.css`:

```css
QWidget[ui="win11-page"][pageVariant="configuration"] QFrame[ui="win11-setting-row"] {
    border-bottom: 1px solid #e8eef6;
}

QWidget[ui="win11-page"][pageVariant="configuration"][resolutionMode="compact"] QFrame[ui="win11-section-card"] {
    border-radius: 18px;
}

QWidget[ui="win11-page"][pageVariant="list-management"] QScrollArea {
    background: transparent;
}

QWidget[ui="win11-page"][pageVariant="list-management"] QFrame[ui="win11-section-card"] {
    border-radius: 18px;
}
```

- [ ] **Step 7: Run the focused settings/forms tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.SettingsAndFormsWorkbenchTests -q`

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py assets/styles.css
git commit -m "feat: redesign settings and forms as management surfaces"
```

### Task 4: Redesign Schedule And History As Distinct Control-And-Query Pages

**Files:**
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing schedule/history redesign tests**

```python
class ScheduleAndHistoryWorkbenchTests(QtAppTestCase):
    def test_schedule_page_marks_itself_as_control_panel_variant(self) -> None:
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
        self.assertEqual(page.property("pageVariant"), "control-panel")

    def test_history_page_marks_itself_as_records_variant(self) -> None:
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
        self.assertEqual(page.property("pageVariant"), "records")

    def test_history_page_switches_filter_grid_to_compact_mode_at_1366x768(self) -> None:
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

        self.assertEqual(page.property("resolutionMode"), "compact")
        self.assertEqual(page.filter_grid.property("compact"), True)
```

- [ ] **Step 2: Run the focused schedule/history tests to verify they fail**

Run: `python -m unittest tests.test_gui_windows11_shell.ScheduleAndHistoryWorkbenchTests -q`

Expected: `FAIL` because the pages do not yet expose these variants and the new test class does not yet exist.

- [ ] **Step 3: Mark schedule as the control-panel variant and keep status-first ordering**

Inside `SchedulePage.__init__`, add this line immediately after `self.setProperty("page", "schedule")`:

```python
self.set_page_variant("control-panel")
```

Use this `def _apply_workspace_layout(self) -> None:` body:

```python
def _apply_workspace_layout(self) -> None:
    if self.workspace_splitter is None:
        return

    compact = self.width() <= 1366
    self.set_resolution_mode(compact)
    self.workspace_splitter.setOrientation(Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal)
    self.left_panel.setMinimumWidth(0 if compact else 420)
    self.left_panel.setMaximumWidth(16777215 if compact else 560)
    self.log_text.setMinimumHeight(180 if compact else 220)
    status_card_min = max(220, self.status_card.minimumHeight())
    self.workspace_splitter.setSizes([status_card_min + 160, 300] if compact else [560, 920])
```

- [ ] **Step 4: Mark history as the records variant and formalize the filter-grid query layout**

Inside `HistoryPage.__init__`, add this line immediately after `self.setProperty("page", "history")`:

```python
self.set_page_variant("records")
```

Use this `def _apply_filter_layout(self) -> None:` body:

```python
def _apply_filter_layout(self) -> None:
    compact = self.width() <= 1366
    self.set_resolution_mode(compact)
    self.filter_grid.setProperty("compact", compact)
    while self.filter_grid_layout.count():
        item = self.filter_grid_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)

    positions = [(0, 0), (0, 1), (1, 0), (1, 1)] if compact else [(0, 0), (0, 1), (0, 2), (0, 3)]
    for (row, col), widget in zip(positions, self.filter_fields):
        self.filter_grid_layout.addWidget(widget, row, col)
```

- [ ] **Step 5: Reframe history as a query-results page**

Use this `def _create_content(self) -> QWidget:` body:

```python
def _create_content(self) -> QWidget:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(14)
    layout.addWidget(self._create_filter_card())
    layout.addWidget(self._create_table_card(), 1)
    layout.addWidget(self._create_pagination_card())
    return root
```

Use this `def _create_filter_card(self) -> Win11SectionCard:` body:

```python
def _create_filter_card(self) -> Win11SectionCard:
    card = Win11SectionCard("筛选条件", "按关键字、时间、状态和类型筛选结果。")

    self.filter_grid = QWidget()
    self.filter_grid.setProperty("compact", False)
    self.filter_grid_layout = QGridLayout(self.filter_grid)
    self.filter_grid_layout.setContentsMargins(0, 0, 0, 0)
    self.filter_grid_layout.setHorizontalSpacing(12)
    self.filter_grid_layout.setVerticalSpacing(12)
    self.filter_fields = [
        self._create_inline_field("搜索", self.search_box),
        self._create_inline_field("时间范围", self.combo_time_range),
        self._create_inline_field("状态", self.combo_status),
        self._create_inline_field("类型", self.combo_type),
    ]
    card.content_layout.addWidget(self.filter_grid)
    return card
```

- [ ] **Step 6: Add control-panel and records-page styles**

Append these selectors to `assets/styles.css`:

```css
QWidget[ui="win11-page"][pageVariant="control-panel"] QFrame[ui="win11-section-card"] {
    border-radius: 18px;
}

QWidget[ui="win11-page"][pageVariant="control-panel"] QFrame[ui="win11-log-toolbar"] {
    border-radius: 12px;
}

QWidget[ui="win11-page"][pageVariant="records"] QFrame[ui="win11-pagination-card"] {
    border-radius: 16px;
}

QWidget[ui="win11-page"][pageVariant="records"][resolutionMode="compact"] QWidget[compact="true"] QLabel[ui="win11-row-note"] {
    line-height: 1.35;
}
```

- [ ] **Step 7: Run the focused schedule/history tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.ScheduleAndHistoryWorkbenchTests -q`

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py assets/styles.css
git commit -m "feat: redesign schedule and history as control-and-query pages"
```

### Task 5: Run Full Verification For The Five-Page Frontend Redesign

**Files:**
- Review: `src/gui/components/page_shell.py`
- Review: `src/gui/kingdee_sync_gui.py`
- Review: `src/gui/pages/sync_page.py`
- Review: `src/gui/pages/settings_page.py`
- Review: `src/gui/pages/forms_page.py`
- Review: `src/gui/pages/schedule_page.py`
- Review: `src/gui/pages/history_page.py`
- Review: `assets/styles.css`
- Review: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Run the full GUI smoke suite**

Run: `python -m unittest tests.test_gui_windows11_shell -q`

Expected: `OK`

- [ ] **Step 2: Run GUI compile validation**

Run: `python -m compileall -q src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py src/gui/pages`

Expected: no output

- [ ] **Step 3: Validate shell launch at `1366x768` and compact shell mode**

Run:

```bash
$env:QT_QPA_PLATFORM='offscreen'; @'
from PySide6.QtWidgets import QApplication
from src.gui.kingdee_sync_gui import KingdeeSyncGUI
app = QApplication.instance() or QApplication([])
window = KingdeeSyncGUI()
window.resize(1366, 768)
window.show()
app.processEvents()
print(window.size().width(), window.size().height(), window.sidebar_compact)
window.close()
window.deleteLater()
app.processEvents()
app.quit()
'@ | python -
```

Expected: `1366 768 True`

- [ ] **Step 4: Confirm the dashboard page remains out of scope**

Run: `rg -n "pageVariant|resolutionMode" src/gui/pages/dashboard_page.py`

Expected: no output or only pre-existing markers unrelated to this five-page redesign

- [ ] **Step 5: Commit the integrated five-page redesign**

```bash
git add src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: redesign non-dashboard pages with responsive frontend layouts"
```
