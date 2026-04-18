# 简体中文界面文案统一改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 Win11 桌面应用中面向用户可见的英文界面文案统一改为简体中文，并覆盖页面、提示框、状态消息与日志反馈。

**Architecture:** 采用“共享文案集中 + 页面专属文案就地中文化”的混合方案。共享按钮、加载态、反馈消息优先收敛到 `src/gui/ui_text.py`，页面自己的标题、说明、状态提示与日志消息保留在页面文件中逐页翻译，从而避免把本次任务膨胀成完整国际化框架改造。

**Tech Stack:** Python 3.11, PySide6, unittest, Qt offscreen smoke tests

---

## File Structure

### Shared copy layer

- `src/gui/ui_text.py`
  Responsibility: shared button text, loading text, shell text, common feedback messages, reusable Chinese copy constants.

### Shell

- `src/gui/kingdee_sync_gui.py`
  Responsibility: top bar, navigation, shell status text, search placeholder, menu copy, shell badges.

### Pages

- `src/gui/pages/dashboard_page.py`
  Responsibility: 仪表盘标题、摘要卡、副标题、状态说明、趋势/失败列表提示。
- `src/gui/pages/sync_page.py`
  Responsibility: 同步工作台标题、按钮、配置说明、运行状态、日志消息、错误反馈。
- `src/gui/pages/settings_page.py`
  Responsibility: 系统设置标题、说明、字段标签、保存/测试反馈。
- `src/gui/pages/forms_page.py`
  Responsibility: 默认同步表单配置页标题、筛选说明、保存/重置/批量操作提示。
- `src/gui/pages/schedule_page.py`
  Responsibility: 调度页标题、调度状态、预设说明、日志与操作反馈。
- `src/gui/pages/history_page.py`
  Responsibility: 历史页标题、筛选说明、分页、导出反馈。

### Verification

- `tests/test_gui_windows11_shell.py`
  Responsibility: shell 和 6 个页面的中文关键文案 smoke test、中文化回归保护。

---

### Task 1: 统一共享文案与主壳层中文化

**Files:**
- Modify: `src/gui/ui_text.py`
- Modify: `src/gui/kingdee_sync_gui.py`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写主壳层中文文案回归测试**

```python
class ZhCnShellCopyTests(QtAppTestCase):
    def test_shell_copy_is_simplified_chinese(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        self.assertEqual(window.btn_search.text(), "搜索")
        self.assertEqual(window.btn_notice.text(), "历史记录")
        self.assertEqual(window.btn_setting.text(), "系统设置")
        self.assertEqual(window.topbar_user.text(), "金")
        self.assertEqual(window.topbar_search.placeholderText(), "搜索页面、功能或关键字")
```

- [ ] **Step 2: 运行测试，确认当前实现先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnShellCopyTests -q`
Expected: FAIL，至少在 `topbar_user` 或按钮文本上与当前英文/缩写文案不一致

- [ ] **Step 3: 在共享文案层新增壳层中文常量**

```python
class ShellText:
    SEARCH = "搜索"
    HISTORY = "历史记录"
    SETTINGS = "系统设置"
    SEARCH_PLACEHOLDER = "搜索页面、功能或关键字"
    USER_BADGE = "金"
```

- [ ] **Step 4: 在主壳层改用共享中文常量并适配按钮宽度**

```python
from src.gui.ui_text import ShellText

self.topbar_search.setPlaceholderText(ShellText.SEARCH_PLACEHOLDER)
self.btn_search = self._create_top_action_button(ShellText.SEARCH, self.focus_topbar_search, accent=True)
self.btn_notice = self._create_top_action_button(ShellText.HISTORY, lambda: self.switch_to_page("history"))
self.btn_setting = self._create_top_action_button(ShellText.SETTINGS, lambda: self.switch_to_page("settings"))
self.topbar_user = QLabel(ShellText.USER_BADGE)
```

```python
def _create_top_action_button(self, text, callback, accent=False):
    button = QPushButton(text)
    button.setObjectName("topbar_action_btn")
    button.setProperty("ui", "win11-command-button")
    button.setProperty("accent", accent)
    button.setFixedHeight(34)
    button.setMinimumWidth(84)
    button.clicked.connect(callback)
    return button
```

- [ ] **Step 5: 运行测试并确认通过**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnShellCopyTests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/gui/ui_text.py src/gui/kingdee_sync_gui.py tests/test_gui_windows11_shell.py
git commit -m "feat: localize shell copy to zh-cn"
```

### Task 2: 仪表盘与同步页中文化

**Files:**
- Modify: `src/gui/pages/dashboard_page.py`
- Modify: `src/gui/pages/sync_page.py`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写 dashboard / sync 关键中文文案回归测试**

