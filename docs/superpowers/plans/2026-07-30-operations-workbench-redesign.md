# 金蝶同步运维工作台重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供版本化 Go REST API 与高密度前端运维工作台，同时保留金蝶到 Doris 的全部同步业务能力。

**Architecture:** Go 端先以 `/api/v1` 并行引入显式 contract、错误响应和聚合读模型，再使 React Query 页面切换到 v1。前端以 `QueryResult`、主题 token、共享领域组件和页面专属 Hook 组织，页面入口只负责组合和用户操作。

**Tech Stack:** Go、Gin、GORM、React 19、Umi Max、Ant Design 6、React Query、Vitest、Testing Library、Biome。

---

## 文件结构

- `apps/server/internal/api/contract/v1.go`：v1 DTO、分页元数据与 problem 结构。
- `apps/server/api/routes/v1/`：runs、overview、schedules、resources 和 system handlers；只复用现有 service/engine。
- `apps/server/api/routes/v1/*_test.go`：Gin 路由、状态码、错误和脱敏契约测试。
- `apps/web/src/services/v1.ts`：v1 请求、API 错误解析和共享 TypeScript 类型。
- `apps/web/src/components/QueryResult.tsx`：pending、error、empty、success 统一渲染。
- `apps/web/src/components/ErrorForms.tsx`：Overview 与 Monitor 共享异常表单。
- `apps/web/src/styles/tokens.css`：运维控制台语义 token。
- `apps/web/src/pages/*/hooks.ts`：React Query 协调层；`components/`：拆分后的展示与操作区。

### Task 1: 定义 v1 通用契约与响应写入器

**Files:**
- Create: `apps/server/internal/api/contract/v1.go`
- Create: `apps/server/api/routes/v1/response.go`
- Create: `apps/server/api/routes/v1/response_test.go`

- [ ] **Step 1: 写入失败测试，固定成功、分页与 problem JSON 形状。**

```go
func TestWriteProblemUsesHTTPStatusAndStableShape(t *testing.T) {
  recorder := httptest.NewRecorder()
  context, _ := gin.CreateTestContext(recorder)
  WriteProblem(context, http.StatusConflict, contract.Problem{Code: "RUN_ALREADY_ACTIVE", Message: "同步任务正在运行"})
  require.Equal(t, http.StatusConflict, recorder.Code)
  require.JSONEq(t, `{"error":{"code":"RUN_ALREADY_ACTIVE","message":"同步任务正在运行"}}`, recorder.Body.String())
}
```

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/server && go test ./api/routes/v1 -run TestWriteProblemUsesHTTPStatusAndStableShape -count=1`

Expected: 编译失败，`WriteProblem` 未定义。

- [ ] **Step 3: 实现 contract 和 writer。**

```go
type Envelope[T any] struct { Data T `json:"data"`; Meta *PageMeta `json:"meta,omitempty"` }
type Problem struct { Code string `json:"code"`; Message string `json:"message"`; Details any `json:"details,omitempty"` }
func WriteData[T any](c *gin.Context, status int, data T) { c.JSON(status, contract.Envelope[T]{Data: data}) }
func WriteProblem(c *gin.Context, status int, p contract.Problem) { c.JSON(status, gin.H{"error": p}) }
```

`PageMeta` 固定使用 `page`、`page_size`、`total`；`v1.go` 定义 `Run`、`RunEvent`、`Overview`、`Schedule`、`Form`、`DataSource`、`Diagnostics` DTO，并复用既有 `contract.SyncStatus`。

- [ ] **Step 4: 补 data envelope 与分页 meta 测试后运行通过。**

Run: `cd apps/server && go test ./api/routes/v1 -run 'TestWrite(Data|Problem)' -count=1`

Expected: PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/server/internal/api/contract/v1.go apps/server/api/routes/v1/response.go apps/server/api/routes/v1/response_test.go && git commit -m "feat(api): add v1 response contract"`

