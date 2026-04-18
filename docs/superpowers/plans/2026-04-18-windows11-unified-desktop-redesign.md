# Windows 11 Unified Desktop Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Apple/macOS-like desktop UI language with a unified Windows 11-style interface across the main shell and every page in the PySide6 application.

**Architecture:** Introduce a reusable Windows 11 page scaffold and shared design tokens, then migrate each page onto the same hero / summary / content-section structure instead of continuing to hand-roll similar layouts with `apple-*` properties. The visual system should use Windows 11 cues: mica-like surfaces, soft acrylic layering, restrained blue accents, clearer command bars, Explorer-like content panels, and consistent page scaffolding across dashboard, sync, forms, schedule, history, and settings.

**Tech Stack:** Python 3.11, PySide6, Qt stylesheets, shared GUI components in `src/gui/components`, smoke tests with `unittest`

---

## File Map

- `tests/test_gui_windows11_shell.py`
  Responsibility: offscreen smoke tests proving the shared Windows 11 scaffold, main shell, and migrated pages instantiate with the expected structural markers.
- `src/gui/design_tokens.py`
  Responsibility: centralize Windows 11 palette, radii, and surface tokens instead of the current Apple-like token comments / naming.
- `src/gui/components/page_shell.py`
  Responsibility: define reusable Windows 11 page primitives shared by all pages, including summary cards, hero panels, section cards, and page scaffold layout helpers.
- `src/gui/components/__init__.py`
  Responsibility: export the new shared page-shell primitives.
- `src/gui/kingdee_sync_gui.py`
  Responsibility: migrate the application shell to Windows 11 naming and structure, including sidebar rail, command bar, content host, and title/top actions.
- `src/gui/pages/dashboard_page.py`
  Responsibility: migrate dashboard to the shared scaffold and Windows 11 control-center layout.
- `src/gui/pages/sync_page.py`
  Responsibility: migrate sync execution page to a Windows 11 workbench layout with left configuration column and right execution/log panes.
- `src/gui/pages/settings_page.py`
  Responsibility: migrate settings to the shared scaffold with Windows 11 cards, grouped sections, and footer action bar.
- `src/gui/pages/forms_page.py`
  Responsibility: migrate forms to the shared scaffold with Windows 11 list-management layout and unified section cards.
- `src/gui/pages/schedule_page.py`
  Responsibility: migrate schedule to the shared scaffold and Windows 11 automation workbench layout.
- `src/gui/pages/history_page.py`
  Responsibility: migrate history to the shared scaffold and Windows 11 records center layout.
- `assets/styles.css`
  Responsibility: become the final Windows 11 stylesheet, removing or superseding all `apple-*` / macOS-style selectors and the recent warm editorial override.

---

### Task 1: Create the reusable Windows 11 page scaffold and smoke test

**Files:**
- Create: `tests/test_gui_windows11_shell.py`
- Create: `src/gui/components/page_shell.py`
- Modify: `src/gui/components/__init__.py`
- Modify: `src/gui/design_tokens.py`

- [ ] **Step 1: Write the failing scaffold smoke test**

```python
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from src.gui.components.page_shell import Win11PageScaffold, Win11SummaryCard


class Win11PageShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_scaffold_builds_required_regions(self) -> None:
        page = Win11PageScaffold("测试页面", "验证统一页面骨架")
        hero = page.findChild(QLabel, "page_hero_title")
        self.assertIsNotNone(hero)
        self.assertEqual(page.property("ui"), "win11-page")

    def test_summary_card_uses_win11_markers(self) -> None:
        card = Win11SummaryCard("状态", "待命", "说明")
        self.assertEqual(card.property("ui"), "win11-summary-card")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.gui.components.page_shell'`

- [ ] **Step 3: Implement the shared scaffold and Windows 11 tokens**

