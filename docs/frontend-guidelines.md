# 前端 / GUI 设计系统规范

**适用范围：** `src/gui/` 下所有 PySide6 / Qt Widgets 代码
**最后更新：** 2026-06-17

---

## 结论速览

| 项 | 现状 | 规范 |
|---|------|------|
| 框架 | PySide6 / Qt Widgets | 不变，不引入 Web 框架 |
| 视觉风格 | Windows 11 / Fluent 工作台 | 统一为浅色云雾背景 + 白色卡片 + 蓝色强调 |
| 样式管理 | `assets/styles.css`（集中 QSS，含 600+ 唯一 hex 色值）+ `design_tokens.py` | QSS 集中管理，token 是唯一 Python 颜色源 |
| 组件复用 | `Win11PageScaffold`、`Win11SectionCard`、`LoadingButton` 等已有 | 继续扩展，禁止页面重复实现 |
| 最低分辨率 | 1366×768 | 不变 |
| 违规项 | 3 处 `setStyleSheet`、113 处散落硬编码尺寸 | 列入整改清单，不顺手改 |

---

## 1. 总体设计风格

### 1.1 视觉定位

- **Windows 11 / Fluent 工作台风格**：浅色云雾背景、白色卡片、深色左侧导航、蓝色强调色。
- **企业数据同步/运维工具气质**：稳定、清晰、紧凑、低装饰。
- **不做**：营销页、插画页、大面积渐变、大卡片堆叠、圆角大于 18px 的装饰性容器。

### 1.2 页面信息层级

每个页面遵循同一问答顺序：

1. **我在哪？** — 页面标题 / hero 区
2. **当前状态？** — 摘要卡 / 状态指示
3. **主要操作？** — 操作栏 / 按钮区
4. **详细内容？** — 表格 / 日志 / 列表 / 表单

### 1.3 分辨率基线

| 分辨率 | 要求 |
|--------|------|
| 1366×768 | 完整可用，所有主操作可见 |
| 1600×900 | 舒展布局 |
| 1920×1080+ | 自然留白扩展 |

---

## 2. 前端技术方案

### 2.1 技术栈

- **PySide6 >= 6.5.0**（Qt Widgets，非 QML）
- **Qt Layout Manager**：`QVBoxLayout`、`QHBoxLayout`、`QGridLayout`、`QSplitter`
- **Signal / Slot**：标准 Qt 通信机制
- **QSizePolicy**：控制伸缩，禁止绝对定位
- **QThread / Worker**：异步操作（见 `src/gui/workers.py`）

### 2.2 样式方案

- **唯一全局样式入口**：`assets/styles.css`，通过主窗口 `self.setStyleSheet()` 加载（见 `kingdee_sync_gui.py:123`，非 `QApplication.setStyleSheet()`）
- **唯一 Python token 源**：`src/gui/design_tokens.py`
- **皮肤机制**：控件通过 `objectName` 或 `setProperty("ui", ...)` 让 QSS 选中
- **不使用** `qt-material`（已在 `requirements.txt` 但不应与 Win11 QSS 混用）

### 2.3 禁止事项

- 禁止引入 Vue / React / Web 前端框架
- 禁止绕开 Qt 布局系统手写 `setGeometry()` 绝对定位（`ScaleButton` 中的动画除外）
- 禁止在页面中使用 `setStyleSheet()` 内联样式（极小动态状态且无法用 QSS property 表达的除外）

---

## 3. UI 组件库策略

### 3.1 基础控件

优先使用 Qt 官方控件：`QPushButton`、`QLabel`、`QLineEdit`、`QComboBox`、`QTableWidget`、`QProgressBar`、`QScrollArea`、`QSplitter`、`QStackedWidget`。

### 3.2 项目自有组件（`src/gui/components/`）

