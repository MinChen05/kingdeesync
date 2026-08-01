# 二次开发规范

本文档面向参与 kingdee-sync 项目开发的开发者，涵盖代码规范、扩展流程和测试要求。

---

## 一、项目结构

```
├── apps/
│   ├── server/              # Go 后端
│   │   ├── cmd/server/      #   应用入口
│   │   ├── api/routes/v1/   #   HTTP 路由与 DTO（仅做路由注册和参数绑定）
│   │   ├── internal/        #   业务逻辑（按领域分包，禁止跨层循环依赖）
│   │   │   ├── config/      #     配置加载（INI + JSON）
│   │   │   ├── db/          #     sqlx 轻量查询（Doris/MySQL 业务表）
│   │   │   ├── gormdb/      #     GORM（内部表：schedule、runs、stats）
│   │   │   ├── kind/        #     金蝶 API 客户端
│   │   │   ├── syncengine/  #     同步引擎核心
│   │   │   ├── schedule/    #     定时调度
│   │   │   ├── circuit/     #     熔断器
│   │   │   ├── ratelimit/   #     限流器
│   │   │   ├── retry/       #     重试
│   │   │   ├── task/        #     任务服务
│   │   │   └── datasource/  #     数据源
│   │   └── testdata/        #   测试数据
│   └── web/                 # React 前端
│       └── src/
│           ├── pages/       #   页面（Page → Container → UI Component）
│           ├── components/  #   公共 UI 组件（无业务逻辑）
│           ├── services/    #   API 客户端封装
│           ├── hooks/       #   全局自定义 Hooks
│           ├── utils/       #   工具函数
│           └── types/       #   全局类型定义
├── packages/sync-config/    # 表单配置与脱敏配置
├── deploy/                  # 容器化部署
└── docs/                    # 文档
```

---

## 二、后端开发规范（Go）

### 2.1 命名约定

| 元素 | 规则 | 示例 |
|------|------|------|
| 包名 | 小写单词 | `config`, `gormdb`, `syncengine` |
| 结构体 | PascalCase | `SyncEngine`, `FormQuery` |
| 公开方法 | PascalCase | `NewSyncEngine()`, `SyncData()` |
| 私有方法 | camelCase | `runSync()`, `writeRows()` |
| 常量 | PascalCase 前缀 | `StatusRunning`, `ErrTimeout` |
| JSON 标签 | snake_case | `json:"run_id"` |
| GORM 标签 | 显式声明约束 | `gorm:"type:varchar(64);uniqueIndex;not null"` |

### 2.2 错误处理

- 使用 `fmt.Errorf("context: %w", err)` 包装错误，保留错误链（原因：便于上层判断错误类型）
- 定义明确的 sentinel errors：`var ErrSyncAlreadyRunning = errors.New("...")`
- 区分业务错误（HTTP 4xx）与系统错误（HTTP 5xx）（原因：前端需要差异化处理）
- 通过 `WriteProblem(c, status, Problem{...})` 返回结构化错误（原因：统一错误响应格式）
- **禁止吞掉 error**（原因：静默失败导致故障无法排查）

### 2.3 日志规范

- 使用标准库 `log.Printf`，模块前缀标识来源：`[SYNC]`, `[KIND]`, `[DB]` 等
- 关键操作记录上下文：form name、run ID、耗时、记录数
- **禁止打印密码、Token 等敏感数据**（原因：安全合规要求）

### 2.4 并发规范

- 共享状态用 `sync.RWMutex` 保护
- 异步操作必须传入 `context.Context`，支持取消传播
- Goroutine 必须有明确退出路径（`defer` + `done` channel）（原因：防止 goroutine 泄漏）
- 并发度控制使用 `sync.WaitGroup` + channel semaphore

### 2.5 分层纪律

- `api/routes/` 仅做路由注册、参数绑定和响应封装，不含业务逻辑（原因：保持路由层薄）
- `internal/` 按领域分包，禁止循环依赖（原因：模块边界清晰，便于独立测试）
- GORM（`gormdb`）仅用于内部表（schedule、runs），业务数据查询使用 sqlx（`db`）（原因：分离 OLTP 和 OLAP 场景）

---

## 三、前端开发规范（React / TypeScript）

### 3.1 组件分层

采用 **Page → Container(Hook) → UI Component** 三层架构：

| 层级 | 职责 | 位置 |
|------|------|------|
| **Page** | 布局组装，不含业务逻辑和展示细节 | `pages/Xxx/index.tsx` |
| **Container** | 数据获取、状态管理、业务逻辑 | `pages/Xxx/hooks.ts` |
| **UI Component** | 纯展示，接收 Props，无副作用 | `pages/Xxx/components/` |

**新增页面 = 写 UI 组件 + 在 Page 的 `index.tsx` 中加一行引用**（原因：保持组装层轻量）

### 3.2 Hooks 规范

- 数据获取统一使用 `@tanstack/react-query`（`useQuery`）（原因：内置缓存、重试、加载状态管理）
- 自定义 Hook 命名 `useXxx`，返回统一结构：`{ data, loading, refresh }`
- `useEffect` 必须声明完整依赖数组，cleanup 中清理定时器/订阅（原因：防止内存泄漏和过期闭包）

### 3.3 API 请求

- 统一使用 UmiJS 的 `request`，v1 API 封装在 `services/v1.ts`
- 错误统一抛 `ApiProblemError`（带 `code` 和 `details`）（原因：前端统一错误处理）
- 全局错误拦截在 `requestErrorConfig.ts`（原因：避免每个请求重复写 try-catch）

