# Comet Design Handoff

- Change: redesign-gui-icons
- Phase: design
- Mode: compact
- Context hash: e2eda34743412154853e026a2b12ff86be04fc6255455b54bf81578d5383dac5

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/redesign-gui-icons/proposal.md

- Source: openspec/changes/redesign-gui-icons/proposal.md
- Lines: 1-31
- SHA256: c60822bf25985814387e44835410390fd2436457f0e0cf71c0dd1a68b033bbf0

```md
## 为什么

当前 GUI 已经在侧边栏导航、顶部操作、仪表盘指标、诊断、表单、数据源、计划任务、历史记录、日志中心、设置、任务管理等页面大量使用图标，但图标来源分散：部分来自 SVG 文件，部分来自页面本地映射，部分来自 CSS，部分来自手绘 fallback。结果是渲染质感、线条粗细、对齐、状态色和尺寸不一致，影响整体桌面端专业感。

本变更要为所有 GUI 页面重做图标体系，使图标更清晰、更统一、更易维护，同时不改变同步业务逻辑、数据库逻辑和页面工作流。

## 变更内容

- 为 PySide6 桌面 GUI 引入统一的图标视觉体系。（原因：解决多页面图标风格不一致的问题）
- 重做页面导航、工具栏动作、指标/状态、空状态/错误状态、表单/卡片等图标集合。（原因：覆盖用户能看到的主要图标入口）
- 将分散的页面本地图标选择迁移到可复用的图标 token 或集中注册表。（原因：减少重复映射并便于测试覆盖）
- 保持现有页面布局和业务流程不变，仅改善图标渲染、尺寸、对齐、颜色状态、禁用/悬停/选中态。（原因：降低视觉改造对功能逻辑的影响）
- 补充图标资产存在性、页面覆盖、视觉一致性、打包资产包含关系的验证。（原因：防止开发环境可见但打包后缺失）
- 不引入同步行为、数据库行为、运行配置的破坏性变更。（原因：本变更目标限定为 GUI 图标体验）

## 能力范围

### 新增能力

- `gui-icon-system`：覆盖桌面 GUI 的统一图标语言、资产注册、渲染规则、页面覆盖和验证要求。

### 修改能力

- 无。

## 影响范围

- 受影响 UI 资产：`assets/icons/`、`assets/styles.css`，以及必要时与桌面窗口标题一致的图标资产。（原因：这些位置承载当前图标渲染）
- 受影响 GUI 代码：`src/gui/kingdee_sync_gui.py`、`src/gui/components/` 公共组件、`src/gui/pages/` 页面模块。（原因：这些位置存在图标加载、映射和展示逻辑）
- 受影响测试：GUI shell、导航、图标尺寸、资产覆盖、打包资产检查和截图/人工视觉验证。（原因：全页面图标重做需要覆盖回归风险）
- 打包影响：`kingdee_sync.spec` 需继续包含重做后的图标资产和配置 JSON 文件。（原因：保证打包产物运行时能解析图标）
```

## openspec/changes/redesign-gui-icons/design.md

- Source: openspec/changes/redesign-gui-icons/design.md
- Lines: 1-47
- SHA256: b48ce81be72010dfd79c7bb05593e7a0136060537ed708a2ba39a7d189206fc7

