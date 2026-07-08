---
change: redesign-gui-icons
design-doc: docs/superpowers/specs/2026-07-08-gui-icon-system-design.md
base-ref: 5de8fb44c124dc7baf2cac94bdaa5e78d65b178a
archived-with: 2026-07-08-redesign-gui-icons
---

# GUI Icon System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重做全 GUI 页面图标渲染，建立本地 SVG 资产、集中注册表和共享渲染助手。

**Architecture:** 新增 `src/gui/icon_registry.py` 作为图标语义注册表，页面只通过 page/action/status/metric token 获取资产路径或 `QIcon`。保留 `SvgIconLabel` 作为渲染组件，并让它优先使用注册表解析资产，页面迁移时减少本地硬编码映射。（原因：同类图标映射已跨页面重复超过 2 次，应抽象为公共模块）

**Tech Stack:** Python、PySide6、Qt SVG、本地 SVG assets、pytest/unittest 风格 GUI 测试、PyInstaller assets 打包。

archived-with: 2026-07-08-redesign-gui-icons
---

## File Structure

- Create: `src/gui/icon_registry.py`
  - 维护页面、动作、状态、指标、页面局部图标 token 到 SVG 文件的映射。
  - 提供 `icon_path()`、`qicon()`、`required_icon_files()`、`page_icon_source()` 等只读 API。
- Modify: `src/gui/components/common.py`
  - 让 `SvgIconLabel` 支持传入注册表 token 或文件名，并保持现有 `icon-source` 属性兼容。
- Modify: `src/gui/kingdee_sync_gui.py`
  - 将 `SIDEBAR_NAV_ICON_FILES`、顶部按钮、状态图标加载迁移到注册表。
- Modify: `src/gui/pages/*.py`
  - 将仪表盘、同步、计划任务、表单、诊断、日志中心、历史记录、数据源、设置、任务管理的本地图标字典迁移到注册表。
- Modify: `assets/icons/*.svg`
  - 重做主要 SVG，统一 24x24 viewBox、线性风格、`currentColor` 颜色入口。
- Modify: `assets/styles.css`
  - 保持图标尺寸、状态色、页面局部选择器与注册表命名一致。
- Create/Modify: `tests/test_gui_icon_registry.py`
  - 覆盖注册表完整性、资产存在性、页面映射和 QIcon 非空。
- Modify: `tests/test_gui_windows11_shell.py`
  - 将旧文件名硬断言迁移为注册表断言，保留关键尺寸/属性检查。
- Modify: `openspec/changes/redesign-gui-icons/tasks.md`
  - 每完成阶段性任务后勾选。

archived-with: 2026-07-08-redesign-gui-icons
---

### Task 1: Build Icon Registry Test First

**Files:**
- Create: `tests/test_gui_icon_registry.py`
- Create: `src/gui/icon_registry.py`
- Modify: `openspec/changes/redesign-gui-icons/tasks.md`

- [ ] **Step 1: Write failing registry coverage tests**

Create `tests/test_gui_icon_registry.py`:

```python
import unittest

from PySide6.QtGui import QIcon

from src.gui import icon_registry
from src.gui.kingdee_sync_gui import PAGE_ORDER


class GuiIconRegistryTests(unittest.TestCase):
    def test_all_sidebar_pages_have_existing_icons(self) -> None:
        missing_pages = []
        missing_files = []

        for page_id, _label in PAGE_ORDER:
            source = icon_registry.page_icon_source(page_id)
            if not source:
                missing_pages.append(page_id)
                continue
            path = icon_registry.icon_path(source)
            if not path.exists():
                missing_files.append((page_id, source))

        self.assertEqual(missing_pages, [])
        self.assertEqual(missing_files, [])

    def test_required_icon_files_exist(self) -> None:
        missing = [
            source
            for source in sorted(icon_registry.required_icon_files())
            if not icon_registry.icon_path(source).exists()
        ]

        self.assertEqual(missing, [])

    def test_registered_qicons_are_not_null(self) -> None:
        null_icons = []
        for source in sorted(icon_registry.required_icon_files()):
            icon = icon_registry.qicon(source)
            if not isinstance(icon, QIcon) or icon.isNull():
                null_icons.append(source)

        self.assertEqual(null_icons, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py -q
```

