# 全页面前端重构设计方案

**日期：** 2026-06-18
**状态：** 设计稿（不改代码）

---

## 1. 技术方案对比

### 1.1 候选方案评估

| 方案 | 优势 | 劣势 | 适配度 |
|------|------|------|--------|
| **PySide6 + 自研组件层**（当前） | 零迁移成本；已建立 token/组件/测试体系；Windows 桌面原生体验 | 需自行维护组件库；复杂表格/图表能力有限 | ★★★★★ |
| **PySide6 + QFluentWidgets** | 开箱即用的 Fluent 风格组件；减少自研量 | 第三方库稳定性风险；与现有 token/QSS 体系冲突；API 不完全兼容 | ★★★☆☆ |
| **Qt Quick / QML** | 声明式 UI；动画流畅；适合复杂交互 | 需重写全部页面；Python/QML 桥接复杂度高；桌面工具场景过度 | ★★☆☆☆ |
| **Flet (Flutter)** | 现代 UI；跨平台 | 生态不成熟；桌面支持不完善；需全部重写 | ★☆☆☆☆ |
| **Web / Electron / Tauri** | Web 生态丰富；UI 表现力强 | 引入运行时开销；需重写；与 Python 后端集成复杂 | ★☆☆☆☆ |

### 1.2 推荐方案

**继续 PySide6 + 自研组件层，不做框架迁移。**

理由：
1. **已有投入不可忽视**：7 个 token 类、6 个公共组件、113 个 GUI 测试、QSS 色值治理完成 29%
2. **桌面工具场景匹配**：PySide6 的 QWidget 体系对表单/表格/日志类 UI 足够，无需 QML 的动画能力
3. **QFluentWidgets 不值得引入**：与现有 token/QSS 体系冲突，迁移成本高于收益
4. **Web 方案不适用**：桌面同步工具不需要跨平台，Electron/Tauri 增加了 50MB+ 运行时开销

**唯一可考虑的局部引入**：如果后续需要复杂数据可视化（如实时同步拓扑图），可评估 `QWebEngineView` 嵌入一个小型 D3.js/ECharts 组件，但仅限 Dashboard 的图表区域，不扩展到全页面。

---

## 2. 全局页面重构原则

### 2.1 架构分层

```
┌─────────────────────────────────────────────┐
│  KingdeeSyncGUI (shell)                      │
│  - 导航栏、标题栏、窗口行为                    │
│  - 页面注册与切换                              │
├─────────────────────────────────────────────┤
│  Pages (6 个)                                │
│  - 页面编排、服务调用、状态更新                  │
│  - 通过 Win11PageScaffold 构建骨架             │
├─────────────────────────────────────────────┤
│  Components (公共)                            │
│  - 无业务逻辑的 UI 原子/分子组件                │
│  - 通过 ui property 接受 QSS 皮肤              │
├─────────────────────────────────────────────┤
│  Design Tokens + QSS                         │
│  - 唯一颜色/间距/尺寸/字体来源                  │
│  - styles.css 集中管理                         │
├─────────────────────────────────────────────┤
│  Services / Workers                          │
│  - 数据获取、同步、调度等业务逻辑                │
│  - 页面不直接操作数据库                         │
└─────────────────────────────────────────────┘
```

### 2.2 页面模板统一

每个页面遵循同一骨架（`Win11PageScaffold`）：

```
┌──────────────────────────────────────┐
│  Hero Card (标题 + 状态标签 + 操作按钮) │
├──────────────────────────────────────┤
│  Primary Action Bar (主操作按钮区)      │
├──────────────────────────────────────┤
│  Summary Strip (统计卡片区)            │
├──────────────────────────────────────┤
│  Content Host (页面主体内容)            │
│  ┌─────────────┬───────────────────┐ │
│  │  左侧面板    │  右侧内容区       │ │
│  │  (配置/筛选) │  (表格/日志/图表) │ │
│  └─────────────┴───────────────────┘ │
└──────────────────────────────────────┘
```

### 2.3 重构纪律

| 规则 | 说明 |
|------|------|
| 逐页重构 | 每次只重构一个页面，完成后再做下一个 |
| 行为不变 | 重构只改 UI 结构，不改数据流、业务逻辑、API 调用 |
| 测试先行 | 重构前补充该页面的快照测试，重构后测试必须通过 |
| Token only | 新组件/页面不允许新增裸 hex、裸像素、内联 setStyleSheet |
| 1366×768 | 每个页面必须在此分辨率下完整可用 |

---

## 3. 页面级重构方案

### 3.1 Dashboard（运营总览）✅ 已完成

**重构前**：Phase 0 基线约 625 行
**重构后**：主页面已降至 526 行，拆出 3 个页面私有子组件和 1 个通用 DataTable

**实际提取**：
- `DashboardStatusCards`（59 行）— 状态卡片区
- `DashboardCharts`（95 行）— 趋势图 + 体积图 + 范围按钮
- `DashboardFailTable`（32 行）— 失败表单表
- `DataTable`（55 行）— 通用最小表格组件