```md
## 背景

本项目是 PySide6 桌面工具，整体采用 Windows 11 风格外壳。当前图标来自多个来源：`assets/icons/*.svg`、CSS 图片规则、`QIcon` 文件加载、页面本地字典，以及 `_make_nav_icon` 等手绘 fallback。现有测试已经覆盖了部分导航图标文件和 CSS 图标使用，但图标体系随着页面扩展变得不够统一。

用户反馈是“GUI 页面图标渲染不太好看”，并明确范围是“所有页面”。因此本变更是跨页面视觉系统改造，不应改变金蝶同步、SQL Server 写入、checkpoint、日志等业务行为。

## 目标 / 非目标

**目标：**

- 建立一套统一的 GUI 图标语言：线条粗细、几何风格、光学留白、颜色状态和尺寸 token 保持一致。（原因：提升全页面视觉一致性）
- 覆盖侧边栏导航、标题栏/顶部操作、页面工具栏、仪表盘指标、状态卡片、诊断、表单/配置卡片、计划/历史/日志/任务管理控件、空状态和错误状态。（原因：这些是用户主要可见图标区域）
- 优先使用真实可复用 SVG 资产和共享图标查找助手，减少临时手绘和页面本地一次性图标。（原因：避免同类 UI 结构重复超过 2 次）
- 保持现有工作流、页面结构和文案基本不变，仅在图标与标签配对需要对齐时做小范围调整。（原因：控制变更范围）
- 保持打包产物兼容。（原因：桌面应用必须在 PyInstaller 环境中稳定加载资产）

**非目标：**

- 不重做整套 GUI 布局、间距系统或配色方案。（原因：本变更聚焦图标，不扩大到完整 UI 改版）
- 不改变同步逻辑、数据库逻辑、OpenSpec 流程或打包机制，仅在必要时确认图标资产包含关系。（原因：避免影响采购入库单等已验证链路）
- 不默认引入运行时 Web 图标库依赖，除非后续实现证明本地 SVG 方案不可行。（原因：优先复用现有 PySide6 与本地资产能力）

## 设计决策

1. 使用本地 SVG 资产作为主要图标来源。

   备选方案包括继续保留 QPainter 手绘图标、引入字体图标、生成栅格图片。推荐本地 SVG，因为 PySide6 已支持加载 SVG，当前打包流程已包含 `assets`，并且 SVG 在 16-24 px 场景下更清晰。（原因：复用现有框架能力并保证高 DPI 清晰度）

2. 先建立共享图标注册表或 token 映射，再替换页面图标。

   注册表应覆盖 page id、常用 action、metric/status tone 和 fallback 名称。这样测试可以直接审计覆盖率，页面无需各自维护重复字典。（原因：降低全页面迁移时的遗漏风险）

3. 将图标重做视为“资产与系统迁移”，不是逐页布局重写。

   实现应优先更新图标文件、查找路径和共享组件；只有页面硬编码图标或手动渲染导致不一致时才改页面代码。（原因：减少无关 UI 重构和行为回归）

4. 保留应急 fallback，但不能作为正常视觉路径。

   如果资产缺失，fallback 可以避免窗口崩溃；但测试应在打包前发现必需资产缺失。（原因：兼顾稳定性和视觉质量）

## 风险 / 权衡

- [风险] 全页面触达容易产生大 diff。缓解方式：先集中映射，再只迁移必须改的调用点。（原因：控制审阅和回归成本）
- [风险] 图标在普通态好看，但选中、禁用、警告等状态下可读性不足。缓解方式：明确状态色规则并截图核对代表页面。（原因：桌面 GUI 需要在不同状态下保持辨识度）
- [风险] 现有测试可能断言具体文件名。缓解方式：将测试调整为注册表覆盖和资产存在性断言，除非文件名本身是稳定契约。（原因：避免测试绑定旧图标资产）
- [风险] 打包后缺少新增资产。缓解方式：资产放在 `assets/icons/`，并验证 `kingdee_sync.spec` 输出。（原因：PyInstaller 资产缺失通常只在运行时暴露）
- [风险] 用户期望更有表现力的图标风格，而不是克制的系统刷新。缓解方式：在 Comet 设计阶段先确认视觉方向，再进入实现。（原因：视觉口味需要前置对齐）
```

## openspec/changes/redesign-gui-icons/tasks.md

- Source: openspec/changes/redesign-gui-icons/tasks.md
- Lines: 1-24
- SHA256: e3c23859367ffff5646f42e8d63d33cb680d7a9c69ede789838038b2d7efe1b5

```md
## 1. 图标盘点与方向确认

- [ ] 1.1 盘点 `src/gui/`、`assets/styles.css` 和现有 GUI 测试中的所有图标调用点。（原因：避免漏掉页面局部图标）
- [ ] 1.2 定义目标图标视觉语言：线条粗细、画布尺寸、圆角、留白、状态色、页面/动作分类。（原因：先统一规则再批量替换）
- [ ] 1.3 决定哪些现有图标文件可保留、哪些需要替换、哪些新图标名称需要新增。（原因：减少无意义资产 churn）

## 2. 共享图标系统

- [ ] 2.1 新增或更新共享 GUI 图标注册表/助手，覆盖 page id、常用 action、metric/status tone 和 fallback 行为。（原因：集中管理全页面图标选择）
- [ ] 2.2 替换 `assets/icons/` 下低质或不一致的主要 SVG 资产。（原因：从源头改善渲染质量）
- [ ] 2.3 确保图标尺寸复用现有 `SizeTokens`，状态色与 Windows 11 shell 样式保持一致。（原因：避免产生第二套视觉 token）

## 3. 页面集成

- [ ] 3.1 将侧边栏导航和顶部操作图标迁移到共享图标系统。（原因：这是最核心的全局入口）
- [ ] 3.2 迁移仪表盘、同步、计划任务、表单、诊断、日志中心、历史记录、数据源、设置、任务管理等页面图标。（原因：满足“所有页面”范围）
- [ ] 3.3 在真实资产已覆盖时移除或降级手绘图标，同时保留安全 fallback。（原因：提升正常路径质量并保留异常容错）

## 4. 验证

- [ ] 4.1 新增/更新图标注册表覆盖、资产存在性、导航/页面图标映射测试。（原因：让缺失资产在测试阶段失败）
- [ ] 4.2 运行 GUI 相关测试，覆盖导航、图标尺寸、CSS 图标规则和页面构造。（原因：验证图标改造未破坏窗口初始化）
- [ ] 4.3 截图或检查主要 GUI 页面并记录视觉结论。（原因：图标质量不能只靠单元测试判断）
- [ ] 4.4 验证 PyInstaller 打包仍包含重做后的图标资产。（原因：确保发布产物可用）
```

## openspec/changes/redesign-gui-icons/specs/gui-icon-system/spec.md

- Source: openspec/changes/redesign-gui-icons/specs/gui-icon-system/spec.md
- Lines: 1-45
- SHA256: 54096728250d6baef5e15053d0b26e23e5e95d995dce997e27ea720deee0402e

```md
### Requirement: Unified GUI Icon System

系统 SHALL 为所有桌面 GUI 页面提供统一的图标视觉语言，覆盖导航、工具栏动作、指标/状态卡片、表单/配置卡片、诊断、计划任务、历史记录、日志中心、设置、任务管理和同步页面。

#### Scenario: 所有主要 GUI 表面使用同一图标风格
- **WHEN** 用户在 GUI 页面之间切换
- **THEN** 图标 SHALL 在描边粗细、圆角处理、光学尺寸、留白和颜色行为上保持一致
- **AND** 主要导航或页面级控件 SHALL NOT 继续使用明显不匹配的旧图标资产。

#### Scenario: 图标状态保持可读
- **WHEN** 图标处于普通、悬停、选中、禁用、成功、警告、危险或中性状态
- **THEN** 图标 SHALL 在对应背景上保持清晰可辨
- **AND** 状态色 SHALL 与现有 Windows 11 shell 主题 token 对齐。

### Requirement: Centralized Icon Selection

系统 SHALL 对 page id、action id、status/metric tone 的图标选择进行足够集中化管理，使开发者无需逐页搜索即可审计覆盖情况。

#### Scenario: 导航图标覆盖完整
- **WHEN** 测试检查 GUI 页面顺序配置
- **THEN** 每个 page id SHALL 映射到存在的图标资产或已注册图标 token
- **AND** 缺失文件 SHALL 在打包前通过测试失败暴露。

#### Scenario: 页面局部图标被明确映射
- **WHEN** 页面需要指标、状态或动作图标
- **THEN** 页面 SHALL 在可行时使用共享图标名称/token
- **AND** 页面专用图标 SHALL 仍放入公共图标资产集合。

### Requirement: Packaged Icon Assets

打包后的桌面应用 SHALL 包含 GUI 所需的重做后图标资产。

#### Scenario: PyInstaller 构建包含图标资产
- **WHEN** 应用被打包
- **THEN** 所有必需 SVG/PNG/ICO 图标资产 SHALL 出现在打包产物的 `_internal/assets` 树下
- **AND** 运行时 GUI 代码 SHALL 能解析这些资产，不应在正常路径退回低质量生成图标。

### Requirement: Visual Regression Evidence

本变更 SHALL 包含重做后图标在 GUI 中正确渲染的验证证据。

#### Scenario: GUI 图标截图被核对
- **WHEN** 执行图标重做验证
- **THEN** 验证 SHALL 捕获或检查覆盖导航、仪表盘、同步、计划任务、表单、诊断、日志中心、历史记录、数据源、设置、任务管理的代表屏幕
- **AND** 验证报告 SHALL 记录剩余视觉风险或明确排除项。
```

