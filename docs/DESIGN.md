# 金蝶数据同步工具 - GUI 重设计方案

> 面向长期 Web 化（Tauri + Python 后端），严格对齐 Meta 设计系统。

## 一、总体定位

- 应用名称：金蝶数据同步工具（Kingdee Sync Tool）
- 形态：桌面 Web 应用（后续使用 Tauri 打包），内嵌 Python 同步服务作为后端。
- 核心目标：
  - 提供清晰、可控的数据同步操作入口
  - 提供直观的同步历史与统计视图
  - 使用 Meta 风格设计系统，保持简洁、卡片化、数据优先的视觉语言

## 二、技术架构（高层）

- 前端：
  - Web 技术栈（HTML/CSS/JS + 任意现代框架）
  - 使用 Tauri 打包为桌面应用，支持本地文件系统与进程通信
- 后端：
  - 现有 Python 同步逻辑封装为 HTTP API（如 FastAPI）
  - 对外暴露：同步控制、配置管理、历史查询、统计查询、诊断等接口
- 通信：
  - 前端通过 REST/JSON 调用后端 API
  - Tauri 环境下可走 localhost HTTP 或 Tauri Command 桥接

## 三、设计系统映射（基于 Meta DESIGN.md）

### 颜色使用策略

- 页面背景：`{colors.canvas}`（#ffffff）
- 卡片背景：`{colors.canvas}`，边框 `{colors.hairline-soft}`
- 主文字：`{colors.ink-deep}` / `{colors.ink}`
- 辅助文字：`{colors.steel}` / `{colors.slate}`
- 主要交互色：
  - 全局主按钮：`{colors.ink-button}`（黑色）
  - 核心业务操作（如“开始同步”）：`{colors.primary}`（#0064E0）
- 状态色：
  - 成功：`{colors.success}`
  - 警告：`{colors.warning}` / `{colors.attention}`
  - 错误：`{colors.critical}` / `{colors.critical-strong}`

### 排版

- 标题层级：
  - 页面标题：`{typography.heading-sm}`（24px / 500）
  - 区块标题：`{typography.subtitle-lg}`（18px / 700）
  - 正文：`{typography.body-md}`（16px / 400）
  - 辅助说明：`{typography.body-sm}`（14px / 400）
- 按钮文字：`{typography.button-md}`（14px / 700）

### 圆角与卡片

- 按钮、标签、Tab：`{rounded.full}`（100px）
- 普通功能卡片：`{rounded.xl}`（16px）或 `{rounded.xxl}`（24px）
- 重要展示卡片（如统计概览）：`{rounded.xxxl}`（32px）

### 间距

- 页面内边距：`{spacing.xxl}`（32px）
- 区块间距：`{spacing.section}`（64px）或 `{spacing.section-sm}`（48px）
- 卡片内边距：`{spacing.xxl}`（32px）
- 列表项间距：`{spacing.base}`（16px）

## 四、全局布局

### 整体布局结构

- 顶部：Promo Banner（可选）+ 导航栏
- 左侧：固定导航菜单（页签）
- 右侧：主内容区（各页面）

### 顶部导航栏（Top Nav）

- 背景：`{colors.canvas}`，底部边框：1px `{colors.hairline-soft}`
- 左侧：
  - 应用名称/Logo（文字：“金蝶数据同步工具”）
- 中间：
  - 页面导航 Pill Tab（如：概览 / 同步 / 历史 / 统计 / 表单 / 设置）
- 右侧：
  - 状态指示：
    - 同步状态（空闲 / 同步中 / 异常）
    - 最后同步时间
  - 操作：
    - 诊断按钮（小图标圆形按钮）
    - 设置入口（小图标圆形按钮）

### 左侧导航（可选）

- 若页面较多，可使用左侧固定导航，顶部仅保留 Logo + 全局状态
- 导航项使用 `{typography.body-sm-bold}`，选中态背景 `{colors.surface-soft}`，圆角 `{rounded.lg}`