| 组件 | 文件 | 用途 |
|------|------|------|
| `Win11PageScaffold` | `page_shell.py` | 页面骨架：hero + 操作栏 + 摘要条 + 内容区 |
| `Win11SectionCard` | `page_shell.py` | 内容卡片：标题 + 副标题 + body |
| `Win11SummaryCard` | `page_shell.py` | 摘要统计卡 |
| `LoadingButton` | `buttons.py` | 带加载动画的主操作按钮 |
| `SwitchButton` | `buttons.py` | 开关按钮 |
| `ScaleButton` | `buttons.py` | 点击缩放效果按钮 |
| `ClickableLabel` | `buttons.py` | 可点击标签 |
| `SearchableComboBox` | `combobox.py` | 可搜索下拉框 |
| `StateWidget` | `states.py` | 空态 / 错误态 / 加载态面板 |
| `HorizontalBarChart` | `charts.py` | 水平柱状图 |
| `SimpleLineChart` | `charts.py` | 折线图 |
| `SuccessRateBar` | `charts.py` | 成功率柱状图 |

### 3.3 禁止重复实现

页面**不得**重复实现以下通用结构，必须使用已有组件或封装新组件：

- 按钮（特别是带 loading 状态的按钮）
- 状态标签 / 状态指示器
- 筛选栏 / 搜索栏
- 空态 / 错误态 / 加载态
- 卡片容器

---

## 4. 目录结构和模块边界

```
src/gui/
├── kingdee_sync_gui.py    # 壳层：窗口、导航、标题栏、页面装配
├── design_tokens.py       # 唯一 Python token 源（颜色、圆角、尺寸）
├── ui_text.py             # 唯一文案常量源
├── feedback.py            # 统一消息对话框
├── workers.py             # 异步 worker
├── async_loader.py        # 异步加载器
├── logging_utils.py       # GUI 日志工具
├── components/            # 低耦合复用组件
│   ├── page_shell.py      # 页面骨架、卡片
│   ├── buttons.py         # 按钮组件
│   ├── combobox.py        # 下拉框组件
│   ├── states.py          # 状态视图
│   └── charts.py          # 图表
└── pages/                 # 页面编排、服务调用、状态更新
    ├── dashboard_page.py
    ├── sync_page.py
    ├── forms_page.py
    ├── schedule_page.py
    ├── history_page.py
    └── settings_page.py
```

### 边界规则

| 位置 | 允许 | 禁止 |
|------|------|------|
| `kingdee_sync_gui.py` | 壳层逻辑、导航、窗口行为 | 业务逻辑、通用组件定义 |
| `design_tokens.py` | 颜色、圆角、尺寸常量 | 业务逻辑、UI 组件 |
| `components/` | 通用、低业务耦合的 UI 组件 | 页面特有逻辑、业务调用 |
| `pages/` | 页面编排、服务调用、状态更新 | 通用组件重复实现、散落样式 |
| `ui_text.py` | 文案常量 | 样式、逻辑 |

---

## 5. 优先封装组件

以下组件建议优先封装到 `src/gui/components/`，当前尚不存在或封装不完整：

### 5.1 ActionBar

页面顶部主操作区。当前各页面自行创建 `QPushButton` + `QHBoxLayout`，应统一为组件。

```
[ 主操作按钮 ] [ 次要按钮 ] [ ... ] [ 右侧辅助 ]
```

### 5.2 FieldRow / SettingRow

标题 + 说明 + 输入控件的水平行。当前 `settings_page.py` 和 `schedule_page.py` 中大量重复。

```
[ 标题 ] [ 说明文字 ] [ 输入控件 ]
```

### 5.3 StatusChip

成功、警告、失败、运行中、空闲状态标签。当前 `dashboard_page.py` 和 `sync_page.py` 各自实现。

### 5.4 FilterToolbar

搜索 + 筛选 + 查询 + 导出的工具栏。当前 `history_page.py` 和 `forms_page.py` 各自实现。

### 5.5 DataTable + PaginationCard

