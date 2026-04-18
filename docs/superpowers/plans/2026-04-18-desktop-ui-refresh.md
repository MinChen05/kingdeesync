# Kingdee Desktop UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the PySide6 desktop application into a more distinctive, editorial operations console while preserving existing sync workflows and page behavior.

**Architecture:** Keep the current page/component structure and apply the redesign through shared shell styling plus small, safe page-level structural updates. Centralize the visual shift in `assets/styles.css`, then add only the minimum new widget properties and layout tweaks in the main shell and the highest-traffic pages so the new aesthetic reaches the whole app without rewriting business logic.

**Tech Stack:** Python 3.11, PySide6, Qt stylesheets, existing page widgets in `src/gui`

---

### Task 1: Map the redesign onto the shared desktop shell

**Files:**
- Modify: `assets/styles.css`
- Modify: `src/gui/kingdee_sync_gui.py`
- Verify: `python -m compileall src/gui/kingdee_sync_gui.py`

- [ ] **Step 1: Add a final stylesheet override section for the new visual language**

```css
/* 2026 desktop redesign: editorial operations deck */
QWidget#desktop_body {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #f7f1e3,
        stop: 0.45 #ebe4d5,
        stop: 1 #d9d0bf
    );
}

QFrame#sidebar {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 #151b22,
        stop: 1 #1e2731
    );
}

QFrame#top_status_bar,
QFrame[ui="apple-settings-card"],
QFrame[ui="apple-summary-card"] {
    background-color: rgba(255, 250, 242, 0.9);
    border: 1px solid #d9ceb8;
}
```

- [ ] **Step 2: Restyle title bar, search, chips, buttons, and cards around the same palette**

```css
QPushButton[class="apple-primary"] {
    background-color: #8c5a2b;
    border: 1px solid #8c5a2b;
    color: #fffaf2;
}

QPushButton[class="apple-secondary"] {
    background-color: rgba(255, 250, 242, 0.92);
    border: 1px solid #cfc1a5;
    color: #2b241c;
}

QLabel[td="status-chip"][tone="info"] {
    background-color: #efe2c6;
    color: #7b4d1f;
}
```

- [ ] **Step 3: Upgrade the shell widgets with clearer object names and more intentional topbar actions**

```python
self.btn_search = self._create_top_action_button("搜索", self.focus_topbar_search)
self.btn_notice = self._create_top_action_button("历史", lambda: self.switch_to_page("history"))
self.btn_setting = self._create_top_action_button("设置", lambda: self.switch_to_page("settings"))
self.topbar_user.setText("OPS")
```

- [ ] **Step 4: Add shell-level accent containers only if the existing selectors are not enough**

```python
content_shell.setObjectName("main_content_shell")
bar.setObjectName("top_status_bar")
self.topbar_search.setObjectName("topbar_search")
```

- [ ] **Step 5: Run a syntax-only verification on the updated shell file**

Run: `python -m compileall src/gui/kingdee_sync_gui.py`
Expected: `Compiling 'src/gui/kingdee_sync_gui.py'...`

- [ ] **Step 6: Commit**

```bash
git add assets/styles.css src/gui/kingdee_sync_gui.py docs/superpowers/plans/2026-04-18-desktop-ui-refresh.md
git commit -m "feat: refresh desktop shell styling"
```

### Task 2: Recompose the dashboard into a stronger control-center front page

**Files:**
- Modify: `src/gui/pages/dashboard_page.py`
- Modify: `assets/styles.css`
- Verify: `python -m compileall src/gui/pages/dashboard_page.py`

- [ ] **Step 1: Add a stronger hero composition with a stat rail / narrative tone rather than plain summary copy**

```python
hero_meta = QVBoxLayout()
hero_meta.setSpacing(8)
self.hero_kicker = QLabel("Control Deck")
self.hero_kicker.setProperty("td", "hero-kicker")
self.hero_narrative = QLabel("把同步工具首页做成运营指挥台，而不是普通后台首页。")
self.hero_narrative.setProperty("td", "hero-narrative")
hero_meta.addWidget(self.hero_kicker)
hero_meta.addWidget(self.hero_narrative)
layout.addLayout(hero_meta, 1)
```

- [ ] **Step 2: Add dedicated properties for dashboard cards so the stylesheet can differentiate them**

```python
card.setProperty("ui", "dashboard-hero-card")
trend_card.setProperty("ui", "dashboard-panel")
gauge_card.setProperty("ui", "dashboard-panel")
summary_card.setProperty("ui", "dashboard-panel")
```

- [ ] **Step 3: Add matching final stylesheet selectors for dashboard-specific polish**

