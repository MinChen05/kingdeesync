# Windows 11 Responsive Desktop Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前桌面应用的 6 个页面统一重设计为 Windows 11 风格，并确保在 `1366×768` 下核心操作始终完整可见，次要信息通过折叠或局部滚动承载。

**Architecture:** 保持现有 Win11 shell 与业务逻辑不变，在共享页面骨架上统一 6 个页面的结构层级：`标题区 + 核心操作区 + 主内容区`。通过共享布局约束、页面级卡片组件、局部滚动和断点下分栏转纵向的方式，保证小屏幕下不再出现核心操作被截断或内容挤压到不可用的情况。

**Tech Stack:** Python 3.11, PySide6, shared Win11 page scaffold, Qt stylesheets, unittest smoke tests

---

## File Structure

- `src/gui/components/page_shell.py`
  Responsibility: 共享页面骨架、标题区动作槽位、通用分区卡片和页面级响应式容器。
- `src/gui/kingdee_sync_gui.py`
  Responsibility: 保持 shell 稳定，只在必要时暴露页面级响应式钩子，不做大改。
- `src/gui/pages/dashboard_page.py`
  Responsibility: 仪表盘总览、图表、异常列表、底部摘要卡的统一 Win11 响应式布局。
- `src/gui/pages/sync_page.py`
  Responsibility: 同步工作台的双栏/纵向切换、核心操作固定可见、日志区局部滚动。
- `src/gui/pages/settings_page.py`
  Responsibility: 设置页的主操作固定、表单字段分组、说明文字在小屏下换行不截断。
- `src/gui/pages/forms_page.py`
  Responsibility: 默认表单集筛选/列表/底部状态区统一布局，小屏下列表区优先保留可用高度。
- `src/gui/pages/schedule_page.py`
  Responsibility: 调度页状态卡、配置卡、日志区统一工作台结构，并在小屏下切换为纵向。
- `src/gui/pages/history_page.py`
  Responsibility: 历史筛选、表格、分页卡在小屏下保持“筛选可见、分页可点、表格局部滚动”。
- `assets/styles.css`
  Responsibility: 页面级 Win11 视觉系统、断点样式、卡片/说明/按钮/分页/日志区的统一外观。
- `tests/test_gui_windows11_shell.py`
  Responsibility: 响应式 smoke tests，验证 `1366×768` 下关键操作控件存在且可见。

---

### Task 1: 扩展共享页面骨架并建立 1366×768 响应式回归测试

**Files:**
- Modify: `src/gui/components/page_shell.py`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写会失败的 1366×768 响应式 smoke test**

```python
class Win11ResponsiveLayoutSmokeTests(QtAppTestCase):
    def test_sync_page_keeps_primary_actions_visible_at_1366x768(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["客户", "订单"]),
            patch(
                "src.gui.pages.sync_page.sync_service.get_sync_config",
                return_value={"default_forms": ["客户"], "sync_type": "incremental"},
            ),
        ):
            page = SyncPage(gui)

        self.addCleanup(cleanup_widget, page)
        page.resize(1366, 768)
        self._app.processEvents()

        self.assertTrue(page.start_sync_btn.isVisible())
        self.assertTrue(page.test_conn_btn.isVisible())
        self.assertFalse(page.start_sync_btn.geometry().isNull())
```

- [ ] **Step 2: 运行测试，确认当前实现先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ResponsiveLayoutSmokeTests -q`
Expected: FAIL，至少缺少专门的响应式断言支撑或共享布局钩子

- [ ] **Step 3: 在共享骨架中加入统一页面结构能力**

```python
class Win11PageScaffold(QWidget):
    def __init__(..., parent=None):
        ...
        self.primary_action_host = QWidget(self)
        self.primary_action_host.setObjectName("page_primary_actions")
        self.primary_action_host.setProperty("ui", "win11-primary-action-host")

        self.primary_action_layout = QHBoxLayout(self.primary_action_host)
        self.primary_action_layout.setContentsMargins(0, 0, 0, 0)
        self.primary_action_layout.setSpacing(10)
        ...
        root.addWidget(self.primary_action_host)
        root.addWidget(self.content_host, 1)

    def add_primary_action(self, widget: QWidget) -> None:
        self.primary_action_layout.addWidget(widget)