### Task 2: 暴露 v1 运行与事件资源

**Files:**
- Create: `apps/server/api/routes/v1/runs.go`
- Create: `apps/server/api/routes/v1/runs_test.go`
- Modify: `apps/server/api/routes/sync.go`
- Modify: `apps/server/cmd/server/main.go`

- [ ] **Step 1: 写入创建、冲突、查询、取消和事件脱敏的失败测试。**

```go
func TestCreateRunReturnsCreatedResource(t *testing.T) {
  router := newV1Router(testEngine)
  request := httptest.NewRequest(http.MethodPost, "/api/v1/runs", strings.NewReader(`{"forms":["物料"],"sync_type":"full"}`))
  request.Header.Set("Content-Type", "application/json")
  response := httptest.NewRecorder(); router.ServeHTTP(response, request)
  require.Equal(t, http.StatusCreated, response.Code)
  require.JSONEq(t, `{"data":{"run_id":"run-001","status":"running"}}`, response.Body.String())
}
```

增加：重复运行返回 `409/RUN_ALREADY_ACTIVE` 且 `details.run_id`；`POST /runs/:runId/actions/cancel` 返回 `stopping`；`GET /runs/:runId/events` 不含密码与 Bearer Token。

在 `runs_test.go` 中定义 `newV1Router(engine)`：创建 `gin.New()`，调用 `InitRoutes(router, engine)`，并为测试注入与 `sync_test.go` 相同的内存/替身数据库和同步 runner；每个用例在 `t.Cleanup` 中重置 `activeTask`、`activeSync`、`lastSyncResult` 与 `syncRunner`。

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/server && go test ./api/routes/v1 -run 'Test(CreateRun|CancelRun|RunEvents)' -count=1`

Expected: FAIL，路由为 404 或 helper 缺失。

- [ ] **Step 3: 抽取可复用运行流程并注册 v1 routes。**

```go
group := engine.Group("/api/v1/runs")
group.POST("", createRun)
group.GET("", listRuns)
group.GET("/:runId", getRun)
group.GET("/:runId/events", listRunEvents)
group.POST("/:runId/actions/cancel", cancelRun)
```

`createRun` 复用当前 `startSync` 的互斥、`PrepareRun`、背景 runner 与写库流程；`cancelRun` 复用 `stopSync` 的超时和状态机；不得创建第二份 active task 状态。`listRuns`/`getRun` 使用 `gormdb` 运行记录与表单明细；事件使用现有 redact 规则。

- [ ] **Step 4: 在 `main.go` 注册 `v1.InitRoutes(r, engine)`，运行回归测试。**

Run: `cd apps/server && go test ./api/routes/... -run 'Test(CreateRun|CancelRun|RunEvents|Start|Stop|SyncLogs)' -count=1`

Expected: PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/server/api/routes/v1/runs.go apps/server/api/routes/v1/runs_test.go apps/server/api/routes/sync.go apps/server/cmd/server/main.go && git commit -m "feat(api): add v1 run resources"`

### Task 3: 实现 v1 概览、调度、表单、数据源与系统资源

**Files:**
- Create: `apps/server/api/routes/v1/overview.go`
- Create: `apps/server/api/routes/v1/schedules.go`
- Create: `apps/server/api/routes/v1/resources.go`
- Create: `apps/server/api/routes/v1/system.go`
- Create: `apps/server/api/routes/v1/resources_test.go`

- [ ] **Step 1: 写入概览、调度 CRUD、表单 PATCH、数据源测试、配置更新与归档的失败测试。**

```go
func TestOverviewReturnsSingleReadModel(t *testing.T) {
  response := performRequest(router, http.MethodGet, "/api/v1/overview", "")
  require.Equal(t, http.StatusOK, response.Code)
  require.JSONEq(t, `{"data":{"today":{},"health":{},"active_run":null,"trend":[],"risks":[],"recent_runs":[]}}`, response.Body.String())
}
```