```python
# src/gui/components/page_shell.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class Win11SummaryCard(QFrame):
    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("ui", "win11-summary-card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setProperty("td", "win11-summary-title")
        self.value_label = QLabel(value)
        self.value_label.setProperty("td", "win11-summary-value")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setProperty("td", "win11-summary-subtitle")
        self.subtitle_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)


class Win11PageScaffold(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setProperty("ui", "win11-page")
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 22, 30, 30)
        root.setSpacing(16)

        self.hero_card = QFrame()
        self.hero_card.setObjectName("page_hero_card")
        self.hero_card.setProperty("ui", "win11-hero-card")
        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(20, 18, 20, 18)

        text_wrap = QVBoxLayout()
        self.hero_eyebrow = QLabel("Workspace")
        self.hero_eyebrow.setProperty("td", "win11-eyebrow")
        self.hero_title = QLabel(title)
        self.hero_title.setObjectName("page_hero_title")
        self.hero_title.setProperty("td", "win11-hero-title")
        self.hero_subtitle = QLabel(subtitle)
        self.hero_subtitle.setProperty("td", "win11-hero-subtitle")
        self.hero_subtitle.setWordWrap(True)
        text_wrap.addWidget(self.hero_eyebrow)
        text_wrap.addWidget(self.hero_title)
        text_wrap.addWidget(self.hero_subtitle)
        hero_layout.addLayout(text_wrap, 1)

        self.summary_strip = QWidget()
        self.summary_strip.setObjectName("page_summary_strip")
        self.summary_strip.setProperty("ui", "win11-summary-strip")
        self.summary_layout = QHBoxLayout(self.summary_strip)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(12)

        self.content_host = QWidget()
        self.content_host.setObjectName("page_content_host")
        self.content_host.setProperty("ui", "win11-content-host")
        self.content_layout = QVBoxLayout(self.content_host)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)

        root.addWidget(self.hero_card)
        root.addWidget(self.summary_strip)
        root.addWidget(self.content_host, 1)
```

```python
# src/gui/design_tokens.py
class ColorTokens:
    ACCENT_700 = "#005A9E"
    ACCENT_600 = "#0F6CBD"
    ACCENT_500 = "#2B88D8"
    ACCENT_100 = "#DCEBFA"
    ACCENT_50 = "#F4F8FD"

    TEXT_PRIMARY = "#1B1B1B"
    TEXT_SECONDARY = "#444444"
    TEXT_MUTED = "#616161"
    SURFACE_BASE = "#FAFAFA"
    SURFACE_CARD = "#F7F9FC"
    SURFACE_ELEVATED = "#FFFFFF"
    BORDER_DEFAULT = "#D9E2EC"
    BORDER_STRONG = "#C7D2E0"
```

- [ ] **Step 4: Export the new shared scaffold**

```python
# src/gui/components/__init__.py
from src.gui.components.page_shell import Win11PageScaffold, Win11SummaryCard

__all__ = [
    "Win11PageScaffold",
    "Win11SummaryCard",
]
```

- [ ] **Step 5: Run the scaffold test again**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: PASS for `test_scaffold_builds_required_regions` and `test_summary_card_uses_win11_markers`

- [ ] **Step 6: Commit**

```bash
git add tests/test_gui_windows11_shell.py src/gui/components/page_shell.py src/gui/components/__init__.py src/gui/design_tokens.py
git commit -m "feat: add shared windows11 page scaffold"
```

### Task 2: Replace the application shell with Windows 11 structure and styling

**Files:**
- Modify: `tests/test_gui_windows11_shell.py`
- Modify: `src/gui/kingdee_sync_gui.py`
- Modify: `assets/styles.css`

- [ ] **Step 1: Extend the smoke test with main-shell structure expectations**