Expected: FAIL because `src.gui.icon_registry` does not exist.

- [ ] **Step 3: Add minimal registry module**

Create `src/gui/icon_registry.py`:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
ICONS_DIR = ASSETS_DIR / "icons"

PAGE_ICONS: dict[str, str] = {
    "dashboard": "dashboard.svg",
    "sync": "sync.svg",
    "history": "history.svg",
    "task_management": "task_management.svg",
    "data_source": "data_source.svg",
    "forms": "forms.svg",
    "schedule": "schedule.svg",
    "diagnostics": "diagnostics.svg",
    "log_center": "log_center.svg",
    "settings": "settings.svg",
}

ACTION_ICONS: dict[str, str] = {
    "collapse_sidebar": "menu_fold.svg",
    "settings": "topbar_settings.svg",
    "help": "topbar_help.svg",
    "user": "topbar_user.svg",
    "chevron_down": "chevron_down.svg",
    "chevron_left": "chevron_left.svg",
    "chevron_right": "chevron_right.svg",
    "export": "export.svg",
    "filter": "filter.svg",
    "refresh": "refresh.svg",
    "copy": "copy.svg",
    "trash": "trash.svg",
    "close": "close.svg",
}

STATUS_ICONS: dict[str, str] = {
    "success": "status_ok.svg",
    "danger": "status_err.svg",
    "warning": "metric_pending_warning.svg",
    "neutral": "info.svg",
}

METRIC_ICONS: dict[str, str] = {
    "dashboard_trend": "metric_sync_count.svg",
    "dashboard_success_rate": "metric_success_rate.svg",
    "dashboard_failed": "metric_failed_task.svg",
    "dashboard_pending": "metric_pending_warning.svg",
    "dashboard_avg_time": "metric_avg_time.svg",
    "history_clock": "summary_clock.svg",
    "history_fail": "summary_fail.svg",
    "history_rows": "summary_rows.svg",
    "history_document": "summary_document.svg",
    "sync_mode": "sync_mode.svg",
    "sync_target": "sync_target.svg",
    "sync_progress": "sync_progress.svg",
    "sync_result": "sync_result.svg",
    "sync_record": "sync_record.svg",
    "sync_runtime": "sync_runtime.svg",
    "sync_status": "sync_status.svg",
}


def normalize_source(source: str) -> str:
    return source.removeprefix("icons/")


def icon_path(source: str) -> Path:
    normalized = normalize_source(source)
    return ICONS_DIR / normalized


def qicon(source: str) -> QIcon:
    return QIcon(str(icon_path(source)))


def page_icon_source(page_id: str) -> str:
    return PAGE_ICONS[page_id]