```

- [ ] **Step 4: 给骨架增加统一的小屏辅助容器**

```python
class Win11SectionCard(QFrame):
    def __init__(...):
        ...
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
```

```python
class Win11PageScaffold(QWidget):
    def create_scroll_content(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return scroll
```

- [ ] **Step 5: 运行测试并确认通过**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ResponsiveLayoutSmokeTests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/gui/components/page_shell.py tests/test_gui_windows11_shell.py
git commit -m "feat: add shared responsive page scaffold hooks"
```

### Task 2: 统一 Dashboard / Sync 的工作台结构并保证小屏核心操作可见

**Files:**
- Modify: `src/gui/pages/dashboard_page.py`
- Modify: `src/gui/pages/sync_page.py`
- Modify: `assets/styles.css`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写会失败的页面结构 smoke test**

```python
class Win11PageStructureTests(QtAppTestCase):
    def test_dashboard_and_sync_share_primary_action_pattern(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage
        from src.gui.pages.sync_page import SyncPage

        dashboard = DashboardPage(SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_a, **_k: None))
        sync = SyncPage(SimpleNamespace())

        self.addCleanup(cleanup_widget, dashboard)
        self.addCleanup(cleanup_widget, sync)

        self.assertIsNotNone(dashboard.findChild(QObject, "page_primary_actions"))
        self.assertIsNotNone(sync.findChild(QObject, "page_primary_actions"))
```

- [ ] **Step 2: 运行测试，确认当前实现先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11PageStructureTests -q`
Expected: FAIL

- [ ] **Step 3: 重排 Dashboard 结构**

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.refresh_btn)
    self.set_content(self._create_scroll_content())
```

```python
self.overview_card = Win11SectionCard(
    "每日概览",
    "优先展示成功率、失败队列与吞吐变化，帮助快速决策。"
)
```

- [ ] **Step 4: 重排 Sync 结构**

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.test_conn_btn)
    self.add_primary_action(self.start_sync_btn)
    self.set_content(self._create_workspace())
```

```python
def resizeEvent(self, event) -> None:
    if self.width() <= 1366:
        self.workspace_splitter.setOrientation(Qt.Orientation.Vertical)
        self.config_container.setMaximumWidth(16777215)
    else:
        self.workspace_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.config_container.setMaximumWidth(420)
    super().resizeEvent(event)
```

- [ ] **Step 5: 加入页面级 Win11 样式**

```css
QWidget[ui="win11-page"] QWidget#page_primary_actions[ui="win11-primary-action-host"] {
    background-color: rgba(255, 255, 255, 0.94);
    border: 1px solid #d8e2ef;
    border-radius: 14px;
    padding: 8px 12px;
}

QWidget[ui="win11-page"] QSplitter[ui="win11-page-splitter"]::handle {
    background-color: #dbe4f1;
}
```

- [ ] **Step 6: 跑通过测试**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11PageStructureTests tests.test_gui_windows11_shell.Win11ResponsiveLayoutSmokeTests -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: unify dashboard and sync responsive layout"
```

### Task 3: 统一 Settings / Forms 的配置工作流布局

**Files:**
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `assets/styles.css`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写配置页结构测试**

```python
class Win11ConfigPageStructureTests(QtAppTestCase):
    def test_settings_and_forms_keep_primary_actions_visible(self) -> None:
        from src.gui.pages.settings_page import SettingsPage
        from src.gui.pages.forms_page import FormConfigPage

        settings = SettingsPage(SimpleNamespace())
        forms = FormConfigPage(SimpleNamespace())
        self.addCleanup(cleanup_widget, settings)
        self.addCleanup(cleanup_widget, forms)

        settings.resize(1366, 768)
        forms.resize(1366, 768)
        self._app.processEvents()

        self.assertTrue(settings.btn_test.isVisible())
        self.assertTrue(settings.btn_save.isVisible())
        self.assertTrue(forms.btn_reset.isVisible())
        self.assertTrue(forms.btn_save.isVisible())
```

- [ ] **Step 2: 运行测试，确认当前实现先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ConfigPageStructureTests -q`
Expected: FAIL

- [ ] **Step 3: Settings 改成固定主操作 + 分组内容**

```python
def setup_ui(self) -> None:
    self._init_editors()
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_test)
    self.add_primary_action(self.btn_save)
    self.set_content(self._create_scroll_content())
```

- [ ] **Step 4: Forms 改成固定主操作 + 列表优先**

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_reset)
    self.add_primary_action(self.btn_save)
    self.set_content(self._create_scroll_content())
```

```python
def resizeEvent(self, event) -> None:
    self.search_box.setFixedWidth(240 if self.width() <= 1366 else 280)
    super().resizeEvent(event)
```

- [ ] **Step 5: 加入配置页统一样式**