表格 + 空态 + 分页。当前 `history_page.py` 和 `dashboard_page.py` 各自实现表格逻辑。

### 5.6 LogPanel

日志过滤 + 复制 + 清空 + 滚动策略。当前 `sync_page.py` 和 `schedule_page.py` 各自实现。

### 5.7 MetricCard

统一指标卡（标题 + 数值 + 趋势）。当前 `dashboard_page.py` 和 `sync_page.py` 各自实现。

---

## 6. Design Token 规范

**Python 侧**（动态样式、`QColor`、代码中设置颜色）：必须从 `src/gui/design_tokens.py` 获取。**禁止页面新增裸 hex 色值、裸 QColor 数值、局部 setStyleSheet。**

**QSS 侧**（`assets/styles.css` 中的静态样式）：Qt QSS 无法直接读取 Python 变量。当前策略：
- QSS 中的色值暂保留手写 hex，但应与 `ColorTokens` 中的值保持一致。
- 后续如引入 token→QSS 生成器，可从 Python token 自动生成 QSS 片段。
- 在生成器就绪前，新增 QSS 仍写在 `assets/styles.css`，色值参考 `ColorTokens`。
- 逐步整改现有 QSS 中与 token 不一致的色值（见整改清单）。

### 6.1 颜色（`ColorTokens`）

| 分类 | Token | 值 | 用途 |
|------|-------|-----|------|
| **Accent** | `ACCENT_700` | `#2578DA` | 按下 / 深色强调 |
| | `ACCENT_600` | `#4CA8F8` | 主强调色 |
| | `ACCENT_500` | `#7AC2FF` | 悬停 / 浅强调 |
| | `ACCENT_100` | `#D8EEFF` | 浅色背景 |
| | `ACCENT_50` | `#EFF8FF` | 极浅背景 |
| **Neutrals** | `NEUTRAL_900` | `#14263A` | 近黑文字 |
| | `NEUTRAL_700` | `#284157` | 次要文字 |
| | `NEUTRAL_500` | `#647F97` | 弱化文字 |
| | `NEUTRAL_400` | `#8CA3B6` | 禁用文字 |
| | `NEUTRAL_200` | `#D7E3ED` | 浅描边 |
| | `NEUTRAL_100` | `#EBF2F8` | 浅背景 |
| | `NEUTRAL_50` | `#F6FAFD` | 极浅背景 |
| **Surface** | `SURFACE_BASE` | `#FFFFFF` | 卡片 / 输入框背景 |
| | `SURFACE_SUBTLE` | `#F7FBFF` | 次级表面 |
| | `SURFACE_MUTED` | `#EEF6FD` | 三级表面 |
| **Stroke** | `STROKE_DEFAULT` | `#D4E5F3` | 默认描边 |
| | `STROKE_SUBTLE` | `#E5F0F8` | 轻描边 |
| **Status** | `SUCCESS` | `#2E95D9` | 成功 |
| | `SUCCESS_BG` | `#EAF5FF` | 成功背景 |
| | `WARNING` | `#B0861A` | 警告 |
| | `WARNING_BG` | `#FFF8E2` | 警告背景 |
| | `DANGER` | `#C24D4D` | 危险 / 失败 |
| | `DANGER_BG` | `#FCEEEE` | 危险背景 |
| | `INFO` | `ACCENT_600` | 信息 |

**注意**：`SUCCESS` 当前值 `#2E95D9` 是蓝色而非绿色，这是有意为之（与 Accent 统一）。如需语义绿色，应新增 `SUCCESS_GREEN` 系列而非修改现有值。

### 6.2 圆角（`RadiusTokens`）

| Token | 值 | 用途 |
|-------|-----|------|
| `SM` | 10 | 小控件、输入框 |
| `MD` | 12 | 普通卡片、按钮 |
| `LG` | 18 | 大卡片、弹窗 |
| `PILL` | 999 | 胶囊形 |