def required_icon_files() -> set[str]:
    files: set[str] = set()
    for registry in (PAGE_ICONS, ACTION_ICONS, STATUS_ICONS, METRIC_ICONS):
        files.update(registry.values())
    return files
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py -q
```

Expected: PASS.

- [ ] **Step 5: Mark task and commit**

Update `openspec/changes/redesign-gui-icons/tasks.md`:

```markdown
- [x] 1.1 盘点 `src/gui/`、`assets/styles.css` 和现有 GUI 测试中的所有图标调用点。（原因：避免漏掉页面局部图标）
- [x] 2.1 新增或更新共享 GUI 图标注册表/助手，覆盖 page id、常用 action、metric/status tone 和 fallback 行为。（原因：集中管理全页面图标选择）
- [x] 4.1 新增/更新图标注册表覆盖、资产存在性、导航/页面图标映射测试。（原因：让缺失资产在测试阶段失败）
```

Commit:

```bash
git add src/gui/icon_registry.py tests/test_gui_icon_registry.py openspec/changes/redesign-gui-icons/tasks.md
git commit -m "feat(gui): add icon registry coverage"
```

archived-with: 2026-07-08-redesign-gui-icons
---

### Task 2: Migrate Shared Rendering Helpers And Shell Icons

**Files:**
- Modify: `src/gui/components/common.py`
- Modify: `src/gui/kingdee_sync_gui.py`
- Modify: `tests/test_gui_windows11_shell.py`
- Modify: `openspec/changes/redesign-gui-icons/tasks.md`

- [ ] **Step 1: Write failing shell assertions**

In `tests/test_gui_windows11_shell.py`, update nav icon assertions to import and use the registry:

```python
from src.gui import icon_registry
```

Replace old `EXPECTED_ICON_FILES` expectations with:

```python
self.assertEqual(btn.property("icon-source"), f"icons/{icon_registry.page_icon_source(page_id)}")
self.assertFalse(btn.icon().isNull(), f"Nav button icon missing for {page_id!r}")
self.assertEqual(btn.iconSize().width(), 20)
self.assertEqual(btn.iconSize().height(), 20)
```

Add topbar/collapse expectations:

```python
self.assertEqual(window.sidebar_collapse_btn.property("icon-source"), "icons/menu_fold.svg")
self.assertFalse(window.sidebar_collapse_btn.icon().isNull())
self.assertEqual(window.btn_setting.property("icon-source"), "icons/topbar_settings.svg")
self.assertEqual(window.btn_help.property("icon-source"), "icons/topbar_help.svg")
```

- [ ] **Step 2: Run focused GUI shell tests**

Run:

```bash
python -m pytest tests/test_gui_windows11_shell.py -q -k "icon or sidebar or topbar"
```

Expected: FAIL where current code still sets mixed `icon-source` values such as `menu_fold.svg`.

- [ ] **Step 3: Update `SvgIconLabel` to use registry paths**

Modify `src/gui/components/common.py`:

```python
from src.gui import icon_registry
```

In `SvgIconLabel.set_icon`, replace direct path resolution with:

```python
self.setProperty("icon-source", icon_file if icon_file.startswith("icons/") else f"icons/{icon_registry.normalize_source(icon_file)}")
path = icon_registry.icon_path(icon_file)
size = icon_size or min(self.width(), self.height())
```

Keep the existing `currentColor` rendering branch and `QIcon(str(path)).pixmap(...)` fallback unchanged.

- [ ] **Step 4: Update shell icon loading**

Modify `src/gui/kingdee_sync_gui.py`:

```python
from src.gui import icon_registry
```

Replace `SIDEBAR_NAV_ICON_FILES` usage with:

```python
icon_file = icon_registry.page_icon_source(page_id)
icon_path = icon_registry.icon_path(icon_file)
if icon_path.exists():
    btn.setProperty("icon-source", f"icons/{icon_file}")
    icon = icon_registry.qicon(icon_file)
else:
    icon = _make_nav_icon(page_id, 18, ColorTokens.NEUTRAL_500)