```python
class ZhCnPrimaryPageCopyTests(QtAppTestCase):
    def test_dashboard_page_uses_chinese_copy(self) -> None:
        from src.gui.pages.dashboard_page import DashboardPage

        gui = SimpleNamespace(sync_running=False, pages={}, switch_to_page=lambda *_args, **_kwargs: None)
        with patch("src.gui.pages.dashboard_page.QTimer.singleShot", lambda *_args, **_kwargs: None):
            page = DashboardPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.hero_title.text(), "运营总览")
        self.assertEqual(page.refresh_btn.text(), "刷新数据")
        self.assertEqual(page.card_count.title_label.text(), "今日任务数")

    def test_sync_page_uses_chinese_copy(self) -> None:
        from src.gui.pages.sync_page import SyncPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.sync_page.sync_service.get_available_forms", return_value=["客户", "订单"]),
            patch("src.gui.pages.sync_page.sync_service.get_sync_config", return_value={"default_forms": ["客户"], "sync_type": "incremental"}),
        ):
            page = SyncPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.hero_title.text(), "同步执行")
        self.assertEqual(page.start_sync_btn.text(), "开始同步")
        self.assertEqual(page.test_conn_btn.text(), "测试连接")
```

- [ ] **Step 2: 运行测试，确认当前文案先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnPrimaryPageCopyTests -q`
Expected: FAIL，`DashboardPage` 与 `SyncPage` 当前仍返回英文标题或按钮文案

- [ ] **Step 3: 翻译 dashboard 页面的标题、摘要卡、状态与说明文案**

```python
super().__init__(
    title="运营总览",
    eyebrow="仪表盘",
    subtitle="查看同步总量、成功率、失败任务与趋势变化。",
    parent=parent,
)

self.card_count = DashboardSummaryCard("今日任务数", "--", "今日执行的同步任务数。")
self.card_records = DashboardSummaryCard("今日同步量", "--", "今日插入或更新的记录总数。")
self.card_rate = DashboardSummaryCard("成功率", "--", "今日同步任务完成质量。")
self.card_status = DashboardSummaryCard("运行状态", "--", "当前同步链路整体状态。")

self.refresh_btn = LoadingButton(ButtonText.REFRESH_DATA)
```

```python
if is_running:
    status_text = "运行中"
    risk_text = "健康提示：当前同步任务正在运行，请关注实时日志与失败队列。"
elif sync_count == 0:
    status_text = "空闲"
    risk_text = "健康提示：今日尚未执行同步任务。"
elif today_fail > 0 or success_rate < 95.0:
    status_text = "需关注"
    risk_text = f"健康提示：今日有 {today_fail} 个失败或部分完成的任务需要处理。"
else:
    status_text = "稳定"
    risk_text = "健康提示：当前同步链路运行稳定。"
```

- [ ] **Step 4: 翻译 sync 页面的标题、按钮、配置说明、日志与反馈消息**

```python
super().__init__(
    title="同步执行",
    eyebrow="同步",
    subtitle="从统一工作台选择范围、测试连接并执行同步任务。",
    parent=parent,
)

self.start_sync_btn = LoadingButton(ButtonText.START_SYNC)
self.test_conn_btn = LoadingButton(ButtonText.TEST_CONNECTION)
self.ops_strip = QLabel("流程：选择范围 -> 测试连接 -> 开始同步")
self.summary_mode = SyncOverviewCard("同步模式", "--", "增量同步适合日常运行。")
self.summary_target = SyncOverviewCard("同步对象", "--", "全部表单、单个表单或保存的默认集合。")
self.summary_progress = SyncOverviewCard("执行进度", "0%", "任务尚未启动。")
self.summary_result = SyncOverviewCard("最近结果", "--", "插入与更新结果将在任务完成后汇总。")
```

```python
UiFeedback.warning(self, "任务已在运行", "请等待当前同步完成后再启动新的任务。")
UiFeedback.info(self, "未配置默认表单", "请先在表单页配置默认同步集合。")
self.append_log("开始执行同步任务。", "INFO")
self.append_log(f"同步对象：{form_selection}", "INFO")
self.append_log(f"同步模式：{sync_mode_text}", "INFO")
```

- [ ] **Step 5: 运行测试并确认通过**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnPrimaryPageCopyTests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py tests/test_gui_windows11_shell.py
git commit -m "feat: localize dashboard and sync copy to zh-cn"
```

### Task 3: 系统设置与表单配置页中文化

**Files:**
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写 settings / forms 中文文案回归测试**