```python
from src.gui.kingdee_sync_gui import KingdeeSyncGUI

    def test_main_window_uses_win11_shell_regions(self) -> None:
        window = KingdeeSyncGUI()
        command_bar = window.findChild(type(window.title_bar), None)
        self.assertEqual(window.findChild(type(window.centralWidget()), "main_content_shell").property("ui"), "win11-shell")
        self.assertEqual(window.findChild(type(window.topbar_search), "top_status_bar").property("ui"), "win11-command-bar")
        window.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: FAIL because `main_content_shell` and `top_status_bar` do not yet expose `win11-*` properties

- [ ] **Step 3: Update the shell to use Windows 11 property names and command-bar language**

```python
# src/gui/kingdee_sync_gui.py
content_shell = QWidget()
content_shell.setObjectName("main_content_shell")
content_shell.setProperty("ui", "win11-shell")

bar = QFrame()
bar.setObjectName("top_status_bar")
bar.setProperty("ui", "win11-command-bar")

sidebar.setProperty("ui", "win11-nav-panel")
status_card.setProperty("ui", "win11-sidebar-status")
```

```python
self.btn_search = self._create_top_action_button("搜索", self.focus_topbar_search)
self.btn_notice = self._create_top_action_button("历史", lambda: self.switch_to_page("history"))
self.btn_setting = self._create_top_action_button("设置", lambda: self.switch_to_page("settings"))
self.topbar_user = QLabel("KD")
```

- [ ] **Step 4: Replace the stylesheet tail with the final Windows 11 system**

```css
QWidget[ui="win11-shell"] {
    background: transparent;
}

QFrame[ui="win11-command-bar"] {
    background-color: rgba(255, 255, 255, 0.72);
    border: 1px solid #d7e1ee;
    border-radius: 18px;
}

QFrame[ui="win11-nav-panel"] {
    background-color: rgba(246, 248, 252, 0.84);
    border-right: 1px solid #d8e2ef;
}

QPushButton[class="win11-primary"] {
    background-color: #0f6cbd;
    border: 1px solid #0f6cbd;
    color: #ffffff;
}

QPushButton[class="win11-secondary"] {
    background-color: rgba(255, 255, 255, 0.85);
    border: 1px solid #ccd7e5;
    color: #1b1b1b;
}
```

- [ ] **Step 5: Remove or supersede all Apple/macOS shell selectors**

```css
/* delete or rewrite selectors using:
   apple-settings-hero
   apple-sync-hero
   apple-summary-card
   apple-settings-card
   apple-settings-footer
*/
```

- [ ] **Step 6: Run the shell smoke test again**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: PASS including `test_main_window_uses_win11_shell_regions`

- [ ] **Step 7: Commit**

```bash
git add src/gui/kingdee_sync_gui.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: convert desktop shell to windows11 layout"
```

### Task 3: Migrate dashboard, sync, settings, and forms onto the shared Windows 11 scaffold

**Files:**
- Modify: `tests/test_gui_windows11_shell.py`
- Modify: `src/gui/pages/dashboard_page.py`
- Modify: `src/gui/pages/sync_page.py`
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `assets/styles.css`

- [ ] **Step 1: Extend the smoke test to assert page-level structure on the first four pages**

```python
    def test_primary_pages_use_win11_page_scaffold(self) -> None:
        window = KingdeeSyncGUI()
        for page_id in ("dashboard", "sync", "settings", "forms"):
            page = window.pages[page_id]
            self.assertEqual(page.property("ui"), "win11-page")
            self.assertIsNotNone(page.findChild(QFrame, "page_hero_card"))
            self.assertIsNotNone(page.findChild(QWidget, "page_summary_strip"))
        window.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: FAIL because those pages still use `apple-*` root markers and bespoke layouts

- [ ] **Step 3: Convert dashboard to the shared scaffold**

```python
# src/gui/pages/dashboard_page.py
from src.gui.components import Win11PageScaffold, Win11SummaryCard

class DashboardPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        super().__init__("运营总览", "Windows 11 风格的数据运营控制台首页。", parent)
        self.gui = parent_gui
        self.hero_eyebrow.setText("Control Center")

        self.card_count = Win11SummaryCard("今日任务数", "--", "同步任务概览")
        self.card_records = Win11SummaryCard("今日同步量", "--", "记录写入情况")
        self.card_rate = Win11SummaryCard("成功率", "--", "任务完成质量")
        self.card_status = Win11SummaryCard("运行状态", "--", "同步链路健康度")
```