## 五、页面规划总览

主要页面：
1. 概览页（Dashboard）
2. 同步页（Sync）
3. 历史页（History）
4. 统计页（Statistics）
5. 表单管理页（Forms）
6. 设置页（Settings）
7. 诊断页（Diagnostics）

## 六、各页面详细设计

### 1) 概览页（Dashboard）

**目标：**
- 一眼看到当前同步健康状况、今日同步概况、最近问题。

**布局结构：**
- 顶部：
  - 页面标题：“同步概览”（`{typography.heading-sm}`）
  - 右侧：时间范围选择器（今天 / 近7天 / 近30天），使用 Pill Tab
- 第一行：状态卡片（3–4 个）
  - 卡片样式：`{card-icon-feature}`
  - 内容：
    - 今日同步次数（sync_count）
    - 今日同步记录数（sync_records）
    - 今日成功率（success_rate）
    - 异常任务数（fail_count）
  - 每个卡片：
    - 顶部：指标名称（`{typography.body-sm-bold}`）
    - 中间：数值（`{typography.heading-sm}`）
    - 底部：与昨日对比（↑↓ + 百分比，`{typography.caption}`，颜色按涨跌）
- 第二行：趋势图表
  - 卡片样式：`{card-product-feature}`
  - 标题：“近 7 天同步趋势”
  - 内容：折线/柱状图
    - X 轴：日期
    - Y 轴左侧：同步次数
    - Y 轴右侧（可选）：成功率
- 第三行：最近失败/异常
  - 卡片样式：`{card-product-feature}`
  - 标题：“最近异常”
  - 内容：列表
    - 每行：时间 + 表单名 + 错误摘要 + 状态 Badge
    - Badge：
      - failed：`{badge-critical}`
      - partial：`{badge-attention}`

**交互：**
- 点击“最近异常”的某条记录 → 跳转到历史页，并定位到对应任务。

**数据源：**
- `get_dashboard_today_stats()`
- `get_trend_7d()`
- `history_manager.get_stats()` / `sync_errors` 查询

### 2) 同步页（Sync）

**目标：**
- 让用户直观选择“同步哪些表”、“以什么模式同步”，并实时看到进度。

**布局结构：**
- 顶部：
  - 页面标题：“数据同步”
- 左侧区域：同步配置
  - 卡片样式：`{card-product-feature}`
  - 内容：
    - 同步模式：
      - Pill Tab：增量 / 全量 / 重置
    - 表单选择：
      - 可搜索多选列表（仓库、物料、销售订单等）
      - 默认选中配置中的 default_forms
    - 高级选项（折叠面板）：
      - 增量时间窗口（天）
      - 并发数（table_concurrency）
      - 是否启用 staging
- 右侧区域：执行与进度
  - 卡片样式：`{card-checkout-summary}`
  - 内容：
    - 顶部：当前状态
      - 空闲：显示“准备就绪”，主按钮：“开始同步”（`{button-buy-cta}`，`{colors.primary}`）
      - 同步中：显示进度条 + 当前同步表单 + 已用时间
      - 完成/失败：显示结果摘要 + 操作按钮（“查看详情”）
    - 中间：实时日志（可折叠）
      - 滚动日志区域，显示关键步骤和错误
    - 底部：
      - 同步中：按钮“停止同步”（`{button-secondary}`）
      - 完成后：按钮“查看历史”（`{button-ghost}`）

**交互：**
- 点击“开始同步”：
  - 调用后端 API 启动同步任务
  - 前端通过轮询或 WebSocket/SSE 获取进度
- 点击“停止同步”：
  - 调用后端 API 请求优雅停止
- 点击“查看详情”：
  - 跳转到历史页，打开对应任务详情

**数据源：**
- `config_manager.get_sync_config()`
- `config_manager.get_table_mapping()`
- `sync_service.sync_data()`
- `sync_runs` / `sync_form_stats` / `sync_errors`（进度与结果）