**默认规则**：普通卡片优先使用 `MD`（12），按钮使用 `SM`（10）。

### 6.3 尺寸（`SizeTokens`）

| Token | 值 | 用途 |
|-------|-----|------|
| `CONTROL_HEIGHT` | 40 | 输入框、下拉框高度 |
| `BUTTON_HEIGHT` | 36 | 按钮高度 |
| `PAGINATION_SIZE` | 34 | 分页控件高度 |

**建议补充**：

| Token | 建议值 | 用途 |
|-------|--------|------|
| `ICON_SIZE_SM` | 16 | 小图标 |
| `ICON_SIZE_MD` | 20 | 中图标 |
| `SIDEBAR_EXPANDED` | 256 | 侧栏展开宽度 |
| `SIDEBAR_COMPACT` | 96 | 侧栏紧凑宽度 |
| `MIN_DESKTOP_WIDTH` | 1366 | 最低支持宽度 |
| `MIN_DESKTOP_HEIGHT` | 768 | 最低支持高度 |

### 6.4 间距

当前未在 token 中定义，建议新增 `SpacingTokens`：

| Token | 值 | 用途 |
|-------|-----|------|
| `XS` | 4 | 极小间距 |
| `SM` | 8 | 小间距 |
| `MD` | 12 | 默认间距 |
| `LG` | 16 | 大间距 |
| `XL` | 20 | 卡片内边距 |
| `XXL` | 24 | 区域间距 |
| `XXXL` | 32 | 页面边距 |

### 6.5 排版

当前通过 QSS 全局设置 `font-size: 13px`。建议在 token 中补充：

| Token | 建议值 | 用途 |
|-------|--------|------|
| `FONT_FAMILY` | `"Segoe UI Variable", "Microsoft YaHei UI", sans-serif` | 字体族 |
| `FONT_SIZE_SM` | 12 | 小字 |
| `FONT_SIZE_MD` | 13 | 正文 |
| `FONT_SIZE_LG` | 15 | 标题 |
| `FONT_SIZE_XL` | 18 | 大标题 |
| `FONT_WEIGHT_NORMAL` | 400 | 正常 |
| `FONT_WEIGHT_MEDIUM` | 600 | 中等 |
| `FONT_WEIGHT_BOLD` | 700 | 加粗 |

### 6.6 效果

| Token | 建议值 | 用途 |
|-------|--------|------|
| `SHADOW_CARD` | `0 2px 8px rgba(0,0,0,0.06)` | 卡片阴影 |
| `SHADOW_POPUP` | `0 4px 16px rgba(0,0,0,0.12)` | 弹窗阴影 |
| `FOCUS_RING` | `0 0 0 2px ACCENT_500` | 焦点环 |

---

## 7. 代码规范和禁止事项

### 7.1 样式规则

| 规则 | 说明 |
|------|------|
| 禁止新增散落的 `setStyleSheet()` | 除非是极小动态状态且无法通过 QSS `property` 表达 |
| 禁止在 pages 里新增硬编码颜色 | 颜色必须来自 `ColorTokens` |
| 禁止裸 hex 色值 | `src/gui/pages/` 下不允许出现 `#[0-9a-fA-F]{3,8}` 字面量 |
| 所有新增 QSS 必须写在 `assets/styles.css` | 不允许页面内嵌样式表 |

### 7.2 布局规则

| 规则 | 说明 |
|------|------|
| 使用 Qt Layout Manager | 禁止 `setGeometry()` 绝对定位（动画除外） |
| 使用 `QSizePolicy` | 控制伸缩行为 |
| 间距值来自 token 或合理默认 | 禁止随意写死像素值 |
| 不破坏 1366×768 可用性 | 新增组件必须在此分辨率下验证 |

### 7.3 组件规则

