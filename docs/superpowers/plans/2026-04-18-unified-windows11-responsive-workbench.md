# Unified Windows 11 Responsive Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a single Windows 11-style responsive desktop workbench across the shell and six primary GUI pages while keeping all existing sync, settings, schedule, forms, dashboard, and history behaviors intact at `1366x768`.

**Architecture:** Build the redesign on top of the existing `Win11PageScaffold` and `KingdeeSyncGUI` shell instead of replacing the PySide6 app structure. Add shared responsive shell/scaffold primitives first, then refactor pages in three focused pairs (`dashboard/sync`, `settings/forms`, `schedule/history`), and close with GUI smoke tests, stylesheet checks, and offscreen validation.

**Tech Stack:** Python 3.11, PySide6, Qt stylesheets, unittest, offscreen Qt smoke tests

---

## Preflight Notes

- The current repository is already dirty. Execute this plan in a fresh git worktree before changing code so feature work stays isolated from unrelated modifications already present in `d:\Kingdee`.
- Keep commits scoped exactly to the files listed in each task.
- Do not change service-layer behavior or business semantics while restructuring the GUI.

## File Structure

- `src/gui/components/page_shell.py`
  Responsibility: shared Windows 11 page scaffold, primary action bar, shared scroll container helper, and page-level responsive hooks.
- `src/gui/kingdee_sync_gui.py`
  Responsibility: responsive shell behavior, adaptive sidebar compaction, compact top command bar behavior, and shell-level sizing hooks.
- `src/gui/pages/dashboard_page.py`
  Responsibility: dashboard hero, primary action placement, compact analytics stacking, and safe chart/table workspace behavior.
- `src/gui/pages/sync_page.py`
  Responsibility: sync workbench layout, compact action bar, responsive workspace stacking, and stable log/monitor behavior.
- `src/gui/pages/settings_page.py`
  Responsibility: configuration-center layout, responsive editor rows, compact action bar, and scroll-safe grouped settings.
- `src/gui/pages/forms_page.py`
  Responsibility: list-first default-form management, top action bar controls, compact search behavior, and stable selection summary.
- `src/gui/pages/schedule_page.py`
  Responsibility: scheduler control console, responsive workspace stacking, compact action bar, and stable log tooling layout.
- `src/gui/pages/history_page.py`
  Responsibility: filter-first history layout, responsive filter grid, stable export/query actions, and always-reachable pagination.
- `assets/styles.css`
  Responsibility: remove conflicting legacy Apple selectors, define the single Windows 11 visual system, and style compact shell/page states.
- `tests/test_gui_windows11_shell.py`
  Responsibility: shell/scaffold smoke tests, `1366x768` visibility and orientation assertions, and stylesheet guardrails.

---

### Task 1: Establish Shared Responsive Shell And Scaffold Primitives

**Files:**
- Modify: `src/gui/components/page_shell.py`
- Modify: `src/gui/kingdee_sync_gui.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing scaffold and shell responsiveness tests**

```python
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
        self.assertTrue(primary_actions.isVisible())

        scroll = scaffold.create_scroll_container("demo_scroll")
        self.assertEqual(scroll.objectName(), "demo_scroll")
        self.assertEqual(scroll.property("ui"), "win11-page-scroll")

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
```

- [ ] **Step 2: Run the focused tests to confirm the current code fails**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ResponsiveShellSmokeTests -q`

Expected: `FAIL` because `Win11PageScaffold` does not expose `page_primary_actions` or `create_scroll_container()`, and `KingdeeSyncGUI` does not compact the sidebar at `1366x768`.

- [ ] **Step 3: Extend `Win11PageScaffold` with a primary action bar and scroll-container helper**

```python
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
```