增加：空 PATCH 返回 `400/INVALID_REQUEST`；不存在调度返回 `404/SCHEDULE_NOT_FOUND`；数据源测试响应不含密钥；写接口缺部署密钥返回 `401`。

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/server && go test ./api/routes/v1 -run 'Test(Overview|Schedule|Form|DataSource|System)' -count=1`

Expected: FAIL。

- [ ] **Step 3: 复用现有 service/handler 读取逻辑实现资源。**

`overview.go` 调用 `dashboard.GetTodayStats`、`GetHealthStatus`、`GetTrend7d`、`GetRiskItems`、`GetRecentRuns` 和活跃运行查询，并映射为 `contract.Overview`。`schedules.go` 复用 `internal/schedule` 和 `gormdb.ScheduleJob`；`resources.go` 调用 forms、datasource service；`system.go` 调用 config、diagnostics、maintenance。所有 handler 使用 Task 1 writer。

- [ ] **Step 4: 运行所有路由测试。**

Run: `cd apps/server && go test ./api/routes/... -count=1`

Expected: PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/server/api/routes/v1 && git commit -m "feat(api): add v1 operations resources"`

### Task 4: 建立前端 v1 客户端、错误模型与主题基础

**Files:**
- Create: `apps/web/src/services/v1.ts`
- Create: `apps/web/src/services/v1.test.ts`
- Create: `apps/web/src/styles/tokens.css`
- Modify: `apps/web/src/global.tsx`
- Modify: `apps/web/src/requestErrorConfig.ts`
- Modify: `apps/web/src/app.tsx`

- [ ] **Step 1: 为 v1 client 写失败测试。**

```ts
it('将 409 problem 转换为 ApiProblemError', async () => {
  requestMock.mockRejectedValue({ response: { status: 409, data: { error: { code: 'RUN_ALREADY_ACTIVE', message: '同步任务正在运行' } } } });
  await expect(createRun({ forms: ['物料'], sync_type: 'full' })).rejects.toMatchObject({ status: 409, code: 'RUN_ALREADY_ACTIVE' });
});
```

增加 `getOverview()` 请求 `/api/v1/overview`、`cancelRun()` 请求 `/api/v1/runs/run-001/actions/cancel`，并断言不访问旧 `/api/sync/*`。

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/web && npm test -- src/services/v1.test.ts`

Expected: FAIL，找不到模块。

- [ ] **Step 3: 实现强类型 client、错误对象和主题 token。**

```ts
export class ApiProblemError extends Error { constructor(public status: number, public code: string, message: string, public details?: unknown) { super(message); } }
export async function createRun(input: CreateRunInput): Promise<Run> { return getData(request<Envelope<Run>>('/api/v1/runs', { method: 'POST', data: input })); }
```

`tokens.css` 定义 `--ops-bg`、`--ops-surface`、`--ops-text`、`--ops-muted`、`--ops-success`、`--ops-warning`、`--ops-danger`、`--ops-border`；`app.tsx` 的 Ant Design theme 映射同一语义色，不再直接使用 `#e2e8f0`、`#f87171` 或其 rgba 变体。

- [ ] **Step 4: 运行 client 测试和类型检查。**

Run: `cd apps/web && npm test -- src/services/v1.test.ts && npm run tsc`

