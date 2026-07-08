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