```python
class Win11PageScaffold(QWidget):
    def __init__(
        self,
        title: str = "",
        *,
        eyebrow: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("ui", "win11-page")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 18)
        root.setSpacing(12)

        self.hero_card = QFrame(self)
        self.hero_card.setObjectName("page_hero_card")
        self.hero_card.setProperty("ui", "win11-hero-card")
        self.hero_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(16)

        hero_text_host = QWidget(self.hero_card)
        hero_text_host.setProperty("ui", "win11-hero-copy")
        hero_text_layout = QVBoxLayout(hero_text_host)
        hero_text_layout.setContentsMargins(0, 0, 0, 0)
        hero_text_layout.setSpacing(4)

        self.hero_eyebrow = QLabel("", hero_text_host)
        self.hero_eyebrow.setObjectName("page_hero_eyebrow")
        self.hero_eyebrow.setProperty("ui", "win11-hero-eyebrow")
        self.hero_eyebrow.setVisible(False)

        self.hero_title = QLabel(title, hero_text_host)
        self.hero_title.setObjectName("page_hero_title")
        self.hero_title.setProperty("ui", "win11-hero-title")
        self.hero_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.hero_subtitle = QLabel("", hero_text_host)
        self.hero_subtitle.setObjectName("page_hero_subtitle")
        self.hero_subtitle.setProperty("ui", "win11-hero-subtitle")
        self.hero_subtitle.setWordWrap(True)
        self.hero_subtitle.setVisible(False)

        hero_text_layout.addWidget(self.hero_eyebrow)
        hero_text_layout.addWidget(self.hero_title)
        hero_text_layout.addWidget(self.hero_subtitle)
        hero_layout.addWidget(hero_text_host, 1)

        self.hero_actions_host = QWidget(self.hero_card)
        self.hero_actions_host.setObjectName("page_hero_actions")
        self.hero_actions_host.setProperty("ui", "win11-hero-actions")
        self.hero_actions_host.setVisible(False)

        self.hero_actions_layout = QHBoxLayout(self.hero_actions_host)
        self.hero_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.hero_actions_layout.setSpacing(12)
        self.hero_actions_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        hero_layout.addWidget(self.hero_actions_host, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.primary_action_host = QFrame(self)
        self.primary_action_host.setObjectName("page_primary_actions")
        self.primary_action_host.setProperty("ui", "win11-primary-action-bar")
        self.primary_action_host.setVisible(False)

        self.primary_action_layout = QHBoxLayout(self.primary_action_host)
        self.primary_action_layout.setContentsMargins(14, 12, 14, 12)
        self.primary_action_layout.setSpacing(10)

        self.summary_strip = QWidget(self)
        self.summary_strip.setObjectName("page_summary_strip")
        self.summary_strip.setProperty("ui", "win11-summary-strip")

        summary_layout = QHBoxLayout(self.summary_strip)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)
        summary_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.content_host = QWidget(self)
        self.content_host.setObjectName("page_content_host")
        self.content_host.setProperty("ui", "win11-content-host")
        self.content_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content_layout = QVBoxLayout(self.content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        root.addWidget(self.hero_card)
        root.addWidget(self.primary_action_host)
        root.addWidget(self.summary_strip)
        root.addWidget(self.content_host, 1)

        self.set_hero_eyebrow(eyebrow)
        self.set_hero_subtitle(subtitle)

    def add_primary_action(self, widget: QWidget) -> None:
        self.primary_action_host.setVisible(True)
        self.primary_action_layout.addWidget(widget)

    def create_scroll_container(self, object_name: str) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setObjectName(object_name)
        scroll.setProperty("ui", "win11-page-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll
```

- [ ] **Step 4: Add compact shell hooks to `KingdeeSyncGUI`**

Add these attributes inside `KingdeeSyncGUI.__init__` near the existing shell state fields:

```python
self.sidebar = None
self.sidebar_status_card = None
self.sidebar_compact = False
self.sidebar_expanded_width = 256
self.sidebar_compact_width = 96
self.topbar_action_buttons = []
```

Insert these assignments inside `create_sidebar()` after the corresponding widgets are created:

```python
self.sidebar = sidebar
self.sidebar_logo_subtitle = logo_subtitle
self.sidebar_section_title = nav_title
self.sidebar_status_card = status_card
```

Replace the first row creation inside `_create_top_status_bar()` with this widget-backed command row:

```python
self.topbar_command_row = QWidget(bar)
self.topbar_command_row.setObjectName("topbar_command_row")
command_layout = QHBoxLayout(self.topbar_command_row)
command_layout.setContentsMargins(0, 0, 0, 0)
command_layout.setSpacing(12)

self.topbar_breadcrumb = QLabel("首页 / 运营总览")
self.topbar_breadcrumb.setObjectName("topbar_breadcrumb")
command_layout.addWidget(self.topbar_breadcrumb)
command_layout.addStretch()

self.topbar_search = QLineEdit()
self.topbar_search.setObjectName("topbar_search")
self.topbar_search.setPlaceholderText(ShellText.TOPBAR_SEARCH_PLACEHOLDER)
self.topbar_search.returnPressed.connect(self.handle_topbar_search)
self.topbar_search.setClearButtonEnabled(True)
self.topbar_search.setMinimumWidth(120)
self.topbar_search.setMaximumWidth(280)
command_layout.addWidget(self.topbar_search)

self.btn_search = self._create_top_action_button(ShellText.SEARCH, self.focus_topbar_search, accent=True)
self.btn_notice = self._create_top_action_button(ShellText.HISTORY, lambda: self.switch_to_page("history"))
self.btn_setting = self._create_top_action_button(
    ShellText.SYSTEM_SETTINGS, lambda: self.switch_to_page("settings")
)
self.topbar_action_buttons = [self.btn_search, self.btn_notice, self.btn_setting]
command_layout.addWidget(self.btn_search)
command_layout.addWidget(self.btn_notice)
command_layout.addWidget(self.btn_setting)

self.topbar_user = QLabel(ShellText.TOPBAR_USER_BADGE)
self.topbar_user.setObjectName("topbar_user")
command_layout.addWidget(self.topbar_user)
root_layout.addWidget(self.topbar_command_row)
```

```python
def resizeEvent(self, event):
    self._apply_responsive_shell_layout()
    super().resizeEvent(event)

def _apply_responsive_shell_layout(self) -> None:
    compact = self.width() <= 1366
    if self.sidebar is not None:
        self.sidebar_compact = compact
        self.sidebar.setProperty("compact", compact)
        self.sidebar.setMaximumWidth(self.sidebar_compact_width if compact else 320)
        if hasattr(self, "sidebar_logo_subtitle"):
            self.sidebar_logo_subtitle.setVisible(not compact)
        if hasattr(self, "sidebar_section_title"):
            self.sidebar_section_title.setVisible(not compact)
        if self.sidebar_status_card is not None:
            self.sidebar_status_card.setVisible(not compact)

    if hasattr(self, "topbar_search") and self.topbar_search is not None:
        self.topbar_search.setMaximumWidth(180 if compact else 280)

    if self.main_splitter is not None:
        sidebar_width = self.sidebar_compact_width if compact else self.sidebar_expanded_width
        content_width = max(960, self.width() - sidebar_width)
        self.main_splitter.setSizes([sidebar_width, content_width])
```

- [ ] **Step 5: Scope the stylesheet to the new scaffold and remove legacy Apple selectors**

```css
QFrame[ui="win11-primary-action-bar"] {
    background-color: rgba(255, 255, 255, 0.96);
    border: 1px solid #d8e3f1;
    border-radius: 18px;
}

QScrollArea[ui="win11-page-scroll"],
QScrollArea[ui="win11-page-scroll"] > QWidget > QWidget {
    background: transparent;
}

QFrame#sidebar[ui="win11-nav-panel"][compact="true"] {
    border-right: 1px solid #d7e1ef;
}

QFrame#sidebar[ui="win11-nav-panel"][compact="true"] QTreeWidget#nav-tree::item {
    padding-left: 8px;
    padding-right: 8px;
}

QWidget#topbar_command_row {
    background: transparent;
}
```

Run this cleanup while editing `assets/styles.css`:

```text
Delete every selector block whose selector contains:
- QWidget[ui="apple-
- QFrame[ui="apple-
- QLabel[td="apple-
- *[td="apple-
- QTextEdit[class="apple-
```

- [ ] **Step 6: Run the focused shell/scaffold tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ResponsiveShellSmokeTests -q`

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py assets/styles.css
git commit -m "feat: add responsive win11 shell and scaffold primitives"
```

### Task 2: Rebuild Dashboard And Sync As Responsive Workbench Pages

**Files:**
- Modify: `src/gui/pages/dashboard_page.py`
- Modify: `src/gui/pages/sync_page.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing dashboard and sync responsive tests**

```python
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

        self.assertTrue(page.test_conn_btn.isVisible())
        self.assertTrue(page.start_sync_btn.isVisible())
        self.assertEqual(page.workspace_splitter.orientation(), Qt.Orientation.Vertical)
        self.assertGreaterEqual(page.log_text.minimumHeight(), 180)