- [ ] **Step 4: Convert sync to the shared scaffold and a unified workbench split**

```python
# src/gui/pages/sync_page.py
class SyncPage(Win11PageScaffold):
    def __init__(self, parent_gui):
        super().__init__("同步执行", "统一的 Windows 11 工作台，用于配置、执行和观察同步。")
        self.gui = parent_gui
        self.setProperty("ui", "win11-page")

        self.workspace_splitter = QSplitter(Qt.Horizontal)
        self.workspace_splitter.setProperty("ui", "win11-workspace")
        self.left_column = QFrame()
        self.left_column.setProperty("ui", "win11-section-card")
        self.right_column = QFrame()
        self.right_column.setProperty("ui", "win11-section-card")
```

- [ ] **Step 5: Convert settings and forms to the shared scaffold and consistent section cards**

```python
# src/gui/pages/settings_page.py / forms_page.py
class SettingsPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        super().__init__("系统设置", "统一的 Windows 11 配置页结构。", parent)
        self.gui = parent_gui

class FormConfigPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        super().__init__("表单配置", "统一的 Windows 11 列表管理页结构。", parent)
        self.gui = parent_gui
```

- [ ] **Step 6: Add the shared Windows 11 page-card selectors**

```css
QWidget[ui="win11-page"] {
    background: transparent;
}

QFrame[ui="win11-hero-card"] {
    background-color: rgba(255, 255, 255, 0.76);
    border: 1px solid #d8e2ef;
    border-radius: 24px;
}

QFrame[ui="win11-summary-card"],
QFrame[ui="win11-section-card"],
QFrame[ui="win11-footer-card"] {
    background-color: rgba(255, 255, 255, 0.88);
    border: 1px solid #dbe4ef;
    border-radius: 20px;
}
```

- [ ] **Step 7: Run the updated page smoke test**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: PASS including `test_primary_pages_use_win11_page_scaffold`

- [ ] **Step 8: Commit**

```bash
git add src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: migrate primary pages to windows11 scaffold"
```

### Task 4: Migrate schedule and history and unify table/log workbench structure

**Files:**
- Modify: `tests/test_gui_windows11_shell.py`
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `assets/styles.css`

- [ ] **Step 1: Extend the smoke test to cover the remaining pages**

```python
    def test_secondary_pages_use_win11_page_scaffold(self) -> None:
        window = KingdeeSyncGUI()
        for page_id in ("schedule", "history"):
            page = window.pages[page_id]
            self.assertEqual(page.property("ui"), "win11-page")
            self.assertIsNotNone(page.findChild(QFrame, "page_hero_card"))
        window.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: FAIL because `schedule` and `history` still expose Apple-style structure

- [ ] **Step 3: Convert schedule into the same Windows 11 workbench layout**

```python
# src/gui/pages/schedule_page.py
class SchedulePage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        super().__init__("调度管理", "统一的 Windows 11 自动化工作台。", parent)
        self.gui = parent_gui

        self.workspace_splitter = QSplitter(Qt.Horizontal)
        self.workspace_splitter.setProperty("ui", "win11-workspace")
        self.status_panel = QFrame()
        self.status_panel.setProperty("ui", "win11-section-card")
        self.log_panel = QFrame()
        self.log_panel.setProperty("ui", "win11-section-card")
```

- [ ] **Step 4: Convert history into the same records-center structure**

```python
# src/gui/pages/history_page.py
class HistoryPage(Win11PageScaffold):
    def __init__(self, parent_gui, parent=None):
        super().__init__("历史记录", "统一的 Windows 11 任务记录中心。", parent)
        self.gui = parent_gui

        self.table_panel = QFrame()
        self.table_panel.setProperty("ui", "win11-section-card")
        self.filter_panel = QFrame()
        self.filter_panel.setProperty("ui", "win11-section-card")
        self.footer_panel = QFrame()
        self.footer_panel.setProperty("ui", "win11-footer-card")