**验证结果**：128 passed，1366×768 集成测试通过，行为回归无问题。
**样板文档**：`docs/dashboard-refactor-pattern.md`

### 3.2 Sync（同步执行）✅ 已完成

**重构前**：623 行（Phase 0 基线）
**重构后**：主页面已降至 607 行，提取 1 个页面私有子组件

**实际提取**：
- `SyncProgressCard`（48 行）— 进度条 + 状态文本（继承 QFrame，`ui="win11-progress-card"`）

**已迁移组件**（此前阶段完成）：
- `FieldRow` — 配置行
- `MetricCard` — 执行指标卡
- `LogPanel` — 日志面板

**验证结果**：157 passed，1366×768 集成测试通过，on_sync_progress/on_sync_finished 行为回归无问题。

### 3.3 Schedule（调度管理）

**当前状态**：574 行，含调度配置、状态面板、日志区、预设按钮

**重构方向**：
- 日志区已迁移 `LogPanel`，保持不变
- 状态面板（运行状态 + 最近执行信息）提取为 `ScheduleStatusPanel` 组件
- 预设按钮区域提取为 `PresetButtonGroup` 组件
- 响应式已 token 化，保持不变

**预期效果**：574 行 → ~400 行主文件 + 2 个 ~60 行子组件

### 3.4 Settings（系统设置）✅ 轻量完成

**当前状态**：271 行，最简洁的页面
**已迁移**：FieldRow（配置行）、token 化布局
**结论**：无需进一步拆分，标记轻量完成。

### 3.5 Forms（表单配置）✅ 轻量完成

**当前状态**：299 行，含表单列表、筛选、批量操作
**已迁移**：StatusChip（hero badge）、token 化布局
**结论**：提取 FormListCard 收益有限，标记轻量完成。

### 3.6 History（历史记录）✅ 已完成

**重构前**：370 行（Phase 0 基线）
**重构后**：主页面已降至 254 行，拆出 2 个页面私有子组件，复用 1 个通用 DataTable

**实际提取**：
- `HistoryFilterPanel`（107 行）— 筛选区（搜索 + 时间范围 + 状态 + 类型 + 响应式布局）
- `HistoryPaginationCard`（68 行）— 分页区（上一页/下一页/跳转/页码信息）
- `DataTable`（55 行）— 复用 Dashboard 提取的通用表格

**验证结果**：147 passed，1366×768 集成测试通过，行为回归无问题。

---

## 4. 公共组件规划

### 4.1 现有组件（已封装）

| 组件 | 文件 | 状态 |
|------|------|------|
| Win11PageScaffold | page_shell.py | ✅ 成熟 |
| Win11SectionCard | page_shell.py | ✅ 成熟 |
| Win11SummaryCard | page_shell.py | ✅ 成熟 |
| LoadingButton | buttons.py | ✅ 成熟 |
| SwitchButton | buttons.py | ✅ 成熟 |
| SearchableComboBox | combobox.py | ✅ 成熟 |
| StateWidget | states.py | ✅ 成熟 |
| StatusChip | common.py | ✅ 新增 |
| MetricCard | common.py | ✅ 新增 |
| LogPanel | common.py | ✅ 新增 |
| FieldRow | common.py | ✅ 新增 |
| ActionBar | common.py | ✅ 新增 |

### 4.2 待封装组件（按优先级）

| 优先级 | 组件 | 用途 | 状态 |
|--------|------|------|------|
| ~~P1~~ | ~~DataTable~~ | 统一表格 | ✅ 已完成 `components/data_table.py` |
| ~~P2~~ | ~~SyncProgressCard~~ | 同步进度条 | ✅ 已完成 `pages/_sync_progress_card.py` |
| ~~P2~~ | ~~ScheduleStatusPanel~~ | 调度运行状态 | ✅ 已完成 `pages/_schedule_status_panel.py` |
| ~~P2~~ | ~~PresetButtonGroup~~ | 快捷预设按钮组 | ✅ 已完成 `pages/_schedule_preset_buttons.py` |
| P3 | **FilterBar** | 统一筛选栏（搜索 + 下拉 + 按钮） | 按需治理，暂缓 |

**说明**：FilterBar 暂不提取，History 页面已通过 HistoryFilterPanel 解决页面级筛选需求。后续如有多个页面需要统一筛选栏，再按需治理。

### 4.3 组件设计约束

| 约束 | 说明 |
|------|------|
| 无业务逻辑 | 组件只负责 UI 渲染和交互事件发射，不调用 service |
| 接收 props | 通过构造函数参数和 setter 方法配置，不读取全局状态 |
| 信号驱动 | 通过 Qt Signal 通知外部，不直接回调页面方法 |
| Token only | 所有尺寸/颜色/间距必须来自 design_tokens.py |
| QSS skinned | 通过 `setProperty("ui", ...)` 接受 QSS 皮肤 |