```css
QFrame[ui="dashboard-hero-card"] {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(33, 40, 48, 0.96),
        stop: 1 rgba(57, 43, 28, 0.94)
    );
    border: 1px solid #5e4a35;
}

QFrame[ui="dashboard-panel"] {
    background-color: rgba(255, 250, 242, 0.94);
    border: 1px solid #dbcdb6;
    border-radius: 24px;
}
```

- [ ] **Step 4: Keep data logic intact and only swap presentation hooks**

```python
self._set_chip(self.status_badge, status_text, status_tone)
self.hero_narrative.setText(
    f"今日执行 {sync_count} 次任务，累计同步 {sync_records:,} 条记录，成功率 {success_rate:.1f}%。"
)
```

- [ ] **Step 5: Run syntax verification for the dashboard page**

Run: `python -m compileall src/gui/pages/dashboard_page.py`
Expected: `Compiling 'src/gui/pages/dashboard_page.py'...`

- [ ] **Step 6: Commit**

```bash
git add src/gui/pages/dashboard_page.py assets/styles.css
git commit -m "feat: redesign dashboard control center"
```

### Task 3: Refresh the sync workspace and align the remaining pages to the same system

**Files:**
- Modify: `src/gui/pages/sync_page.py`
- Modify: `src/gui/pages/settings_page.py`
- Modify: `src/gui/pages/forms_page.py`
- Modify: `src/gui/pages/schedule_page.py`
- Modify: `src/gui/pages/history_page.py`
- Modify: `assets/styles.css`
- Verify: `python -m compileall src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py`

- [ ] **Step 1: Give the sync hero and workspace panels explicit styling hooks**

```python
self.workspace_splitter.setProperty("ui", "workspace-shell")
self.config_container.setProperty("ui", "workspace-column")
self.monitor_container.setProperty("ui", "workspace-column")
self.execution_card.setProperty("ui", "sync-monitor-card")
self.log_card.setProperty("ui", "sync-monitor-card")
```

- [ ] **Step 2: Add a small operations-strip element to the sync page so the redesign feels intentional**

```python
self.ops_strip = QLabel("先确认范围，再测试连接，最后执行同步。")
self.ops_strip.setProperty("td", "ops-strip")
config_layout.insertWidget(1, self.ops_strip)
```

- [ ] **Step 3: Reuse shared selectors on the settings / forms / schedule / history pages instead of rewriting layouts**

```python
card.setProperty("ui", "apple-settings-card")
subtitle.setProperty("td", "apple-group-subtitle")
btn_export.setProperty("class", "apple-secondary")
```

- [ ] **Step 4: Add final selectors for workspace columns, monitor cards, and page-wide typography**

```css
QWidget[ui="workspace-column"] {
    background: transparent;
}

QFrame[ui="sync-monitor-card"] {
    background-color: rgba(255, 251, 245, 0.94);
    border: 1px solid #dacdb7;
    border-radius: 24px;
}

QLabel[td="ops-strip"] {
    background-color: rgba(140, 90, 43, 0.08);
    border: 1px solid #d2bd9b;
    border-radius: 14px;
    color: #6b4823;
    padding: 10px 12px;
}
```

- [ ] **Step 5: Run syntax verification on all touched page files**

Run: `python -m compileall src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py`
Expected: `Compiling ...` lines for each file with no traceback

- [ ] **Step 6: Commit**

```bash
git add src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py assets/styles.css
git commit -m "feat: unify redesigned desktop workspace pages"
```

### Task 4: Verify the redesign without touching unrelated repository changes

**Files:**
- Review only: `git diff -- assets/styles.css src/gui/kingdee_sync_gui.py src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py`

- [ ] **Step 1: Review only the intended UI files before claiming completion**

Run: `git diff -- assets/styles.css src/gui/kingdee_sync_gui.py src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py`
Expected: diff output only for the planned UI refresh files

- [ ] **Step 2: Re-run compile verification across the shell and pages**

Run: `python -m compileall src/gui/kingdee_sync_gui.py src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py`
Expected: successful compile output with no traceback

- [ ] **Step 3: Optional lint pass if environment is ready**

Run: `python -m ruff check src/gui/kingdee_sync_gui.py src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py`
Expected: no new lint errors in the touched files

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-04-18-desktop-ui-refresh.md assets/styles.css src/gui/kingdee_sync_gui.py src/gui/pages/dashboard_page.py src/gui/pages/sync_page.py src/gui/pages/settings_page.py src/gui/pages/forms_page.py src/gui/pages/schedule_page.py src/gui/pages/history_page.py
git commit -m "feat: deliver desktop UI redesign"
```