```

For collapse/settings/help buttons:

```python
self.sidebar_collapse_btn.setProperty("icon-source", "icons/menu_fold.svg")
self.sidebar_collapse_btn.setIcon(icon_registry.qicon("menu_fold.svg"))
self.btn_setting.setProperty("icon-source", "icons/topbar_settings.svg")
self.btn_setting.setIcon(icon_registry.qicon("topbar_settings.svg"))
self.btn_help.setProperty("icon-source", "icons/topbar_help.svg")
self.btn_help.setIcon(icon_registry.qicon("topbar_help.svg"))
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py tests/test_gui_windows11_shell.py -q -k "icon or sidebar or topbar"
```

Expected: PASS.

- [ ] **Step 6: Mark task and commit**

Update `openspec/changes/redesign-gui-icons/tasks.md`:

```markdown
- [x] 2.3 确保图标尺寸复用现有 `SizeTokens`，状态色与 Windows 11 shell 样式保持一致。（原因：避免产生第二套视觉 token）
- [x] 3.1 将侧边栏导航和顶部操作图标迁移到共享图标系统。（原因：这是最核心的全局入口）
```

Commit:

```bash
git add src/gui/components/common.py src/gui/kingdee_sync_gui.py tests/test_gui_windows11_shell.py openspec/changes/redesign-gui-icons/tasks.md
git commit -m "feat(gui): route shell icons through registry"
```

archived-with: 2026-07-08-redesign-gui-icons
---

### Task 3: Redesign Core SVG Assets

**Files:**
- Modify: `assets/icons/*.svg`
- Modify: `tests/test_gui_icon_registry.py`
- Modify: `openspec/changes/redesign-gui-icons/tasks.md`

- [ ] **Step 1: Add SVG quality tests**

Append to `tests/test_gui_icon_registry.py`:

```python
    def test_registered_svgs_use_current_color_and_24_viewbox(self) -> None:
        bad_viewbox = []
        missing_current_color = []

        for source in sorted(icon_registry.required_icon_files()):
            path = icon_registry.icon_path(source)
            text = path.read_text(encoding="utf-8")
            if 'viewBox="0 0 24 24"' not in text:
                bad_viewbox.append(source)
            if "currentColor" not in text:
                missing_current_color.append(source)

        self.assertEqual(bad_viewbox, [])
        self.assertEqual(missing_current_color, [])
```

- [ ] **Step 2: Run quality test to find current failures**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py -q
```

Expected: FAIL listing SVG files that still use old viewBox or fixed colors.

- [ ] **Step 3: Replace registered SVGs with unified 24x24 style**

For every file returned by `icon_registry.required_icon_files()`, use this SVG baseline:

```xml
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="..." stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

Rules:
- keep all page/action/status/metric files under `assets/icons/`;
- do not use filters, masks, gradients, embedded fonts, or external references;
- use `fill="currentColor"` only for simple solid marks such as dots or check marks;
- preserve file names so existing packaging rules continue to include assets.

- [ ] **Step 4: Run SVG quality and registry tests**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py -q
```

Expected: PASS.

- [ ] **Step 5: Mark task and commit**

Update `openspec/changes/redesign-gui-icons/tasks.md`:

```markdown
- [x] 1.2 定义目标图标视觉语言：线条粗细、画布尺寸、圆角、留白、状态色、页面/动作分类。（原因：先统一规则再批量替换）
- [x] 1.3 决定哪些现有图标文件可保留、哪些需要替换、哪些新图标名称需要新增。（原因：减少无意义资产 churn）
- [x] 2.2 替换 `assets/icons/` 下低质或不一致的主要 SVG 资产。（原因：从源头改善渲染质量）
```

Commit:

```bash
git add assets/icons tests/test_gui_icon_registry.py openspec/changes/redesign-gui-icons/tasks.md
git commit -m "style(gui): unify icon svg assets"
```

archived-with: 2026-07-08-redesign-gui-icons
---

### Task 4: Migrate Page-Level Icon Usage

**Files:**
- Modify: `src/gui/pages/dashboard_page.py`
- Modify: `src/gui/pages/_dashboard_status_cards.py`
- Modify: `src/gui/pages/sync_page.py`
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `src/gui/pages/diagnostics_page.py`
- Modify: `src/gui/pages/log_center_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `src/gui/pages/data_source_page.py`
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/task_management_page.py`
- Modify: `tests/test_gui_windows11_shell.py`
- Modify: `openspec/changes/redesign-gui-icons/tasks.md`

- [ ] **Step 1: Extend registry for page-local tokens**

Add dictionaries to `src/gui/icon_registry.py`:

```python
DASHBOARD_ICONS = {
    "health_api": "health_api.svg",
    "health_database": "health_database.svg",
    "health_scheduler": "health_scheduler.svg",
    "health_log": "health_log.svg",
    "risk_danger": "metric_failed_task.svg",
    "risk_warning": "metric_pending_warning.svg",
}

PAGE_SECTION_ICONS = {
    "data_source_api": "data_source_api.svg",
    "data_source_database": "data_source_database.svg",
    "forms_configured": "forms_configured.svg",
    "forms_fields": "forms_fields.svg",
    "forms_missing": "forms_missing.svg",
    "forms_updated": "forms_updated.svg",
    "forms_validation_missing": "forms_validation_missing.svg",
    "forms_validation_type": "forms_validation_type.svg",
    "forms_validation_fix": "forms_validation_fix.svg",
    "diagnostic_api": "diagnostic_api.svg",
    "diagnostic_database": "diagnostic_database.svg",
    "diagnostic_field": "diagnostic_field.svg",
    "diagnostic_retry": "diagnostic_retry.svg",
    "diagnostic_suggestion": "diagnostic_suggestion.svg",
    "diagnostic_total": "diagnostic_total.svg",
    "log_total": "log_total.svg",
    "log_error": "log_error.svg",
    "log_warning": "log_warning.svg",
    "log_recent": "log_recent.svg",
    "log_size": "log_size.svg",
    "schedule_status": "schedule_status.svg",
    "schedule_running": "schedule_running.svg",
    "schedule_result": "schedule_result.svg",
    "schedule_heartbeat": "schedule_heartbeat.svg",
    "schedule_interval": "schedule_interval.svg",
    "schedule_last": "schedule_last.svg",
    "schedule_next": "schedule_next.svg",
    "schedule_success": "schedule_success.svg",
}

def token_source(token: str) -> str:
    for registry in (
        PAGE_ICONS,
        ACTION_ICONS,
        STATUS_ICONS,
        METRIC_ICONS,
        DASHBOARD_ICONS,
        PAGE_SECTION_ICONS,
    ):
        if token in registry:
            return registry[token]
    return normalize_source(token)
```

Update `required_icon_files()` to include the new dictionaries.

- [ ] **Step 2: Run registry tests**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py -q
```

Expected: PASS if all registered assets exist.

- [ ] **Step 3: Replace page-local dictionaries with registry tokens**

In each page, import:

```python
from src.gui import icon_registry
```

Replace local direct asset names with `icon_registry.token_source(...)`. Example for dashboard health cards:

```python
icon_w = SvgIconLabel(
    icon_registry.token_source(f"health_{key}"),
    size=26,
    icon_size=20,
    color=icon_bg,
)
```

Example for task management action buttons:

```python
icon_file = icon_registry.token_source(action_type)
self.setProperty("icon-source", f"icons/{icon_registry.normalize_source(icon_file)}")
self.setIcon(icon_registry.qicon(icon_file))
```

If a page token is not already registered, add it to `PAGE_SECTION_ICONS` instead of adding a new local dictionary.

- [ ] **Step 4: Remove obsolete painter-only icon widgets where covered by SVG**

For painter widgets such as history/task metric icons, prefer `SvgIconLabel` if a registered SVG exists:

```python
icon = SvgIconLabel(icon_registry.token_source("history_clock"), size=48, icon_size=31, color=icon_color)
icon.setProperty("ui", "history-summary-icon")
icon.setProperty("tone", icon_type)
```

Keep painter fallback classes only if they are still used by tests or lack an SVG equivalent.

- [ ] **Step 5: Run page-focused GUI tests**

Run:

```bash
python -m pytest tests/test_gui_windows11_shell.py -q -k "dashboard or sync or schedule or forms or diagnostic or log or history or data_source or settings or task_management or icon"
```

Expected: PASS.

- [ ] **Step 6: Mark task and commit**

Update `openspec/changes/redesign-gui-icons/tasks.md`:

```markdown
- [x] 3.2 迁移仪表盘、同步、计划任务、表单、诊断、日志中心、历史记录、数据源、设置、任务管理等页面图标。（原因：满足“所有页面”范围）
- [x] 3.3 在真实资产已覆盖时移除或降级手绘图标，同时保留安全 fallback。（原因：提升正常路径质量并保留异常容错）
```

Commit:

```bash
git add src/gui/icon_registry.py src/gui/pages tests/test_gui_windows11_shell.py openspec/changes/redesign-gui-icons/tasks.md
git commit -m "feat(gui): migrate page icons to registry"
```

archived-with: 2026-07-08-redesign-gui-icons
---

### Task 5: Style, Packaging, And Visual Verification

**Files:**
- Modify: `assets/styles.css`
- Modify: `tests/test_gui_icon_registry.py`
- Modify: `openspec/changes/redesign-gui-icons/tasks.md`
- Create: `docs/superpowers/reports/2026-07-08-gui-icon-system-verification.md`

- [ ] **Step 1: Add CSS asset reference test**

Append to `tests/test_gui_icon_registry.py`:

```python
import re
from pathlib import Path


class GuiIconCssAssetTests(unittest.TestCase):
    def test_css_icon_urls_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        css = (root / "assets" / "styles.css").read_text(encoding="utf-8")
        refs = re.findall(r'url\\("assets/icons/([^"]+)"\\)', css)
        missing = [ref for ref in refs if not icon_registry.icon_path(ref).exists()]

        self.assertEqual(missing, [])
```

- [ ] **Step 2: Normalize CSS icon sizing and state rules**

In `assets/styles.css`, keep existing selectors but ensure icon labels use stable dimensions:

```css
QMainWindow[theme="win11-shell"] QLabel[ui="svg-icon"] {
    min-width: 16px;
    min-height: 16px;
}

QMainWindow[theme="win11-shell"] QLabel[ui$="-icon"] {
    qproperty-alignment: AlignCenter;
}
```

Do not introduce large palette changes or decorative gradients.

- [ ] **Step 3: Run GUI and registry tests**

Run:

```bash
python -m pytest tests/test_gui_icon_registry.py tests/test_gui_windows11_shell.py -q
```

Expected: PASS.

- [ ] **Step 4: Verify packaged asset inclusion rule**

Run:

```bash
python - <<'PY'
from pathlib import Path
spec = Path("kingdee_sync.spec").read_text(encoding="utf-8")
assert "assets" in spec, "kingdee_sync.spec must include assets"
print("assets packaging rule present")
PY
```

Expected: `assets packaging rule present`.

- [ ] **Step 5: Capture or inspect representative GUI screens**

Run the GUI in an environment with display support:

```bash
python main.py
```

Inspect these pages and record findings: 导航、仪表盘、同步、计划任务、表单、诊断、日志中心、历史记录、数据源、设置、任务管理。

Create `docs/superpowers/reports/2026-07-08-gui-icon-system-verification.md`:

```markdown
# GUI 图标系统验证报告

## 自动化验证

- `python -m pytest tests/test_gui_icon_registry.py tests/test_gui_windows11_shell.py -q`：通过。
- `kingdee_sync.spec` assets 打包规则检查：通过。

## 视觉核对

- 导航：图标尺寸一致，选中/普通态可读。
- 仪表盘：指标、健康状态、风险提醒图标风格一致。
- 同步：摘要与执行区图标清晰，无错位。
- 计划任务：统计卡片与状态项图标一致。
- 表单：配置、字段、校验图标一致。
- 诊断：API、数据库、字段、建议类图标一致。
- 日志中心：统计图标一致。
- 历史记录：摘要与翻页动作图标一致。
- 数据源：API 与数据库卡片图标一致。
- 设置：提示图标清晰。
- 任务管理：指标与行内动作图标一致。

## 剩余风险

- 若运行环境无法打开 GUI，应在报告中写明未截图原因，并保留自动化测试证据。
```

- [ ] **Step 6: Mark task and commit**

Update `openspec/changes/redesign-gui-icons/tasks.md`:

```markdown
- [x] 4.2 运行 GUI 相关测试，覆盖导航、图标尺寸、CSS 图标规则和页面构造。（原因：验证图标改造未破坏窗口初始化）
- [x] 4.3 截图或检查主要 GUI 页面并记录视觉结论。（原因：图标质量不能只靠单元测试判断）
- [x] 4.4 验证 PyInstaller 打包仍包含重做后的图标资产。（原因：确保发布产物可用）
```

Commit:

```bash
git add assets/styles.css tests/test_gui_icon_registry.py docs/superpowers/reports/2026-07-08-gui-icon-system-verification.md openspec/changes/redesign-gui-icons/tasks.md
git commit -m "test(gui): verify redesigned icon system"
```

archived-with: 2026-07-08-redesign-gui-icons
---

## Self-Review

- Spec coverage: 统一图标系统由 Task 1-4 覆盖；集中图标选择由 Task 1、2、4 覆盖；打包资产由 Task 5 覆盖；视觉验证由 Task 5 覆盖。
- Placeholder scan: 计划中没有 `TBD`、`TODO`、`implement later` 或未定义的“适当处理”步骤。
- Type consistency: `icon_registry.icon_path()` 返回 `Path`，`qicon()` 返回 `QIcon`，`required_icon_files()` 返回 `set[str]`，页面迁移和测试均使用同一组函数名。