```

- [ ] **Step 2: Run the targeted dashboard and sync tests to confirm failure**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11DashboardAndSyncResponsiveTests -q`

Expected: `FAIL` because the dashboard does not expose compact splitters and sync only stacks below the current `< 1280` threshold.

- [ ] **Step 3: Refactor `DashboardPage` to use the shared primary action bar and adaptive splitters**

Add this field inside `DashboardPage.__init__` before the `super().__init__` call:

```python
self._responsive_splitters: list[tuple[QSplitter, list[int], list[int]]] = []
```

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.refresh_btn)
    self.set_content(self._create_scroll_content())
    self._sync_window_scope_ui()
    self._apply_workspace_layout()
```

At the end of `_build_hero()`, create the refresh action and keep only the metadata widget in the hero:

```python
self.refresh_btn = LoadingButton(ButtonText.REFRESH_DATA)
self.refresh_btn.setProperty("class", "primary")
self.refresh_btn.setFixedHeight(36)
self.refresh_btn.clicked.connect(self.refresh_dashboard)
self.add_hero_widget(meta_widget)
```

Inside `_create_scroll_content()`, swap in the shared scroll factory and register the three responsive splitters:

```python
scroll = self.create_scroll_container("dashboard_scroll")

self.middle_splitter = self._register_splitter(
    self._create_middle_row(),
    compact_sizes=[500, 320],
    wide_sizes=[860, 520],
)
self.rank_splitter = self._register_splitter(
    self._create_rank_row(),
    compact_sizes=[320, 320],
    wide_sizes=[700, 700],
)
self.bottom_splitter = self._register_splitter(
    self._create_bottom_row(),
    compact_sizes=[320, 320],
    wide_sizes=[860, 520],
)
page_layout.addWidget(self.middle_splitter)
page_layout.addWidget(self.rank_splitter)
page_layout.addWidget(self.bottom_splitter)

def _register_splitter(self, splitter: QSplitter, *, compact_sizes: list[int], wide_sizes: list[int]) -> QSplitter:
    self._responsive_splitters.append((splitter, compact_sizes, wide_sizes))
    return splitter

def _apply_workspace_layout(self) -> None:
    compact = self.width() <= 1366
    for splitter, compact_sizes, wide_sizes in self._responsive_splitters:
        splitter.setOrientation(Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal)
        splitter.setSizes(compact_sizes if compact else wide_sizes)

def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
    self._apply_workspace_layout()
    super().resizeEvent(event)
```

- [ ] **Step 4: Refactor `SyncPage` to move actions into the shared action bar and stack at `1366x768`**

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.test_conn_btn)
    self.add_primary_action(self.start_sync_btn)
    self.set_content(self._create_workspace())
    self._apply_workspace_layout()
```

```python
def _build_hero(self) -> None:
    meta_widget = QWidget()
    meta_layout = QVBoxLayout(meta_widget)
    meta_layout.setContentsMargins(0, 0, 0, 0)
    meta_layout.setSpacing(6)
    meta_layout.addWidget(self.hero_status, 0, Qt.AlignmentFlag.AlignLeft)
    meta_layout.addWidget(self.hero_hint)

    self.start_sync_btn = LoadingButton(ButtonText.START_SYNC)
    self.start_sync_btn.setProperty("class", "primary")
    self.start_sync_btn.setFixedHeight(36)
    self.start_sync_btn.clicked.connect(self.start_sync)
    self.gui.start_sync_btn = self.start_sync_btn

    self.test_conn_btn = LoadingButton(ButtonText.TEST_CONNECTION)
    self.test_conn_btn.setProperty("class", "secondary")
    self.test_conn_btn.setFixedHeight(36)
    self.test_conn_btn.clicked.connect(self.test_connection)
    self.gui.test_conn_btn = self.test_conn_btn

    self.add_hero_widget(meta_widget)
```