Expected: PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/web/src/services/v1.ts apps/web/src/services/v1.test.ts apps/web/src/styles/tokens.css apps/web/src/global.tsx apps/web/src/requestErrorConfig.ts apps/web/src/app.tsx && git commit -m "feat(web): add v1 client and operations theme"`

### Task 5: 添加统一查询状态与共享异常表单组件

**Files:**
- Create: `apps/web/src/components/QueryResult.tsx`
- Create: `apps/web/src/components/QueryResult.test.tsx`
- Create: `apps/web/src/components/ErrorForms.tsx`
- Create: `apps/web/src/components/ErrorForms.test.tsx`
- Modify: `apps/web/src/components/index.ts`
- Delete: `apps/web/src/pages/Overview/components/ErrorForms.tsx`
- Delete: `apps/web/src/pages/monitor/components/ErrorForms.tsx`

- [ ] **Step 1: 写入 QueryResult 和 ErrorForms 的失败测试。**

```tsx
it('错误状态显示 message 并调用重试', async () => {
  const retry = vi.fn(); render(<QueryResult status="error" error={new ApiProblemError(503, 'UNAVAILABLE', '服务不可用')} onRetry={retry}>{() => null}</QueryResult>);
  await userEvent.click(screen.getByRole('button', { name: '重试' })); expect(retry).toHaveBeenCalledOnce();
});
it('监控上下文展示失败次数和最后错误', () => { render(<ErrorForms context="monitor" forms={[{ formName: '销售订单', failureCount: 2, lastError: '超时' }]} />); expect(screen.getByText('销售订单')).toBeInTheDocument(); });
```

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/web && npm test -- src/components/QueryResult.test.tsx src/components/ErrorForms.test.tsx`

Expected: FAIL。

- [ ] **Step 3: 实现四态 QueryResult 和统一 ErrorForms。**

`QueryResult` props 固定为 `status: 'pending' | 'error' | 'empty' | 'success'`、`error?`、`onRetry?`、`emptyDescription?`、`children`。成功 children 只在 `success` 执行。`ErrorForms` props 为 `forms: ErrorForm[]` 和 `context: 'overview' | 'monitor'`，每项具有 `formName`、`failureCount`、`lastError?`；所有色彩使用 token CSS 类。

- [ ] **Step 4: 将两个页面入口改为从 `@/components` 导入并运行测试。**

Run: `cd apps/web && npm test -- src/components/QueryResult.test.tsx src/components/ErrorForms.test.tsx && npm run tsc`

Expected: PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/web/src/components && git rm apps/web/src/pages/Overview/components/ErrorForms.tsx apps/web/src/pages/monitor/components/ErrorForms.tsx && git commit -m "feat(web): unify query states and error forms"`

### Task 6: 重写 Overview 与 Sync 页面

**Files:**
- Modify: `apps/web/src/pages/Overview/hooks.ts`
- Modify: `apps/web/src/pages/Overview/index.tsx`
- Create: `apps/web/src/pages/Overview/hooks.test.tsx`
- Create: `apps/web/src/pages/Overview/components/OverviewStatusBar.tsx`
- Modify: `apps/web/src/pages/sync/hooks.ts`
- Modify: `apps/web/src/pages/sync/index.tsx`
- Create: `apps/web/src/pages/sync/hooks.test.tsx`
- Create: `apps/web/src/pages/sync/components/RunCommandBar.tsx`

- [ ] **Step 1: 写入 Overview 单请求和 Sync 终态停止轮询的失败测试。**

```tsx
it('概览只请求 v1 聚合读模型', async () => { renderHook(() => useOverviewData(), { wrapper }); await waitFor(() => expect(api.getOverview).toHaveBeenCalledOnce()); expect(api.getDataSources).not.toHaveBeenCalled(); });
it('运行到 success 后不再设置轮询间隔', () => { expect(runPollInterval('success')).toBe(false); });
```

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/web && npm test -- src/pages/Overview/hooks.test.tsx src/pages/sync/hooks.test.tsx`

Expected: FAIL。

- [ ] **Step 3: 使 Overview 只消费 `getOverview`，使 Sync 使用 create/cancel/get run/events。**

`useOverviewData` 返回一个 `UseQueryResult<Overview>`；`index.tsx` 用 `QueryResult` 包裹状态条、指标、趋势、风险和近期运行。`useSyncPage` 在 create mutation 成功后保存 `runId` 到 URL search params，`runPollInterval` 对终态返回 `false`；`RunCommandBar` 承载表单选择与启动/取消按钮。