```

- [ ] **Step 5: Add shared table/log Windows 11 selectors**

```css
QTextEdit[class="win11-log"] {
    background-color: #0f1720;
    border: 1px solid #334155;
    border-radius: 16px;
    color: #e5eef8;
}

QTableWidget[td="win11-table"] {
    background-color: rgba(255, 255, 255, 0.94);
    border: 1px solid #dbe4ef;
    border-radius: 16px;
}
```

- [ ] **Step 6: Run the full page smoke test again**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: PASS including `test_secondary_pages_use_win11_page_scaffold`

- [ ] **Step 7: Commit**

```bash
git add src/gui/pages/schedule_page.py src/gui/pages/history_page.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: migrate schedule and history to windows11 scaffold"
```

### Task 5: Remove macOS remnants and verify the final Windows 11 system

**Files:**
- Review only: `src/gui/kingdee_sync_gui.py`
- Review only: `src/gui/pages/dashboard_page.py`
- Review only: `src/gui/pages/sync_page.py`
- Review only: `src/gui/pages/settings_page.py`
- Review only: `src/gui/pages/forms_page.py`
- Review only: `src/gui/pages/schedule_page.py`
- Review only: `src/gui/pages/history_page.py`
- Review only: `assets/styles.css`
- Review only: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: Verify that Apple/macOS naming has been removed from the UI layer**

Run: `rg -n "apple-" src\gui\kingdee_sync_gui.py src\gui\pages assets\styles.css`
Expected: no matches

- [ ] **Step 2: Verify that Windows 11 naming now exists across the UI layer**

Run: `rg -n "win11-" src\gui\kingdee_sync_gui.py src\gui\pages src\gui\components assets\styles.css`
Expected: matches across shell, scaffold, pages, and stylesheet

- [ ] **Step 3: Run the GUI smoke test suite**

Run: `python -m unittest tests.test_gui_windows11_shell -v`
Expected: all tests PASS

- [ ] **Step 4: Run syntax verification on the GUI modules**

Run: `python -m compileall src\gui\kingdee_sync_gui.py src\gui\pages src\gui\components`
Expected: compile output with no traceback

- [ ] **Step 5: Run lint on the touched GUI modules**

Run: `python -m ruff check src\gui\kingdee_sync_gui.py src\gui\pages src\gui\components tests\test_gui_windows11_shell.py`
Expected: no new lint errors

- [ ] **Step 6: Run an offscreen application bootstrap smoke check**

Run: `$env:QT_QPA_PLATFORM='offscreen'; @'
from PySide6.QtWidgets import QApplication
from src.gui.kingdee_sync_gui import KingdeeSyncGUI
app = QApplication.instance() or QApplication([])
window = KingdeeSyncGUI()
print(window.windowTitle())
window.close()
app.quit()
'@ | python -`
Expected: prints the window title and exits without traceback

- [ ] **Step 7: Commit**

```bash
git add assets/styles.css src/gui/kingdee_sync_gui.py src/gui/pages src/gui/components src/gui/design_tokens.py tests/test_gui_windows11_shell.py docs/superpowers/plans/2026-04-18-windows11-unified-desktop-redesign.md
git commit -m "feat: deliver unified windows11 desktop redesign"
```

## Self-Review

**Spec coverage:** Covered the shell, shared scaffold, tokens, stylesheet, every page (`dashboard`, `sync`, `settings`, `forms`, `schedule`, `history`), and explicit verification for removing `apple-*` / macOS remnants. No gaps found relative to the user request.

**Placeholder scan:** No `TODO`, `TBD`, “similar to task N”, or vague “add validation” style steps remain. Each task has concrete files, concrete commands, and concrete code targets.

**Type consistency:** The plan uses one consistent naming system throughout: `Win11PageScaffold`, `Win11SummaryCard`, `win11-page`, `win11-hero-card`, `win11-summary-card`, `win11-section-card`, `win11-footer-card`, and `win11-command-bar`.