| 规则 | 说明 |
|------|------|
| 优先使用已有 `components/` | 禁止重复实现按钮、状态标签、筛选栏等 |
| 新通用组件放 `src/gui/components/` | 不放 pages 目录 |
| 页面只做编排和业务调用 | 不沉淀通用 UI 逻辑 |
| 文案规则见下方 7.5 节 | 通用按钮、状态、反馈文案进入 `ui_text.py`；页面标题和一次性静态说明暂允许保留 |

### 7.4 禁止事项汇总

1. 禁止新增散落的 `setStyleSheet()`
2. 禁止在 pages 里新增硬编码颜色
3. 禁止重复实现已有 components 能承担的 UI
4. 禁止为了单页效果绕开统一 QSS
5. 禁止破坏 1366×768 可用性
6. 禁止改变同步、设置、调度、历史查询等业务逻辑
7. 禁止引入 Web 前端框架
8. 禁止绕开 Qt 布局系统

### 7.5 文案规则

| 分类 | 策略 |
|------|------|
| 通用按钮文案（保存、导出、复制等） | 必须进入 `ui_text.py` 的 `ButtonText` |
| 通用 loading 文案 | 必须进入 `ui_text.py` 的 `LoadingText` |
| 通用状态 / 空态 / 错误态文案 | 必须进入 `ui_text.py` 的 `StateText` |
| 通用消息反馈文案 | 必须进入 `ui_text.py` 的 `MessageText` |
| 页面标题、一次性静态说明、菜单项文案 | 暂允许在页面中内联保留，后续做文案收敛专项 |

**理由**：当前 `kingdee_sync_gui.py` 和 pages 中存在大量内联中文标题/说明，一次性全部迁移到 `ui_text.py` 属于大规模本地化改造，不适合作为前端规范的前置条件。优先保证可复用文案的集中管理。

---

## 8. 测试和验收

### 8.1 现有测试

`tests/test_gui_windows11_shell.py` 已覆盖：
- Win11 selector 存在性
- QSS 加载验证
- 基本组件实例化

### 8.2 建议扩展测试

#### Token 规范检查

```python
def test_pages_have_no_hardcoded_hex_colors():
    """src/gui/pages/ 下不允许裸 hex 色值。"""
    # 扫描 pages/*.py，正则匹配 #[0-9a-fA-F]{3,8}
    # 排除注释和字符串中的 URL
    ...

def test_pages_have_no_inline_stylesheet():
    """src/gui/pages/ 下不允许 setStyleSheet()。"""
    # 扫描 pages/*.py，grep setStyleSheet
    # 当前已知 3 处违规（dashboard_page.py:275/277/279）
    ...
```

#### QSS 唯一性检查

```python
def test_single_global_stylesheet():
    """验证主窗口加载了全局样式。"""
    # 样式通过主窗口 self.setStyleSheet() 加载（非 QApplication 级）
    # 检查 KingdeeSyncGUI 实例的 styleSheet() 非空
    # 检查 assets/styles.css 存在且内容被加载
    ...
```

#### GUI Offscreen Smoke

```python
def test_pages_instantiate_at_1366x768():
    """1366×768 下所有页面可实例化。"""
    app = QApplication.instance() or QApplication([])
    for page_cls in [DashboardPage, SyncPage, FormConfigPage, ...]:
        page = page_cls()
        page.resize(1366, 768)
        page.show()
        # 验证主操作区和内容容器可见
        ...
```

---

## 9. 后续整改清单

以下为当前代码中已存在的违规项，部分已整改，部分留作长期治理：

