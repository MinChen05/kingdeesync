# 金蝶同步运维工作台重构设计

## 目标

将金蝶数据同步系统重构为高密度运维工作台，并将 Go REST API 演进为版本化、强类型的资源契约。保留金蝶 Cloud API 到 Go 同步引擎再到 Doris 的数据处理链路、所有现有同步能力以及六个业务领域；允许重设计前端视觉、前端模块和 REST 路由。

## 非目标

- 不修改金蝶 Cloud API、Doris schema 或同步引擎的业务语义。
- 不引入新的 UI 组件库、GraphQL、服务端渲染或额外后端服务。
- 不保留旧 API 作为长期兼容层；仅在本次迁移期间保留，切换完成后删除。

## 体验与信息架构

前端采用深色高密度运维控制台：碳灰背景、青绿色健康状态、琥珀色告警、红色故障，页面使用紧凑数据表、状态带和固定宽度的操作工具栏。Ant Design 6 与 Pro Components 继续承载表格、抽屉、表单和反馈组件；新增的视觉规则集中在主题 token 和共享样式中。

保留 `/overview`、`/sync`、`/schedule`、`/data`、`/monitor`、`/system` 六条路由。概览页优先展示系统可用性、当前运行、待处理风险和吞吐趋势；同步页围绕运行创建、实时进度与事件；监控页围绕运行历史、详情与异常；其余页面分别管理调度、表单与数据源、系统配置与诊断。

## API 架构

新增 `/api/v1` 路由组。成功响应使用 `{ "data": T, "meta"?: M }`；失败响应使用 `{ "error": { "code": string, "message": string, "details"?: object } }`。HTTP 状态码表达请求结果，前端不再依赖 `ok` 布尔字段。

### 资源与命令

| 领域 | 新接口 | 用途 |
| --- | --- | --- |
| 概览 | `GET /api/v1/overview` | 返回 KPI、系统健康度、活跃运行、趋势、风险和近期运行的聚合读模型。 |
| 同步运行 | `POST /api/v1/runs` | 创建一次同步，入参为 `forms`、`sync_type`、`dry_run`。 |
| 同步运行 | `GET /api/v1/runs`、`GET /api/v1/runs/:runId` | 分页查询运行与单次运行详情、表单统计。 |
| 运行事件 | `GET /api/v1/runs/:runId/events` | 查询脱敏后的事件，支持级别、游标和限制。 |
| 运行取消 | `POST /api/v1/runs/:runId/actions/cancel` | 请求优雅取消；返回更新后的运行状态。 |
| 调度 | `GET/POST /api/v1/schedules`、`GET/PUT/DELETE /api/v1/schedules/:id` | 查询与管理定时任务。 |
| 调度器 | `GET /api/v1/scheduler`、`POST /api/v1/scheduler/actions/:action` | 查询、启动、暂停、恢复或停止调度器。 |
| 表单 | `GET /api/v1/forms`、`PATCH /api/v1/forms/:formName` | 查询与修改可同步表单。 |
| 数据源 | `GET /api/v1/data-sources`、`POST /api/v1/data-sources/:id/actions/test` | 查询脱敏配置与连接诊断。 |
| 系统 | `GET/PUT /api/v1/system/config` | 读取与更新允许在线调整的配置。 |
| 诊断 | `GET /api/v1/system/diagnostics` | 返回金蝶、Doris、运行环境和近期风险。 |
| 维护 | `POST /api/v1/system/actions/archive-history` | 按保留天数清理历史。 |

分页参数统一为 `page`、`page_size`；筛选统一使用 `from`、`to`、`status`、`sync_type`、`form_name`。`runId` 使用已有 UUID 字符串，调度 ID 使用整数。写请求按现有 `X-Deploy-Key` 保护策略继续校验。

每个 v1 handler 依赖 `internal/api/contract` 的请求、响应与错误类型；handler 仅做绑定、校验、HTTP 映射和序列化，保持同步引擎、调度器、数据源服务与存储层的职责不变。敏感字段与事件信息延续现有脱敏策略。

## 前端架构

`src/services/api.ts` 按 v1 资源组织，服务端生成或手写的 TypeScript 类型与 Go contract 一一对应。删除页面内的 `Record<string, unknown>`、`any` 和不安全断言，解析边界只保留在 API 层。

每个页面 `hooks.ts` 负责 React Query 的 query key、轮询、mutation、缓存失效和从 API 响应到领域数据的映射。页面入口只组合 Hook、页面状态和展示组件；筛选栏、指标区、表格、运行详情、配置区与操作区各自为可测试组件。出现至少三次且稳定的逻辑才提升至 `src/components`。

新增 `QueryResult<T>` 统一渲染 pending、error、empty 和 success；调用方提供成功内容及必要的重试动作。`ErrorForms` 合并为共享组件，用稳定的 `ErrorForm` 类型、可选数量和上下文文案覆盖 Overview 与 Monitor 差异。颜色、边框、文字和状态语义收敛到 Ant Design 主题 token 与本地 CSS 变量，组件不得直接硬编码暗色色值。

## 数据流与错误处理

页面首次查询通过 `/api/v1` 读取所需资源；Overview 只请求一个聚合读模型。活跃运行每三秒轮询详情，运行事件按当前页面可见性轮询；终态自动停止轮询。成功的命令 mutation 失效受影响资源和 Overview query，避免局部复制服务端状态。

请求失败由 API 层转换为携带 `code`、`message` 与 HTTP 状态的错误对象。`QueryResult` 显示可理解的错误和重试入口；`409` 同步冲突应显示当前运行并跳转或绑定该运行，`400` 显示字段校验结果，`401/403` 显示部署密钥权限错误，`5xx` 显示不可用状态且保留刷新能力。日志与错误详情不得呈现密码、Token 或 URL 凭据。

## 迁移顺序

1. 在 Go 中定义 v1 contract、响应写入器与测试，并新增 v1 routes；旧 routes 暂不删除。（原因：可用并行契约验证降低切换风险）
2. 建立前端 v1 service、精确类型、QueryResult、共享 ErrorForms 和主题 token。（原因：先提供页面重构所需稳定基础）
3. 重写 Overview、Sync、Monitor、Schedule、Data、System 的页面组成与高密度视觉，并按职责拆分组件。（原因：页面切换可逐页验证）
4. 前端完全切至 v1 后删除旧服务方法与旧 Go routes，更新 OpenAPI/API 文档。（原因：避免双契约长期漂移）
5. 执行完整前后端验证和浏览器视觉检查。（原因：确保行为、契约与呈现均可回归）

## 测试与验收

Go 测试覆盖 v1 成功、参数错误、同步冲突、资源不存在、取消运行、分页、脱敏与写保护。前端测试覆盖每个页面 Hook 的查询、轮询和失效，`QueryResult` 的四种状态，合并 `ErrorForms` 的两种上下文，以及核心命令操作。最后执行 `npm run lint`、`npm test`、`npm run build` 与 `go test ./...`；在桌面和移动视口以浏览器检查六个页面，确认页面无重叠、溢出或空白状态。

## 风险与缓解

API 迁移会同时影响前后端，使用新增 v1 再删除旧路径的顺序限制不可用窗口。Overview 聚合接口可能产生较高查询负担，服务层应一次读取可复用数据并对单次读取设置超时。配置与维护操作属于写操作，继续受部署密钥保护并对输入执行边界校验。实时状态使用短轮询而不是新引入 WebSocket，避免额外连接生命周期与部署复杂度。