```python
class ZhCnSettingsFormsCopyTests(QtAppTestCase):
    def test_settings_page_uses_chinese_copy(self) -> None:
        from src.gui.pages.settings_page import SettingsPage

        gui = SimpleNamespace()
        with patch("src.gui.pages.settings_page.settings_service.get_settings_snapshot", return_value={"kingdee": {}, "database": {}}):
            page = SettingsPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.hero_title.text(), "系统设置")
        self.assertEqual(page.btn_test.text(), "测试连接")
        self.assertEqual(page.btn_save.text(), "保存设置")

    def test_forms_page_uses_chinese_copy(self) -> None:
        from src.gui.pages.forms_page import FormConfigPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.forms_page.config_manager.get_table_mapping", return_value={"客户": "t_customer"}),
            patch("src.gui.pages.forms_page.config_manager.get_sync_config", return_value={"default_forms": ["客户"]}),
        ):
            page = FormConfigPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.hero_title.text(), "默认表单集")
        self.assertEqual(page.btn_reset.text(), "重置")
        self.assertEqual(page.btn_select_all.text(), "全选")
```

- [ ] **Step 2: 运行测试，确认当前文案先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnSettingsFormsCopyTests -q`
Expected: FAIL

- [ ] **Step 3: 翻译 settings 页面的标题、字段说明与反馈消息**

```python
super().__init__(
    title="系统设置",
    eyebrow="设置",
    subtitle="统一维护 Kingdee 与 SQL Server 连接配置。",
    parent=parent,
)

self.hero_badge = QLabel("连接设置")
self.hero_source = QLabel("配置来源：加载中...")
self.btn_test = LoadingButton(ButtonText.TEST_CONNECTION)
self.btn_save = LoadingButton(ButtonText.SAVE_SETTINGS)
```

```python
UiFeedback.success(self, "保存成功", "设置已成功保存。")
UiFeedback.error(self, "保存失败", f"保存设置失败：\n{exc}")
UiFeedback.info(self, "连接测试结果", message)
UiFeedback.error(self, "测试失败", f"测试连接失败：\n{exc}")
```

- [ ] **Step 4: 翻译 forms 页面的标题、筛选说明与保存/重置提示**

```python
super().__init__(
    title="默认表单集",
    eyebrow="表单",
    subtitle="管理保存的默认同步范围，供同步页直接复用。",
    parent=parent,
)

self.hero_badge = QLabel("默认同步集")
self.hero_status = QLabel("选择在使用默认同步范围时预先勾选的表单。")
self.btn_reset = QPushButton("重置")
self.btn_select_all = QPushButton("全选")
self.search_box.setPlaceholderText("按表单名称筛选")
self.status_lbl = QLabel("已选择 0 / 0")
```

```python
UiFeedback.info(self, "已恢复", "已恢复到最近一次保存的默认同步集合。")
UiFeedback.success(self, "保存成功", "默认表单配置已成功保存。")
UiFeedback.error(self, "保存失败", f"保存默认表单配置失败：\n{exc}")
```

- [ ] **Step 5: 运行测试并确认通过**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnSettingsFormsCopyTests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/gui/pages/settings_page.py src/gui/pages/forms_page.py tests/test_gui_windows11_shell.py
git commit -m "feat: localize settings and forms copy to zh-cn"
```

### Task 4: 调度页与历史页中文化

**Files:**
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `tests/test_gui_windows11_shell.py`

- [ ] **Step 1: 写 schedule / history 中文文案回归测试**

```python
class ZhCnScheduleHistoryCopyTests(QtAppTestCase):
    def test_schedule_page_uses_chinese_copy(self) -> None:
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

        self.assertEqual(page.hero_title.text(), "调度管理")
        self.assertEqual(page.btn_toggle_task.text(), "启动任务")

    def test_history_page_uses_chinese_copy(self) -> None:
        from src.gui.pages.history_page import HistoryPage

        gui = SimpleNamespace()
        with (
            patch("src.gui.pages.history_page.history_manager.get_history", return_value=([], 0)),
            patch("src.gui.pages.history_page.history_manager.get_stats", return_value={"today_success_rate": "0%", "avg_duration": "0秒", "top_failures": []}),
        ):
            page = HistoryPage(gui)
        self.addCleanup(cleanup_widget, page)

        self.assertEqual(page.hero_title.text(), "历史记录")
        self.assertEqual(page.btn_export.text(), "导出")
        self.assertEqual(page.btn_prev.text(), "上一页")
        self.assertEqual(page.btn_next.text(), "下一页")
```