| # | 文件 | 问题 | 状态 |
|---|------|------|------|
| 1 | `pages/dashboard_page.py` | `setStyleSheet` 硬编码红/橙/绿色 | ✅ 已修复（改用 tone property） |
| 2 | `assets/styles.css` | 600+ hex 色值，部分未对应 token | ✅ Phase 1-5 治理完成（命中率 29%），长期护栏已建立 |
| 3 | `pages/*.py` | 散落硬编码像素值 | ✅ 6 个页面全部 token 化 |
| 4 | `design_tokens.py` | 缺少 SpacingTokens/TypographyTokens/EffectsTokens | ✅ 已新增 |
| 5 | `design_tokens.py` | 缺少尺寸 token | ✅ 已新增 |
| 6 | `components/` | 缺少通用组件 | ✅ 已封装 ActionBar/FieldRow/StatusChip/LogPanel/MetricCard/DataTable 等 |
| 7 | `pages/*.py` | 页面私有子组件 | ✅ Dashboard/History/Sync/Schedule 已提取 |

**长期治理**：
- `assets/styles.css` 色值逐步收敛（已有静态护栏测试防回退）
- FilterBar 按需治理（History 已通过 HistoryFilterPanel 解决）
- 新增组件必须使用已有 token，不允许引入新裸 hex

---

## 10. 当前状态总结

前端规范整改已全部完成：

- ✅ **token 体系**：7 个 token 类（ColorTokens/RadiusTokens/SizeTokens/SpacingTokens/TypographyTokens/EffectTokens/ChartTokens）
- ✅ **通用组件**：12+ 个已封装（ActionBar/FieldRow/StatusChip/LogPanel/MetricCard/DataTable 等）
- ✅ **页面重构**：6 个页面全部完成（Dashboard/History/Sync/Schedule 完成；Forms/Settings 轻量完成）
- ✅ **QSS 治理**：Phase 1-5 色值治理完成，静态护栏测试已建立
- ✅ **测试覆盖**：169 个 GUI 测试，QSS token 治理 4 个护栏测试

**长期维护**：
- 新增组件必须使用已有 token
- 新增页面必须通过 GUI 测试和 token 合规检查
- `assets/styles.css` 色值按需收敛，不批量替换

---

## 11. 页面重构样板（基于 Dashboard Phase 0-5）

### 11.1 组件提取模式

```
src/gui/pages/dashboard_page.py          ← 页面主文件（编排 + 服务调用）
src/gui/pages/_dashboard_status_cards.py  ← 页面私有子组件
src/gui/pages/_dashboard_charts.py        ← 页面私有子组件
src/gui/pages/_dashboard_fail_table.py    ← 页面私有子组件
src/gui/components/data_table.py          ← 可跨页面复用组件
```

**命名约定**：
- 页面私有子组件：`src/gui/pages/_<page>_<part>.py`（下划线前缀，不导出）
- 可复用组件：`src/gui/components/<name>.py`（无下划线，从 `__init__.py` 导出）

### 11.2 子组件职责边界

| 职责 | 子组件 | 页面 |
|------|--------|------|
| UI 渲染 | ✅ | ❌ 不手写 widget |
| 数据格式化 | ✅ 纯展示格式化 | ✅ 业务格式化 |
| 服务调用 | ❌ **禁止** | ✅ 唯一入口 |
| 业务状态 | ❌ **不保存** | ✅ 唯一持有者 |
| 事件通知 | ✅ Signal 或回调 | ✅ 处理事件 |

### 11.3 数据流

```
页面 → 子组件.update(data)    # 数据推送，单向
子组件 → 页面.on_xxx()        # 事件通知，回调或 Signal
```

### 11.4 DataTable 最小接口

```python
class DataTable(QFrame):
    def __init__(self, headers: list[str], *, parent=None)
    def set_data(rows: list[list[str]]) -> None
    def clear() -> None
    def set_empty_text(text: str) -> None
    @property table -> QTableWidget
```

**扩展边界**：
- History 阶段再扩展分页、行选择回调
- 不提前实现排序、筛选联动、虚拟滚动

### 11.5 测试策略

- 组件级：实例化、数据更新、事件触发、Token 使用
- 页面级：组件集成、行为回归、1366×768 可用性、导航跳转
- 不推荐：像素级截图、子组件内部 widget 直接访问

### 11.6 详细模式文档

参见 `docs/dashboard-refactor-pattern.md`。
