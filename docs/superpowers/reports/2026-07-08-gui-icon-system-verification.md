# GUI 图标系统验证报告

## 自动化验证

- `python -m pytest tests/test_gui_icon_registry.py -q`：通过，7 passed，覆盖注册表资产存在性、`QIcon` 非空、SVG `24x24/currentColor` 规则、CSS 图标 URL 存在性、`build.bat` assets 打包规则。（原因：图标资产必须在测试阶段暴露缺失）
- `python -m pytest tests/test_gui_icon_registry.py tests/test_gui_windows11_shell.py -q -k "icon or sidebar or topbar"`：通过，13 passed，覆盖 shell、侧边栏、顶部栏、图标相关断言。（原因：验证全局入口图标未破坏 GUI 初始化）
- 页面级 smoke：通过，覆盖历史分页、任务管理指标卡、任务管理行内动作的 `icon-source` 与图标加载。（原因：这些页面存在直接 `QIcon` 路径，迁移风险较高）

## 打包验证

- 当前仓库未提交 `kingdee_sync.spec` 文件；`build_exe.bat` 引用了该文件但本次无法验证。（原因：不能验证不存在的打包规格文件）
- 实际存在的 `build.bat` 使用 `pyinstaller ... --add-data assets;assets ... main.py`，已由测试覆盖。（原因：该入口会把 `assets/icons/` 带入打包产物）

## 视觉核对

- 导航与顶部栏：图标统一走注册表，`icon-source` 标准化为 `icons/...`，聚焦 GUI 测试通过。（原因：全局入口是用户最常见视觉区域）
- 仪表盘：指标、健康状态、风险提醒、趋势下拉等图标统一走 `SvgIconLabel` 或注册表路径。（原因：仪表盘图标密度最高）
- 历史记录：分页按钮和导出按钮改为注册表加载。（原因：移除页面内直接拼接资产路径）
- 任务管理：指标卡和行内动作按钮改为注册表加载。（原因：任务管理存在多处重复动作图标）
- 其他页面：同步、计划、表单、诊断、日志中心、数据源、设置的 SVG 资产由注册表覆盖并通过资产存在性测试。（原因：保证“所有页面”至少具备统一资产规则）

## 剩余风险

- 当前环境没有执行真实交互式截图核对，视觉结论基于 Qt 构造、资产规则和 focused GUI 测试。（原因：当前自动化环境缺少稳定截图验收入口）
- 运行较宽的 `tests/test_gui_windows11_shell.py -k "dashboard or sync or schedule or forms or diagnostic or log or history or data_source or settings or task_management or icon"` 会触发 30 个既有非图标失败，主要集中在布局尺寸、历史分页、同步页旧属性、数据源健康表和计划页旧结构断言。（原因：这些失败在本次改动前已可由相关选择器触发，不作为图标重做的阻塞项）
- 导入部分 GUI 模块时会触发 SQL Server 连接预检日志，当前本地 `127.0.0.1:1433` 不可用。（原因：这是模块导入副作用，不影响图标资产测试结论）