### 3) 历史页（History）

**目标：**
- 查看所有同步任务历史，支持按条件筛选，并查看任务级与表单级详情。

**布局结构：**
- 顶部：
  - 页面标题：“同步历史”
  - 右侧：筛选区
    - 时间范围选择器（日期区间）
    - 状态筛选（全部 / 成功 / 部分成功 / 失败）
    - 同步类型（全部 / 增量 / 全量）
    - 表单搜索框（搜索包含某表单的任务）
- 主体：
  - 卡片样式：`{card-product-feature}`
  - 内容：任务列表（表格或卡片列表）
    - 列/字段：
      - 时间（start_time）
      - 同步类型
      - 状态（带 Badge）
      - 涉及表单（forms_synced，截断显示）
      - 记录数（total_records）
      - 耗时（duration_seconds）
    - 点击某行：
      - 右侧或弹窗展示任务详情

**任务详情面板：**
- 样式：`{card-checkout-summary}` 或侧边抽屉
- 内容：
  - 基本信息：run_id、时间、类型、状态、总体说明
  - 表单级统计：
    - 列表：form_name / table_name / fetched / inserted / error / status / 耗时
  - 错误摘要：
    - 列表：form_name / error_type / error_message

**交互：**
- 支持分页（每页 20 条）
- 点击错误摘要某条 → 可展开查看详细日志（如果后端提供）

**数据源：**
- `history_manager.get_history()`
- `sync_form_stats` / `sync_errors`（按 run_id 查询）

### 4) 统计页（Statistics）

**目标：**
- 提供任务级与表级的统计视图，便于分析同步效果和问题分布。

**布局结构：**
- 顶部：
  - 页面标题：“同步统计”
  - 右侧：时间范围选择器（近7天 / 近30天 / 自定义区间）
- 第一区块：任务统计概览
  - 卡片样式：`{card-product-feature}`
  - 内容：
    - 总任务数
    - 成功任务数 / 失败任务数
    - 平均成功率
    - 平均耗时
- 第二区块：表级统计
  - 卡片样式：`{card-product-feature}`
  - 内容：表格
    - 列：
      - 表单名
      - 同步次数
      - 总拉取数（fetched）
      - 总写入数（inserted）
      - 总错误数（error）
      - 成功率
    - 支持排序（按次数、错误数、成功率）
- 第三区块：失败分布
  - 卡片样式：`{card-product-feature}`
  - 内容：
    - Top N 失败表单列表（按错误次数）
    - 可选：错误类型分布（api_error / write_error / timeout 等）

**交互：**
- 点击某表单行 → 可下钻查看该表单的历史任务列表（跳转到历史页并过滤）

**数据源：**
- `sync_runs` / `sync_form_stats` / `sync_errors`
- 后端需提供聚合接口（按时间范围、按表单汇总）

### 5) 表单管理页（Forms）

**目标：**
- 管理需要同步的表单：启用/禁用、查看映射、配置增量字段。

**布局结构：**
- 顶部：
  - 页面标题：“表单管理”
- 主体：
  - 卡片样式：`{card-product-feature}`
  - 内容：表单列表（表格）
    - 列：
      - 表单名
      - 目标表名（table_name）
      - 状态（启用/禁用）
      - 增量字段（如 FModifyDate）
      - 操作（编辑 / 查看详情）
    - 支持搜索表单名
- 编辑面板：
  - 样式：`{card-checkout-summary}` 或抽屉
  - 内容：
    - 表单名（只读）
    - 目标表名
    - 是否启用（开关）
    - 增量字段
    - 备注

**交互：**
- 修改后点击“保存” → 调用后端 API 更新配置（如 tables.json / config）

**数据源：**
- `config_manager.get_table_mapping()`
- INCREMENTAL_FIELDS 配置

### 6) 设置页（Settings）

**目标：**
- 管理连接配置、同步策略、界面偏好。

**布局结构：**
- 顶部：
  - 页面标题：“设置”