- [ ] **Step 4: 运行两页测试、类型检查和浏览器人工检查。**

Run: `cd apps/web && npm test -- src/pages/Overview/hooks.test.tsx src/pages/sync/hooks.test.tsx && npm run tsc`

Expected: PASS；在 1280px 与 390px 宽度无横向溢出。

- [ ] **Step 5: 提交。**

Run: `git add apps/web/src/pages/Overview apps/web/src/pages/sync && git commit -m "feat(web): rebuild overview and sync workflows"`

### Task 7: 重写 Monitor 与 Schedule 页面

**Files:**
- Modify: `apps/web/src/pages/monitor/hooks.ts`
- Modify: `apps/web/src/pages/monitor/index.tsx`
- Modify: `apps/web/src/pages/monitor/components/RunDetailDrawer.tsx`
- Create: `apps/web/src/pages/monitor/hooks.test.tsx`
- Modify: `apps/web/src/pages/schedule/hooks.ts`
- Modify: `apps/web/src/pages/schedule/index.tsx`
- Create: `apps/web/src/pages/schedule/hooks.test.tsx`
- Create: `apps/web/src/pages/schedule/components/ScheduleToolbar.tsx`

- [ ] **Step 1: 写入运行筛选、详情抽屉和调度 mutation 失效的失败测试。**

```tsx
it('筛选条件映射为 v1 page 参数', async () => { renderHook(() => useMonitorPage({ status: 'failed', page: 2 }), { wrapper }); await waitFor(() => expect(api.listRuns).toHaveBeenCalledWith({ status: 'failed', page: 2 })); });
it('更新调度后失效 schedules 和 scheduler', async () => { const { result } = renderHook(() => useSchedulePage(), { wrapper }); await result.current.updateSchedule.mutateAsync({ id: 1, name: '每日同步' }); expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['v1', 'schedules'] }); });
```

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/web && npm test -- src/pages/monitor/hooks.test.tsx src/pages/schedule/hooks.test.tsx`

Expected: FAIL。

- [ ] **Step 3: 使用 v1 runs/events 与 schedules/scheduler 替换旧请求，并拆分工具栏和详情区域。**

`RunDetailDrawer` 只展示由 `useRun` 传入的 `Run`；`HistoryTable` 只发出分页和筛选事件。`ScheduleToolbar` 只显示调度器状态和动作，`JobTable` 接收 `Schedule[]` 与 typed callbacks。mutation 成功后失效 `['v1','schedules']`、`['v1','scheduler']` 和 `['v1','overview']`。

- [ ] **Step 4: 运行页面与既有抽屉测试。**

Run: `cd apps/web && npm test -- src/pages/monitor/hooks.test.tsx src/pages/schedule/hooks.test.tsx src/pages/monitor/components/RunDetailDrawer.test.tsx && npm run tsc`

Expected: PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/web/src/pages/monitor apps/web/src/pages/schedule && git commit -m "feat(web): rebuild monitoring and scheduling"`

### Task 8: 重写 Data 与 System 页面并消除不安全类型

**Files:**
- Modify: `apps/web/src/pages/data/hooks.ts`
- Modify: `apps/web/src/pages/data/index.tsx`
- Modify: `apps/web/src/pages/data/components/FormsManager.tsx`
- Create: `apps/web/src/pages/data/hooks.test.tsx`
- Modify: `apps/web/src/pages/system/hooks.ts`
- Modify: `apps/web/src/pages/system/index.tsx`
- Modify: `apps/web/src/pages/system/components/ConfigPanel.tsx`
- Modify: `apps/web/src/pages/system/components/MaintenancePanel.tsx`
- Create: `apps/web/src/pages/system/hooks.test.tsx`

- [ ] **Step 1: 为表单开关、数据源测试、配置保存与历史归档写失败测试。**