```python
def _apply_workspace_layout(self) -> None:
    if not hasattr(self, "workspace_splitter") or self.workspace_splitter is None:
        return

    compact = self.width() <= 1366
    self.workspace_splitter.setOrientation(Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal)
    self.config_container.setMinimumWidth(0 if compact else 360)
    self.config_container.setMaximumWidth(16777215 if compact else 420)
    if hasattr(self, "execution_card"):
        self.execution_card.setMaximumHeight(320 if compact else 16777215)
    self.log_text.setMinimumHeight(180 if compact else 220)
    self.workspace_splitter.setSizes([330, 390] if compact else [540, 980])

def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
    self._apply_workspace_layout()
    super().resizeEvent(event)
```

- [ ] **Step 5: Add page-level styles for the dashboard and sync workbench**

```css
QWidget[ui="win11-page"] QFrame[ui="win11-primary-action-bar"] QPushButton[class="primary"],
QWidget[ui="win11-page"] QFrame[ui="win11-primary-action-bar"] QPushButton[class="secondary"] {
    min-width: 104px;
}

QWidget[ui="win11-page"] QSplitter[ui="win11-page-splitter"]::handle {
    background-color: #d5deea;
}

QWidget[ui="win11-page"] QTextEdit[class="win11-log"] {
    min-height: 180px;
}
```

- [ ] **Step 6: Run the targeted dashboard and sync tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11DashboardAndSyncResponsiveTests -q`

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py assets/styles.css
git commit -m "feat: redesign dashboard and sync workbench layout"
```

### Task 3: Rebuild Settings And Forms As Compact Configuration Pages

**Files:**
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing settings and forms responsive tests**

```python
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

        self.assertTrue(page.search_box.isVisible())
        self.assertTrue(page.btn_select_all.isVisible())
        self.assertTrue(page.btn_reset.isVisible())
        self.assertTrue(page.btn_save.isVisible())
        self.assertTrue(page.scroll.isVisible())
```

- [ ] **Step 2: Run the targeted settings/forms tests to confirm failure**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11SettingsAndFormsResponsiveTests -q`

Expected: `FAIL` because settings rows are still width-constrained and forms still places search and bulk controls inside the scroll body.

- [ ] **Step 3: Refactor `SettingsPage` into a compact configuration center**

```python
from PySide6.QtWidgets import QBoxLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget
```

Add this field inside `SettingsPage.__init__` before the `super().__init__` call:

```python
self._setting_rows: list[tuple[QFrame, QBoxLayout, QWidget]] = []
```

```python
def setup_ui(self) -> None:
    self._init_editors()
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_test)
    self.add_primary_action(self.btn_save)
    self.set_content(self._create_scroll_content())
    self._apply_responsive_rows()
```

Append these statements at the end of `_build_hero()` after the metadata labels are added:

```python
self.btn_test = LoadingButton(ButtonText.TEST_CONNECTION)
self.btn_test.setProperty("class", "secondary")
self.btn_test.setFixedHeight(36)
self.btn_test.clicked.connect(self.test_connections)