### 3.4 TypeScript

- 类型定义优先复用，不在组件内重复声明
- **禁止滥用 `any` 和 `as` 强制类型断言**（原因：类型安全是 TypeScript 核心价值）
- DTO 类型从后端 v1 定义直接映射（原因：保持前后端契约一致）

### 3.5 样式

- Tailwind CSS 为主（`className="space-y-6"`）
- Ant Design 组件用于复杂交互（ProTable、ProForm 等）
- 暗色主题（`antdTheme.darkAlgorithm`）

---

## 四、扩展流程

### 4.1 新增业务表单

按以下顺序操作，缺一不可：

1. **`form-queries.json`** — 添加表单查询配置：
   ```json
   "新表单名": {
     "FormId": "金蝶FormID",
     "FieldKeys": "FID,FNAME,...",
     "FilterString": "F... = '...'",
     "FieldMap": {},
     "DefaultValues": {}
   }
   ```

2. **`internal/config/config.go`** — `formToTableName` 添加映射：
   ```go
   "新表单名": "target_table_name",
   ```

3. **`internal/db/database.go`** — `primaryKeyMap` 添加主键定义：
   ```go
   "target_table_name": []string{"FID"},
   ```

4. **`internal/syncengine/engine.go`** — `PriorityMap` 添加优先级分组（0=小表，1=中表，2=大表）

5. **Doris 数据库** — 创建目标表（DDL 参考 `docs/doris-ddl-kingdee-sync.sql`）

6. **`config.local.ini`** — `[INCREMENTAL_FIELDS]` 段添加增量字段：
   ```ini
   新表单名 = FModifyDate
   ```

### 4.2 新增 API 接口

1. 在 `api/routes/v1/` 下创建或修改路由文件
2. 定义请求/响应 DTO（与后端 v1 契约一致）
3. 在 `routes.go` 的 `Register()` 中注册路由
4. 前端在 `services/v1.ts` 中添加对应请求方法
5. 补充相关测试

### 4.3 新增调度任务

通过 API 创建，无需修改代码：

```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_task",
    "cron_expr": "0 0 */2 * * 1-6",
    "sync_type": "incremental",
    "forms": ["表单1", "表单2"],
    "enabled": true
  }'
```

---

## 五、测试规范

### 5.1 后端测试（Go）

```go
// 表驱动测试为主
func TestXxx(t *testing.T) {
    tests := []struct {
        name     string
        input    XXX
        expected XXX
    }{
        {"正常场景", ...},
        {"空输入", ...},
        {"边界值", ...},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // ...
        })
    }
}
```

**要求**：
- 文件命名：`xxx_test.go`（与被测文件同目录）
- 覆盖：正常路径、异常路径、关键边界（nil、空 slice、非法格式）
- 使用 `t.TempDir()`、`t.Setenv()`、`t.Cleanup()` 管理测试环境
- 执行：`cd apps/server && go test ./...`

### 5.2 前端测试（Vitest）

```tsx
describe('组件名', () => {
  it('应该渲染正确内容', () => {
    render(<Component />);
    expect(screen.getByText('预期文本')).toBeInTheDocument();
  });
});
```

**要求**：
- 文件命名：`xxx.test.tsx`（与被测文件同级）
- Hook 测试使用 `renderHook` + `QueryClientProvider` wrapper
- Mock 使用 `vi.mock()`，`beforeEach` 中清理 mock 状态
- 执行：`cd apps/web && pnpm test`

---

## 六、Git 提交规范

使用 **Conventional Commits** 格式：

```
<type>(<scope>): <描述>
```

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响逻辑） |
| `refactor` | 重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具/依赖 |

**示例**：
```
feat(sync): 新增委外订单同步支持
fix(schedule): 增量同步调整为周一到周六每2小时一次
docs: 补充二次开发规范
```

**要求**：
- 描述使用中文
- Scope 可选，常见：`sync`, `schedule`, `web`, `deploy`, `api`
- 提交前确保相关测试通过

---

## 七、代码注释规范

- **函数/方法**：单行注释，首字母大写，句号结尾
  ```go
  // WriteData sends a successful JSON response wrapped in an Envelope.
  ```
- **复杂逻辑**：中文注释 + `（原因：xxx）` 标注动机（原因：决策可追溯）
- **文件头**：包级注释说明职责
  ```go
  // Package v1 defines the v1 REST API contract and response writers.
  ```

---

## 八、部署与运维

### 8.1 容器部署

```bash
cd deploy/docker
podman-compose up -d --build     # 构建并启动
podman-compose logs -f           # 查看日志
podman-compose down              # 停止并清理
```

### 8.2 配置文件管理

- `config.local.ini` 通过 volume 挂载到容器，修改后重启容器生效
- 调度任务存储在 `go_state.db`（SQLite），通过 Web 界面或 API 管理
- 日志输出到容器 stdout，通过 `podman logs` 查看

---

## 九、常见问题

### Q: 新增表单后同步不生效？

检查清单：
1. `form-queries.json` 是否已添加
2. `formToTableName` 映射是否存在
3. `primaryKeyMap` 是否定义主键
4. Doris 目标表是否已创建
5. 调度任务的 `forms` 字段是否包含新表单

### Q: 金蝶 API 返回 401？

检查 `config.local.ini` 中 `[KINGDEE]` 段的凭证是否正确，确认 `keep_session_alive = true`。

### Q: 前端构建失败？

确认使用 `pnpm` 而非 `npm`/`yarn`（原因：项目使用 pnpm workspace 管理依赖）。