```css
QWidget[ui="win11-page"] QFrame[ui="win11-setting-row"] {
    border-bottom: 1px solid #e7edf5;
}

QWidget[ui="win11-page"] QFrame[ui="win11-setting-row"][last="true"] {
    border-bottom: none;
}
```

- [ ] **Step 6: 跑通过测试**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11ConfigPageStructureTests -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/gui/pages/settings_page.py src/gui/pages/forms_page.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: unify settings and forms responsive layout"
```

### Task 4: 统一 Schedule / History 的信息密集页布局

**Files:**
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `assets/styles.css`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写信息密集页结构测试**

```python
class Win11DensePageLayoutTests(QtAppTestCase):
    def test_schedule_and_history_keep_core_controls_visible_at_1366x768(self) -> None:
        from src.gui.pages.schedule_page import SchedulePage
        from src.gui.pages.history_page import HistoryPage

        schedule = SchedulePage(SimpleNamespace())
        history = HistoryPage(SimpleNamespace())
        self.addCleanup(cleanup_widget, schedule)
        self.addCleanup(cleanup_widget, history)

        schedule.resize(1366, 768)
        history.resize(1366, 768)
        self._app.processEvents()

        self.assertTrue(schedule.btn_toggle_task.isVisible())
        self.assertTrue(history.btn_export.isVisible())
        self.assertTrue(history.btn_prev.isVisible())
        self.assertTrue(history.btn_next.isVisible())
```

- [ ] **Step 2: 运行测试，确认当前实现先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11DensePageLayoutTests -q`
Expected: FAIL

- [ ] **Step 3: 重排 Schedule 布局**

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_toggle_task)
    self.add_primary_action(self.btn_save)
    self.set_content(self._create_workspace())
```

```python
def resizeEvent(self, event) -> None:
    if self.width() <= 1366:
        self.workspace_splitter.setOrientation(Qt.Orientation.Vertical)
    else:
        self.workspace_splitter.setOrientation(Qt.Orientation.Horizontal)
    super().resizeEvent(event)
```

- [ ] **Step 4: 重排 History 布局**

```python
def setup_ui(self) -> None:
    self._build_hero()
    self._build_summary_strip()
    self.add_primary_action(self.btn_export)
    self.set_content(self._create_scroll_content())
```

```python
self.pagination_card.setProperty("ui", "win11-pagination-card")
```

- [ ] **Step 5: 加入密集页样式**

```css
QFrame[ui="win11-pagination-card"] {
    background-color: rgba(255, 255, 255, 0.94);
    border: 1px solid #d8e2ef;
    border-radius: 14px;
}
```

- [ ] **Step 6: 跑通过测试**

Run: `python -m unittest tests.test_gui_windows11_shell.Win11DensePageLayoutTests -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/gui/pages/schedule_page.py src/gui/pages/history_page.py assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: unify schedule and history responsive layout"
```

### Task 5: 收尾验证与 1366×768 适配验收

**Files:**
- Review: `src/gui/components/page_shell.py`
- Review: `src/gui/pages/*.py`
- Review: `src/gui/kingdee_sync_gui.py`
- Review: `assets/styles.css`
- Review: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 跑全量 smoke test**

Run: `python -m unittest -q tests.test_gui_windows11_shell`
Expected: PASS

- [ ] **Step 2: 跑编译检查**

Run: `python -m compileall -q src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py src/gui/pages`
Expected: no output

- [ ] **Step 3: 用 1366×768 离屏启动主窗口**

Run: `$env:QT_QPA_PLATFORM='offscreen'; @'
from PySide6.QtWidgets import QApplication
from src.gui.kingdee_sync_gui import KingdeeSyncGUI
app = QApplication.instance() or QApplication([])
window = KingdeeSyncGUI()
window.resize(1366, 768)
print(window.size().width(), window.size().height())
window.close()
window.deleteLater()
app.processEvents()
app.quit()
'@ | python -`
Expected: print `1366 768`

- [ ] **Step 4: 检查页面文件里是否仍残留明显英文 UI 文案**

Run: `rg -n "\"[A-Za-z][A-Za-z0-9 ,:()/%._+-]{2,}\"" src/gui/pages src/gui/kingdee_sync_gui.py`
Expected: 剩余结果仅限技术名词、代码注释、非用户可见字符串，不应再出现主界面按钮/标题/提示英文文案

- [ ] **Step 5: Commit**

```bash
git add src/gui/components/page_shell.py src/gui/kingdee_sync_gui.py src/gui/pages assets/styles.css tests/test_gui_windows11_shell.py
git commit -m "feat: deliver unified windows11 responsive page redesign"
```