---

## 5. 第一阶段实施计划

### 5.1 样板页选择：Dashboard

**选择理由**：
1. **覆盖面最广**：包含 MetricCard、图表、DataTable 等多种组件类型
2. **当前较臃肿**：625 行，拆分收益大
3. **视觉冲击最强**：Dashboard 是用户看到的第一个页面，重构效果最直观
4. **业务逻辑独立**：只读取数据，不触发写操作，重构风险最低

### 5.2 实施步骤

```
Phase 0: 准备（1 天）
├── 补充 Dashboard 现有 GUI 测试覆盖
├── 确认 1366×768 下所有断言通过
├── 定义 DataTable 最小接口（columns / rows / empty_state / set_data / clear / ui property）
│   - 第一版只覆盖 Dashboard 失败表单表所需能力
│   - 不做排序、分页、复杂加载态，避免过度设计
│   - History 页面后续再扩展分页和筛选
└── 创建 Dashboard 重构检查清单和测试清单

Phase 1: 提取 DashboardStatusCards（1 天）
├── 从 dashboard_page.py 提取状态卡片区
├── 创建 pages/_dashboard_status_cards.py 或 components/ 内
├── 页面通过组件接口更新数据
└── 测试：卡片实例化、数据更新、token 使用

Phase 2: 提取 DashboardCharts（1 天）
├── 提取图表区（趋势图 + 体积图 + 时间范围选择器）
├── 保持现有图表组件不变
├── 响应式：宽屏双列、窄屏垂直
└── 测试：图表实例化、数据绑定、响应式布局

Phase 3: 提取 DashboardFailTable + DataTable（1.5 天）
├── 实现最小 DataTable 组件（components/data_table.py）
├── 从 dashboard_page.py 提取失败表单表，接入 DataTable
├── DataTable 包含空态显示
└── 测试：DataTable 实例化、空态、数据填充、token 使用

Phase 4: 集成验证（0.5 天）
├── Dashboard 页面重构后集成测试
├── 1366×768 分辨率验证
├── 全量 GUI 测试通过
└── git diff --check clean

Phase 5: 样板文档（0.5 天）
├── 记录重构模式和组件提取规范
├── 为后续页面重构提供模板
└── 更新 frontend-guidelines.md
```

### 5.3 验收标准 ✅ 全部通过

| 检查项 | 标准 | 结果 |
|--------|------|------|
| GUI 测试 | `python -m pytest tests/test_gui_windows11_shell.py` 全部通过 | 128 passed ✅ |
| Token 使用 | Dashboard 页面无裸 hex、无内联 setStyleSheet | ✅ |
| QSS 护栏 | `Win11CssTokenGovernanceGuardTests` 4 个测试通过 | ✅ |
| 分辨率 | 1366×768 下所有主操作区和内容容器可见 | ✅ |
| 行为不变 | 刷新数据、图表渲染、失败表单显示行为与重构前一致 | ✅ |
| 代码量 | 主页面已降至 526 行 | ✅ |

---

## 6. 后续页面重构顺序

Dashboard 样板已完成（Phase 0-5），按以下顺序继续：

| 顺序 | 页面 | 状态 | 重点 |
|------|------|------|------|
| 1 | Dashboard | ✅ 已完成 | 样板页，建立重构模式 |
| 2 | History | ✅ 已完成 | 复用 DataTable，提取 FilterPanel + PaginationCard |
| 3 | Sync | ✅ 已完成 | 提取 SyncProgressCard，日志/指标/配置已迁移 |
| 4 | Schedule | ✅ 已完成 | 提取 ScheduleStatusPanel + PresetButtonGroup，日志/配置已迁移 |
| 5 | Forms | ✅ 轻量完成 | StatusChip + token 化布局，不提取 FormListCard |
| 6 | Settings | ✅ 轻量完成 | FieldRow + token 化布局，已最简洁 |

全部页面已完成。

### History 页面重构 ✅ 已完成

**最终拆分结构**：
- `history_page.py`（254 行）— 页面主文件
- `_history_filter_panel.py`（107 行）— 筛选面板
- `_history_pagination_card.py`（68 行）— 分页控件
- `DataTable`（55 行）— 复用通用表格

**验证**：147 passed，1366×768 集成测试通过，行为回归无问题。

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 组件提取后行为回归 | 中 | 高 | 测试先行，逐个组件提取 |
| 1366×768 布局溢出 | 低 | 高 | 每个组件提取后立即验证 |
| QSS 样式丢失 | 低 | 中 | 保持 `ui` property 不变，QSS selector 不改 |
| 性能下降 | 低 | 低 | Widget 嵌套层级增加有限，Qt 布局引擎足够 |
| 业务逻辑耦合 | 中 | 中 | 组件只做 UI，数据通过 setter/Signal 传递 |