```tsx
it('更新表单后失效 forms 和 overview', async () => { const { result } = renderHook(() => useDataPage(), { wrapper }); await result.current.updateForm.mutateAsync({ formName: '物料', enabled: false }); expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['v1', 'forms'] }); });
it('归档历史使用服务器返回的删除数量', async () => { render(<MaintenancePanel archiveResult={{ runsDeleted: 12 }} />); expect(screen.getByText('已清理 12 条运行记录')).toBeInTheDocument(); });
```

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/web && npm test -- src/pages/data/hooks.test.tsx src/pages/system/hooks.test.tsx`

Expected: FAIL。

- [ ] **Step 3: 切换到 forms/data-sources/system v1 client，并替换所有 `any`。**

`FormsManager` 使用 `Map<string, FormStatistics>` 与 `Form`；配置保存使用 `UpdateSystemConfigInput`；所有 `catch (error: unknown)` 经 `getErrorMessage` 转换。`DataSourceStatus` 接收 `DataSource[]`；归档使用 `ArchiveHistoryInput` 与 `ArchiveHistoryResult`。

- [ ] **Step 4: 检查类型并运行页面测试。**

Run: `cd apps/web && ! rg -n '\bany\b' src --glob '*.{ts,tsx}' -g '!requestErrorConfig.ts' && npm test -- src/pages/data/hooks.test.tsx src/pages/system/hooks.test.tsx && npm run tsc`

Expected: `rg` 无输出，测试与 tsc PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/web/src/pages/data apps/web/src/pages/system && git commit -m "feat(web): rebuild data and system management"`

### Task 9: 切换全局指示器、删除旧前端 API 并统一页面类型

**Files:**
- Modify: `apps/web/src/components/GlobalSyncIndicator.tsx`
- Create: `apps/web/src/components/GlobalSyncIndicator.test.tsx`
- Delete: `apps/web/src/services/api.ts`
- Delete: `apps/web/src/services/api.test.ts`
- Modify: `apps/web/src/pages/Overview/types.ts`
- Modify: `apps/web/src/pages/monitor/types.ts`
- Modify: `apps/web/src/pages/sync/types.ts`
- Modify: `apps/web/src/pages/schedule/types.ts`
- Modify: `apps/web/src/pages/system/types.ts`

- [ ] **Step 1: 添加全局指示器只使用 v1 run detail 的失败测试。**

```tsx
it('活跃运行时查询 v1 run 并显示取消操作', async () => { render(<GlobalSyncIndicator />); await waitFor(() => expect(api.getRun).toHaveBeenCalled()); expect(api.getSyncStatus).not.toHaveBeenCalled(); });
```

- [ ] **Step 2: 运行失败测试和旧导入检索。**

Run: `cd apps/web && npm test -- src/components/GlobalSyncIndicator.test.tsx && rg -n "from '@/services/api'|from './api'" src`

Expected: 测试失败或 grep 列出旧导入。

- [ ] **Step 3: 切换全局指示器与页面类型到 v1 并移除旧 client。**

`GlobalSyncIndicator` 通过 `listRuns({ status: 'running', page_size: 1 })` 发现活跃运行，并通过 `getRun(runId)` 轮询；色彩引用 token class。页面类型只从 `@/services/v1` 导入，不重复声明 DTO。

- [ ] **Step 4: 运行清理检查、测试和类型检查。**

Run: `cd apps/web && ! rg -n "services/api|/api/(sync|dashboard|schedule|forms|config|logs|diagnostics)" src && npm test && npm run tsc`

Expected: 旧路径与旧服务导入均无输出，测试与 tsc PASS。

- [ ] **Step 5: 提交。**

Run: `git add apps/web/src && git rm apps/web/src/services/api.ts apps/web/src/services/api.test.ts && git commit -m "refactor(web): remove legacy api client"`

### Task 10: 删除旧 Go API、更新文档并全量验证