- [ ] **Step 2: 运行测试，确认当前文案先失败**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnScheduleHistoryCopyTests -q`
Expected: FAIL

- [ ] **Step 3: 翻译 schedule 页面的标题、状态、预设与日志反馈**

```python
super().__init__(
    title="调度管理",
    eyebrow="调度",
    subtitle="维护自动调度策略、运行状态与调度日志。",
    parent=parent,
)

self.status_badge = QLabel("空闲")
self.quick_info = QLabel("调度器当前空闲，可保存新的调度策略或直接启动任务。")
self.btn_toggle_task = LoadingButton(ButtonText.START_TASK)
self.btn_save = LoadingButton(ButtonText.SAVE_CONFIG)
```

```python
UiFeedback.success(self, "保存成功", "调度配置已成功保存。")
UiFeedback.error(self, "保存失败", f"保存调度配置失败：\n{exc}")
UiFeedback.error(self, "启动失败", f"启动调度任务失败：\n{exc}")
UiFeedback.error(self, "停止失败", f"停止调度任务失败：\n{exc}")
self.append_log("调度任务已启动。", "INFO")
```

- [ ] **Step 4: 翻译 history 页面的标题、筛选、分页与导出反馈**

```python
super().__init__(
    title="历史记录",
    eyebrow="历史",
    subtitle="查看历史同步任务、筛选记录并导出当前结果。",
    parent=parent,
)

self.hero_badge = QLabel("历史查询")
self.summary_hint = QLabel("当前筛选条件匹配 0 条记录。")
self.btn_export = QPushButton(ButtonText.EXPORT)
self.search_box.setPlaceholderText("按表单名称或消息搜索")
self.btn_prev = QPushButton("上一页")
self.btn_next = QPushButton("下一页")
```

```python
UiFeedback.info(self, "暂无可导出内容", "当前视图中没有可导出的历史记录。")
UiFeedback.success(self, "导出成功", "历史记录已复制到剪贴板。")
UiFeedback.error(self, "导出失败", f"导出历史记录失败：\n{exc}")
```

- [ ] **Step 5: 运行测试并确认通过**

Run: `python -m unittest tests.test_gui_windows11_shell.ZhCnScheduleHistoryCopyTests -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/gui/pages/schedule_page.py src/gui/pages/history_page.py tests/test_gui_windows11_shell.py
git commit -m "feat: localize schedule and history copy to zh-cn"
```

### Task 5: 收尾检查与中文化回归验证

**Files:**
- Modify: `tests/test_gui_windows11_shell.py`
- Review: `src/gui/kingdee_sync_gui.py`
- Review: `src/gui/pages/*.py`
- Review: `src/gui/ui_text.py`

- [ ] **Step 1: 为关键中文化路径补充总体验收测试**

```python
class ZhCnRegressionTests(QtAppTestCase):
    def test_shell_and_pages_expose_key_chinese_copy(self) -> None:
        from src.gui.kingdee_sync_gui import KingdeeSyncGUI

        window = KingdeeSyncGUI()
        self.addCleanup(cleanup_widget, window)

        self.assertEqual(window.btn_search.text(), "搜索")
        self.assertEqual(window.btn_notice.text(), "历史记录")
        self.assertEqual(window.btn_setting.text(), "系统设置")
```

- [ ] **Step 2: 运行完整 smoke test**

Run: `python -m unittest -q tests.test_gui_windows11_shell`
Expected: PASS

- [ ] **Step 3: 运行编译检查**

Run: `python -m compileall -q src/gui/kingdee_sync_gui.py src/gui/pages src/gui/ui_text.py`
Expected: no output

- [ ] **Step 4: 扫描残留英文文案**

Run: `rg -n "\"[A-Za-z][A-Za-z0-9 ,:()/%._+-]{2,}\"" src/gui/kingdee_sync_gui.py src/gui/pages src/gui/ui_text.py`
Expected: 仅保留允许的技术名词，例如 `Kingdee`、`SQL Server`、`API`、`WebAPI`，不应再出现 `Save`、`History`、`Start sync` 这类用户界面英文文案

- [ ] **Step 5: Offscreen 启动 GUI 验证**

Run: `$env:QT_QPA_PLATFORM='offscreen'; @'
from PySide6.QtWidgets import QApplication
from src.gui.kingdee_sync_gui import KingdeeSyncGUI
app = QApplication.instance() or QApplication([])
window = KingdeeSyncGUI()
print(window.windowTitle())
window.close()
window.deleteLater()
app.processEvents()
app.quit()
'@ | python -`
Expected: print `金蝶数据同步工具 v2.0`

- [ ] **Step 6: Commit**

```bash
git add src/gui/ui_text.py src/gui/kingdee_sync_gui.py src/gui/pages tests/test_gui_windows11_shell.py
git commit -m "feat: localize gui copy to zh-cn"
```