- 分区块（每个区块一个卡片）：
  - 金蝶连接设置：
    - 字段：login_url / query_url / acct_id / username / password（加密显示）
    - 按钮：“测试连接”
  - 数据库设置：
    - 类型（SQL Server / MySQL，当前默认 SQL Server）
    - 连接信息（host / database / user / password）
    - 按钮：“测试连接”
  - 同步策略：
    - auto_sync（开关）
    - sync_interval
    - sync_type（默认）
    - table_concurrency / fetch_concurrency
    - 时间窗口（time_window_days）
  - 运维与日志：
    - 记录保留天数（如 90 天）
    - 日志目录
  - 界面设置：
    - 主题（如果后续支持深色）
    - 语言（如后续支持多语言）

**交互：**
- 每个区块独立保存
- 修改连接信息后，提供“测试连接”按钮，给出明确成功/失败提示

**数据源：**
- `config_manager` 相关接口
- `sync_service.test_connections()`

### 7) 诊断页（Diagnostics）

**目标：**
- 帮助排查问题：连接状态、环境信息、最近错误摘要。

**布局结构：**
- 顶部：
  - 页面标题：“系统诊断”
- 区块：
  - 连接状态：
    - 金蝶 API：状态（成功/失败）+ 最后测试时间
    - 数据库：状态 + 版本信息
  - 环境信息：
    - Python 版本
    - 依赖版本（requests、pyodbc 等）
    - 运行模式（开发/打包）
  - 最近错误：
    - 列表：时间 / 表单 / 错误类型 / 摘要
  - 操作：
    - 按钮：“重新测试连接”
    - 按钮：“导出诊断信息”（生成 JSON/文本文件）

**数据源：**
- `sync_service.test_connections()`
- `sync_errors` / 日志文件

## 七、关键交互与状态规范

### 同步状态表示

- 空闲：
  - 状态标签：`{badge-success}` “就绪”
- 同步中：
  - 状态标签：`{badge-attention}` “同步中”
  - 显示进度条和当前表单
- 异常：
  - 状态标签：`{badge-critical}` “异常”
  - 显示简要错误信息 + “查看详情”

### 错误与提示

- 操作失败：
  - 使用 `{colors.critical-strong}` 错误提示条
  - 文案简短，可点击查看完整错误
- 成功提示：
  - 使用 `{colors.success}` 提示条，自动消失

## 八、数据流（前端 ↔ 后端）

### 典型流程

- 页面加载：
  - 前端请求：
    - `GET /api/config`
    - `GET /api/dashboard/today`
    - `GET /api/trend/7d`
    - `GET /api/forms`
- 启动同步：
  - `POST /api/sync/start`
    - body: `{ forms, sync_type }`
  - 前端轮询或订阅：
    - `GET /api/sync/status?run_id=xxx`
- 查看历史：
  - `GET /api/history?page=1&page_size=20&status=...&form=...`
  - `GET /api/history/runs/{run_id}/details`
- 查看统计：
  - `GET /api/stats/summary?from=...&to=...`
  - `GET /api/stats/forms?from=...&to=...`

## 九、与现有项目的对应关系

### 后端模块映射

- `sync_service` → `/api/sync/*`
- `history_manager` → `/api/history/*`
- `reporting` → `/api/dashboard/*` `/api/trend/*` `/api/stats/*`
- `config_manager` → `/api/config` `/api/forms`

### 数据库

- 业务表：不变
- 运维表：`sync_runs` / `sync_form_stats` / `sync_errors`（已迁移到 SQL Server）

## 十、后续实施建议（简要）

- 第一步：
  - 在现有 Python 项目中增加 FastAPI 层，暴露上述 API
  - 保持现有 CLI/GUI 可继续工作
- 第二步：
  - 开发 Web 前端（按本设计文档），调用 Python API
  - 本地以 http://localhost 方式联调
- 第三步：
  - 使用 Tauri 打包为桌面应用，替换原有 PySide6 GUI