**Files:**
- Modify: `apps/server/cmd/server/main.go`
- Delete: `apps/server/api/routes/sync.go`
- Delete: `apps/server/api/routes/dashboard/dashboard.go`
- Delete: `apps/server/api/routes/history/history.go`
- Delete: `apps/server/api/routes/schedule/schedule.go`
- Delete: `apps/server/api/routes/forms/forms.go`
- Delete: `apps/server/api/routes/datasources/datasources.go`
- Delete: `apps/server/api/routes/config/config.go`
- Delete: `apps/server/api/routes/logs/logs.go`
- Delete: `apps/server/api/routes/diagnostics/diagnostics.go`
- Delete: `apps/server/api/routes/maintenance/maintenance.go`
- Modify: `docs/openapi.yaml`
- Modify: `docs/API_DESIGN.md`

- [ ] **Step 1: 添加旧路径未注册、v1 路径已注册的失败测试。**

```go
func TestServerRegistersOnlyV1BusinessRoutes(t *testing.T) {
  router := newServerRouter(testEngine)
  require.Equal(t, http.StatusNotFound, perform(router, http.MethodGet, "/api/dashboard/today").Code)
  require.Equal(t, http.StatusOK, perform(router, http.MethodGet, "/api/v1/overview").Code)
}
```

在 `apps/server/cmd/server/main_test.go` 定义 `newServerRouter(engine)`：创建 `gin.New()`，安装与生产相同的 `installWriteProtection`，调用 `v1.InitRoutes(router, engine)`，但不启动监听器和静态文件服务。

- [ ] **Step 2: 运行失败测试。**

Run: `cd apps/server && go test ./cmd/server -run TestServerRegistersOnlyV1BusinessRoutes -count=1`

Expected: FAIL，旧路径仍被注册。

- [ ] **Step 3: 迁移 legacy handler 的剩余业务逻辑并删除旧 routes 与注册调用。**

不得删除同步状态机、日志脱敏、配置读写或调度服务。`main.go` 只注册 `v1.InitRoutes`、`/health`、`/ready` 和静态资源；旧 handler 所持有的业务逻辑移入 v1 handler 或 `internal` service。

- [ ] **Step 4: 更新 OpenAPI/API 文档并执行全量测试。**

Run: `cd apps/server && go test ./...`

Run: `cd apps/web && npm run lint && npm test && npm run build`

Expected: 全部 PASS。

- [ ] **Step 5: 启动前端，检查六页和移动视口。**

Run: `cd apps/web && npm run dev`

在 `/overview`、`/sync`、`/schedule`、`/data`、`/monitor`、`/system` 的 `1280x800` 与 `390x844` 视口检查：内容不重叠、文字不溢出、空态可见、错误可重试、写操作显示最终状态。

- [ ] **Step 6: 提交接口收尾与文档。**

Run: `git add apps/server docs/openapi.yaml docs/API_DESIGN.md && git rm apps/server/api/routes/sync.go apps/server/api/routes/dashboard/dashboard.go apps/server/api/routes/history/history.go apps/server/api/routes/schedule/schedule.go apps/server/api/routes/forms/forms.go apps/server/api/routes/datasources/datasources.go apps/server/api/routes/config/config.go apps/server/api/routes/logs/logs.go apps/server/api/routes/diagnostics/diagnostics.go apps/server/api/routes/maintenance/maintenance.go && git commit -m "refactor(api): retire legacy endpoints"`

## 计划自审

- 规格覆盖：Task 1-3 提供所有 v1 API；Task 4-5 提供类型、三态、共享错误表单和主题；Task 6-8 覆盖六页；Task 9-10 移除旧契约、补文档并验证构建。
- 占位检查：没有 `TODO`、`TBD`、未定义的后续工作或泛化测试描述；每个任务给出固定文件、命令和结果。
- 类型一致性：前端统一使用 `Run`、`RunEvent`、`Overview`、`Schedule`、`Form`、`DataSource`、`ApiProblemError` 和 v1 `Envelope`；后端使用同名 v1 DTO 与既有 `SyncStatus`。