self.btn_save = LoadingButton(ButtonText.SAVE_SETTINGS)
self.btn_save.setProperty("class", "primary")
self.btn_save.setFixedHeight(36)
self.btn_save.clicked.connect(self.save_settings)
self.add_hero_widget(meta_widget)
```

```python
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
    layout.addWidget(editor, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    self._setting_rows.append((row, layout, editor))
    return row

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

def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
    self._apply_responsive_rows()
    super().resizeEvent(event)
```

- [ ] **Step 4: Refactor `FormConfigPage` into a list-first workbench**

```python
class FormConfigPage(Win11PageScaffold):
    def setup_ui(self) -> None:
        self._init_action_controls()
        self._build_hero()
        self._build_summary_strip()
        self.add_primary_action(self.search_box)
        self.add_primary_action(self.btn_select_all)
        self.add_primary_action(self.btn_reset)
        self.add_primary_action(self.btn_save)
        self.set_content(self._create_scroll_content())
        self._apply_action_sizing()
```

```python
def _init_action_controls(self) -> None:
    self.search_box = QLineEdit()
    self.search_box.setProperty("td", "win11-input")
    self.search_box.setPlaceholderText("按表单名称筛选")
    self.search_box.textChanged.connect(self.filter_cards)

    self.btn_select_all = QPushButton("全选")
    self.btn_select_all.setProperty("class", "secondary")
    self.btn_select_all.setFixedHeight(36)
    self.btn_select_all.clicked.connect(self.toggle_all)

    self.btn_reset = QPushButton("重置")
    self.btn_reset.setProperty("class", "secondary")
    self.btn_reset.setFixedHeight(36)
    self.btn_reset.clicked.connect(self.reset_selection)

    self.btn_save = QPushButton(ButtonText.SAVE_CONFIG)
    self.btn_save.setProperty("class", "primary")
    self.btn_save.setFixedHeight(36)
    self.btn_save.clicked.connect(self.save_config)
```

```python
def _create_scroll_content(self) -> QScrollArea:
    scroll = self.create_scroll_container("forms_scroll")
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    layout.addWidget(self._create_form_list_card(), 1)
    layout.addWidget(self._create_footer_card())
    scroll.setWidget(page)
    return scroll

def _apply_action_sizing(self) -> None:
    compact = self.width() <= 1366
    self.search_box.setMinimumWidth(180 if compact else 260)
    self.search_box.setMaximumWidth(260 if compact else 320)

def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
    self._apply_action_sizing()
    super().resizeEvent(event)
```

- [ ] **Step 5: Add compact configuration-page styles**

```css
QWidget[ui="win11-page"] QFrame[ui="win11-setting-row"] {
    border-bottom: 1px solid #e8eef6;
}

QWidget[ui="win11-page"] QFrame[ui="win11-setting-row"][selected="true"] {
    background-color: #f1f7ff;
    border: 1px solid #d8e7fb;
    border-radius: 16px;
}

QWidget[ui="win11-page"] QLineEdit[td="win11-input"] {
    min-height: 22px;
}
```

- [ ] **Step 6: Run the targeted settings/forms tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11SettingsAndFormsResponsiveTests -q`

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py assets/styles.css
git commit -m "feat: redesign settings and forms workbench layout"
```

### Task 4: Rebuild Schedule And History As Dense Desktop Workbenches

**Files:**
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `assets/styles.css`
- Test: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Write the failing schedule and history responsive tests**

```python
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

        self.assertEqual(page.filter_grid.property("compact"), True)
        self.assertTrue(page.btn_query.isVisible())
        self.assertTrue(page.btn_prev.isVisible())
        self.assertTrue(page.btn_next.isVisible())
```

- [ ] **Step 2: Run the targeted schedule/history tests to confirm failure**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ScheduleAndHistoryResponsiveTests -q`

Expected: `FAIL` because schedule still compacts below `1280` and history does not expose a responsive filter grid.

- [ ] **Step 3: Refactor `SchedulePage` to use the shared action bar and compact workspace threshold**

```python
def setup_ui(self) -> None:
    self._init_editors()
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_toggle_task)
    self.add_primary_action(self.btn_save)
    self.set_content(self._create_workspace())
    self._apply_workspace_layout()
```

Append these statements at the end of `SchedulePage._build_hero()` after the metadata labels are added:

```python
self.btn_toggle_task = LoadingButton(ButtonText.START_TASK)
self.btn_toggle_task.setProperty("class", "primary")
self.btn_toggle_task.setFixedHeight(36)
self.btn_toggle_task.clicked.connect(self.on_toggle_task)

self.btn_save = LoadingButton(ButtonText.SAVE_SETTINGS)
self.btn_save.setProperty("class", "secondary")
self.btn_save.setEnabled(False)
self.btn_save.setFixedHeight(36)
self.btn_save.clicked.connect(self.save_config)
self.add_hero_widget(meta_widget)
```

```python
def _apply_workspace_layout(self) -> None:
    if not hasattr(self, "workspace_splitter") or self.workspace_splitter is None:
        return

    compact = self.width() <= 1366
    self.workspace_splitter.setOrientation(Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal)
    self.left_panel.setMinimumWidth(0 if compact else 420)
    self.left_panel.setMaximumWidth(16777215 if compact else 560)
    self.log_text.setMinimumHeight(180 if compact else 220)
    status_card_min = max(220, self.status_card.minimumHeight())
    self.workspace_splitter.setSizes([status_card_min + 160, 300] if compact else [560, 920])

def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
    self._apply_workspace_layout()
    super().resizeEvent(event)
```

- [ ] **Step 4: Refactor `HistoryPage` into a filter-grid layout with always-visible actions and pagination**

```python
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
```

```python
def setup_ui(self) -> None:
    self._init_filters()
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_query)
    self.add_primary_action(self.btn_export)
    self.set_content(self._create_content())
    self._apply_filter_layout()
```

```python
def _init_filters(self) -> None:
    self.search_box = QLineEdit()
    self.search_box.setPlaceholderText("按表单名称或消息内容搜索")
    self.search_box.setProperty("td", "win11-input")
    self.search_box.returnPressed.connect(lambda: self.load_history(1))

    self.combo_time_range = QComboBox()
    self.combo_time_range.setProperty("td", "win11-input")
    self.combo_time_range.addItem("今天", 0)
    self.combo_time_range.addItem("近 7 天", 7)
    self.combo_time_range.addItem("近 30 天", 30)

    self.combo_status = QComboBox()
    self.combo_status.setProperty("td", "win11-input")
    self.combo_status.addItem("全部状态", None)
    self.combo_status.addItem("成功", "success")
    self.combo_status.addItem("部分成功", "partial")
    self.combo_status.addItem("失败", "failed")

    self.combo_type = QComboBox()
    self.combo_type.setProperty("td", "win11-input")
    self.combo_type.addItem("全部类型", None)
    self.combo_type.addItem("增量", "incremental")
    self.combo_type.addItem("全量", "full")
    self.combo_type.addItem("完整", "complete")

    self.btn_query = QPushButton(ButtonText.QUERY)
    self.btn_query.setProperty("class", "primary")
    self.btn_query.setFixedHeight(36)
    self.btn_query.clicked.connect(lambda: self.load_history(1))
```

Append these statements at the end of `HistoryPage._build_hero()` after the metadata labels are added:

```python
self.btn_export = QPushButton(ButtonText.EXPORT)
self.btn_export.setProperty("class", "secondary")
self.btn_export.setFixedHeight(36)
self.btn_export.clicked.connect(self.export_data)
self.add_hero_widget(meta_widget)
```

```python
def _create_filter_card(self) -> Win11SectionCard:
    card = Win11SectionCard(
        "筛选条件",
        "可按关键字、时间范围、状态与同步类型筛选历史记录后再查看或导出。",
    )

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

def _apply_filter_layout(self) -> None:
    compact = self.width() <= 1366
    self.filter_grid.setProperty("compact", compact)
    while self.filter_grid_layout.count():
        item = self.filter_grid_layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)

    positions = [(0, 0), (0, 1), (1, 0), (1, 1)] if compact else [(0, 0), (0, 1), (0, 2), (0, 3)]
    for (row, col), widget in zip(positions, self.filter_fields):
        self.filter_grid_layout.addWidget(widget, row, col)

def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
    self._apply_filter_layout()
    super().resizeEvent(event)
```

- [ ] **Step 5: Add dense-page styles for schedule logs and history filter grids**

```css
QWidget[ui="win11-page"] QWidget[compact="true"] {
    background: transparent;
}

QWidget[ui="win11-page"] QFrame[ui="win11-pagination-card"] {
    background-color: rgba(255, 255, 255, 0.96);
    border: 1px solid #dbe5f2;
    border-radius: 18px;
}

QWidget[ui="win11-page"] QWidget[compact="true"] QLabel[ui="win11-row-note"] {
    line-height: 1.35;
}
```

- [ ] **Step 6: Run the targeted schedule/history tests again**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ScheduleAndHistoryResponsiveTests -q`

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py assets/styles.css
git commit -m "feat: redesign schedule and history workbench layout"
```

### Task 5: Run Full Verification And Finalize The Branch

**Files:**
- Review: `src/gui/components/page_shell.py`
- Review: `src/gui/kingdee_sync_gui.py`
- Review: `src/gui/pages/dashboard_page.py`
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

- [ ] **Step 2: Run a Python compile check over the GUI surface**

Run: `python -m compileall -q src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py src/gui/pages`

Expected: no output

- [ ] **Step 3: Validate the shell can instantiate offscreen at `1366x768`**

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

- [ ] **Step 4: Confirm the legacy Apple stylesheet system is gone**

Run: `rg -n "apple-" assets/styles.css src/gui`

Expected: no output

- [ ] **Step 5: Commit the final integrated redesign**

```bash
git add src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py src/gui/pages assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: deliver unified windows11 responsive workbench"
```
