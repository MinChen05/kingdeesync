# 金蝶数据同步工具 - 前端开发文档

> 基于 Ant Design Pro + UmiJS Max 的企业级管理界面。

---

## 一、技术栈

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 框架 | React | ^19.2.7 | UI 框架 |
| 脚手架/构建 | @umijs/max (UmiJS v4) | ^4.6.75 | 路由、打包、插件体系 |
| UI 组件库 | antd | ^6.5.1 | 基础组件 |
| Pro 组件 | @ant-design/pro-components | ^3.1.14-2 | ProTable、ProCard、StatisticCard 等 |
| 图表 | @ant-design/plots | ^2.6.8 | 基于 G2 的图表封装 |
| 状态管理 | @tanstack/react-query | ^5.101.2 | 服务端状态（插件启用但未深度使用） |
| Hooks | ahooks | ^3.9.7 | 请求封装、轮询等 |
| CSS | Tailwind CSS | ^4.3.2 | 原子化样式（通过 `tailwind.css` @import） |
| CSS-in-JS | antd-style | ^4.1.0 | 全局样式（`global.style.ts`） |
| 时间处理 | dayjs | ^1.11.21 | moment 替代（umi moment2dayjs 插件） |
| Lint | @biomejs/biome | ^2.5.3 | 代码格式化与检查 |
| 测试 | vitest | 4.1.10 | 单元测试 |
| 提交规范 | @commitlint/cli | ^21.2.1 | conventional commits |
| Git Hooks | husky | ^9.1.7 | pre-commit 等钩子 |

**Node 版本要求：** >= 22.0.0

---

## 二、项目结构

```
frontend/
├── config/                      # UmiJS 配置
│   ├── config.ts                # 主配置（生产环境）
│   ├── config.dev.ts            # 开发环境配置
│   ├── config.prod.ts           # 生产构建配置（精简版）
│   ├── defaultSettings.ts       # ProLayout 主题与布局配置
│   ├── proxy.ts                 # 开发代理配置
│   └── routes.ts                # 路由定义
├── public/
│   └── scripts/loading.js       # 首屏 loading
├── src/
│   ├── app.tsx                  # 运行时配置（initialState、layout、request）
│   ├── access.ts                # 权限配置（当前全部公开）
│   ├── global.tsx               # 全局入口（引入 tailwind）
│   ├── global.style.ts          # 全局样式（antd-style）
│   ├── loading.tsx              # 路由加载动画
│   ├── requestErrorConfig.ts    # 统一错误处理 + 请求拦截器
│   ├── typings.d.ts             # 全局类型声明
│   ├── locales/                 # 国际化
│   │   ├── zh-CN.ts / en-US.ts
│   │   └── zh-CN/menu.ts        # 菜单文案
│   ├── components/              # 通用组件
│   │   ├── ErrorBoundary/
│   │   └── HeaderDropdown/
│   ├── services/
│   │   ├── api.ts               # 业务 API 函数（全部）
│   │   └── ant-design-pro/      # 脚手架遗留（未使用）
│   ├── utils/
│   │   ├── format.ts            # 工具函数
│   │   └── chinaDivision.ts     # 行政区划（未使用）
│   └── pages/                   # 业务页面（详见第三节）
│       ├── Overview/            # 系统概览（首页）
│       ├── sync/                # 同步管理
│       ├── data/                # 数据配置
│       ├── monitor/             # 监控分析
│       ├── system/              # 系统
│       └── 404.tsx
├── tailwind.css                 # Tailwind 入口
├── biome.json                   # Biome 配置
├── package.json
└── tsconfig.json
```

---

## 三、路由配置

路由定义在 `frontend/config/routes.ts`，采用声明式配置。

| 路径 | 菜单名 | 图标 | 组件 | 说明 |
|------|--------|------|------|------|
| `/` | - | - | - | 重定向到 `/overview` |
| `/overview` | 概览 | dashboard | `./Overview` | 首页仪表盘 |
| `/sync` | 同步管理 | sync | - | 父菜单，重定向到 `/sync/execute` |
| `/sync/execute` | 同步执行 | playCircle | `./sync/Execute` | 手动启动同步 |
| `/sync/tasks` | 表单监控 | orderedList | `./sync/Tasks` | Doris 中各表单数据状态 |
| `/sync/task-management` | 任务管理 | unorderedList | `./sync/TaskManagement` | 同步任务 CRUD |
| `/sync/schedule` | 定时任务 | clockCircle | `./sync/Schedule` | Cron 调度管理 |
| `/data` | 数据配置 | database | - | 父菜单，重定向到 `/data/sources` |
| `/data/sources` | 数据源 | cluster | `./data/Sources` | 金蝶/Doris/SQLite 配置 |
| `/monitor` | 监控分析 | radarChart | - | 父菜单，重定向到 `/monitor/history` |
| `/monitor/history` | 同步历史 | history | `./monitor/History` | 同步记录列表 |
| `/monitor/history/:runId` | 历史详情 | - | `./monitor/HistoryDetail` | 隐藏菜单，动态路由 |
| `/monitor/stats` | 统计分析 | barChart | `./monitor/Stats` | 汇总统计 |
| `/monitor/logs` | 日志中心 | fileSearch | `./monitor/Logs` | 运行日志 |
| `/system` | 系统 | setting | - | 父菜单，重定向到 `/system/settings` |
| `/system/diagnostics` | 异常诊断 | tool | `./system/Diagnostics` | 连接健康检查 |
| `/system/settings` | 系统设置 | setting | `./system/Settings` | 全局配置 |
| `/*` | - | - | `./404` | 404 页面 |

**权限：** `access.ts` 返回 `canAdmin: true`，所有路由公开访问，无登录流程。

---

## 四、页面列表及职责

### 4.1 概览（Overview）

**文件：** `src/pages/Overview/index.tsx` + 7 个子组件 + `hooks.ts` + `types.ts`

**职责：** 系统仪表盘，按运维决策优先级分层展示：

1. **HeroStatus** - 系统整体状态指示灯 + 一键同步按钮
2. **MetricCards** - 今日核心 KPI（同步次数、成功率、失败数、平均耗时），含昨日对比
3. **TrendChart** - 近 7 天同步趋势柱状图（@ant-design/plots）
4. **ErrorForms** - 近 7 天异常表单 Top5
5. **HealthGrid** - 金蝶 API / Doris / 调度器 / 日志服务健康状态
6. **RecentRuns** - 最近 6 条同步记录

**数据获取：** `hooks.ts` 统一封装，使用 `ahooks useRequest`，同步状态 3 秒轮询。

### 4.2 同步执行（sync/Execute）

**文件：** `src/pages/sync/Execute/index.tsx`

**职责：** 手动触发同步任务。

- 选择同步模式：增量 / 全量 / 重置
- 选择目标表单（支持全选）
- 实时日志面板（1 秒轮询状态 + 2 秒轮询日志，自动滚动）
- 进度条 + 当前表单 + 已用时间
- 支持停止运行中的同步

### 4.3 表单监控（sync/Tasks）

**文件：** `src/pages/sync/Tasks/index.tsx`

**职责：** 查看 Doris 中各表单的数据状态。

- 统计卡片：总表单数、已同步/未同步数、总行数
- ProTable 展示：表单名、目标表、分类、行数、状态、最后同步时间
- 30 秒自动刷新（可关闭）

### 4.4 任务管理（sync/TaskManagement）

**文件：** `src/pages/sync/TaskManagement/index.tsx`

**职责：** 管理同步任务的生命周期。

- 统计卡片：启用/暂停任务数、今日执行数、失败待重试
- ProTable：任务名称、关联表单、同步方式、状态、最近执行、成功率
- 操作：立即运行、启用/暂停、查看详情（Drawer）
- 批量操作：批量启用、批量暂停

### 4.5 定时任务（sync/Schedule）

**文件：** `src/pages/sync/Schedule/index.tsx`

**职责：** Cron 定时调度管理。

- 卡片列表展示各定时任务（名称、Cron 表达式、包含表单数、上次运行/状态）
- 启用/禁用开关
- 立即执行按钮
- 编辑 Modal（3 步向导：基本信息 → 调度策略 → 选择表单）
- Cron 预设：每 5/10/20/30 分钟、每小时、每天午夜/凌晨 2 点、每周日

### 4.6 数据源（data/Sources）

**文件：** `src/pages/data/Sources/index.tsx`

**职责：** 查看和管理三个数据源配置。

- **金蝶云星空** - 账套 ID、用户名、QPS 限制、每页大小、登录/查询地址
- **Doris 数据仓库** - 主机、端口、数据库、用户
- **SQLite 状态库** - 本地只读展示
- 测试连接按钮（调用 `/api/datasources/test`）
- 编辑 Modal（敏感信息提示在配置文件中修改）

### 4.7 同步历史（monitor/History）

**文件：** `src/pages/monitor/History/index.tsx`

**职责：** 分页查询同步运行记录。

- ProTable request 模式，服务端分页
- 筛选：状态、同步类型、日期范围
- 列：状态 Tag、类型 Tag、开始时间、耗时、表单数、成功/失败数、记录数
- 行可点击，跳转到 `/monitor/history/:runId`

### 4.8 历史详情（monitor/HistoryDetail）

**文件：** `src/pages/monitor/HistoryDetail/index.tsx`

**职责：** 单次同步任务的详细信息。

- Descriptions：类型、状态、耗时、表单数、成功/失败、记录数、起止时间
- 错误信息 Alert（如有）
- 表单明细表格：每个表单的拉取/写入/失败数、耗时、错误

### 4.9 统计分析（monitor/Stats）

**文件：** `src/pages/monitor/Stats/index.tsx`

**职责：** 汇总统计概览。

- 统计卡片：总次数、成功/失败/部分成功、总记录数、成功率
- 性能统计：平均耗时、成功/失败记录数
- 运行分布：Progress 条形图

### 4.10 日志中心（monitor/Logs）

**文件：** `src/pages/monitor/Logs/index.tsx`

**职责：** 查看系统运行日志。

- ProTable：级别（ERROR/WARN/INFO/DEBUG）、表单、消息、详情、时间
- 筛选：级别、表单名
- 行可展开查看详情
- 5 秒自动刷新（可关闭）

### 4.11 异常诊断（system/Diagnostics）

**文件：** `src/pages/system/Diagnostics/index.tsx`

**职责：** 系统连接和环境诊断。

- 连接状态：金蝶 API、数据库（含响应时间）
- 系统环境：OS、架构、CPU 核心数、Go 版本、数据库类型
- 诊断信息 Alert
- 服务健康：调度器状态/下次执行、日志服务状态/写入速度/日志大小

### 4.12 系统设置（system/Settings）

**文件：** `src/pages/system/Settings/index.tsx`

**职责：** 全局同步配置。

- 顶部状态条：自动同步开关、同步模式、并发数、QPS
- 配置表单（ProCard 网格布局）：
  - 自动同步（Switch）
  - 同步间隔（30~86400 秒）
  - 同步类型（增量/全量）
  - 增量时间窗口（1~365 天）
  - 表并发数（1~16）
  - QPS 限制（1~100）
  - 每页查询大小（100~90000）
  - 数据维护：清理 N 天前历史数据

---

## 五、API 对接方式

### 5.1 代理配置

**文件：** `config/proxy.ts`

开发环境将 `/api/**` 代理到 Go 后端：

```typescript
'/api/': {
  target: 'http://127.0.0.1:8000',
  changeOrigin: true,
}
```

- 前端调用 `/api/xxx` → 开发服务器代理 → `http://127.0.0.1:8000/api/xxx`
- 生产环境：通过反向代理或同域部署，`baseURL` 为空字符串（相对路径）

### 5.2 请求模式

**文件：** `src/services/api.ts`（42 个 API 函数）

统一使用 UmiJS Max 内置 `request`（基于 axios）：

```typescript
import { request } from '@umijs/max';

export async function startSync(params: SyncStartParams) {
  return request<ApiResponse<any>>('/api/sync/start', { method: 'POST', data: params });
}
```

**统一错误处理（`requestErrorConfig.ts`）：**

- 后端响应格式：`{ ok: boolean, data?: T, error?: string }`
- `errorThrower`：当 `ok === false` 时抛出 `BizError`
- `errorHandler`：根据 `showType` 选择 message.error / notification / redirect
- 网络错误：离线检测、无响应提示

### 5.3 数据获取模式

主要使用 `ahooks useRequest`：

```typescript
import { useRequest } from 'ahooks';
import { getDashboardToday } from '@/services/api';

const { data, loading, refresh } = useRequest(getDashboardToday);
// data 是完整响应 { ok, data }, 业务数据在 data.data
```

**轮询场景：**
- 同步状态：3 秒（Overview）
- 表单监控：30 秒（sync/Tasks）
- 日志中心：5 秒（可选，monitor/Logs）

**注意：** TanStack Query (`@tanstack/react-query`) 已安装且 Umi 插件已启用（`reactQuery: {}`），但当前代码主要使用 ahooks，未深度使用 React Query。

---

## 六、全局状态管理

### 6.1 initialState

**文件：** `src/app.tsx`

```typescript
export async function getInitialState(): Promise<{
  settings?: Partial<LayoutSettings>;
  settingDrawerOpen?: boolean;
  version?: string;
}>
```

- `settings`：ProLayout 布局配置，从 localStorage 读取（key: `kingdee-sync-layout-settings`）
- `version`：应用版本，从 `/api/version` 获取
- 无用户认证状态（系统无登录）

### 6.2 服务端状态

- **ahooks useRequest**：页面级数据获取主力，支持缓存、轮询、依赖刷新
- **TanStack Query**：已配置但未使用（可作为后续优化方向）
- **无全局 store**：不使用 umi-model / zustand / redux，各页面独立管理本地状态

### 6.3 权限

`access.ts` 固定返回 `canAdmin: true`，无角色/权限控制。

---

## 七、布局与主题

### 7.1 ProLayout 配置

**文件：** `config/defaultSettings.ts`

```typescript
{
  navTheme: 'realDark',       // 深色导航
  colorPrimary: '#38bdf8',    // 科技青蓝
  layout: 'mix',              // 混合布局（左侧菜单 + 顶部 header）
  contentWidth: 'Fluid',      // 内容区全宽
  fixedHeader: true,
  fixSiderbar: true,
  title: '金蝶数据同步',
  logo: false,
}
```

### 7.2 运行时布局定制

**文件：** `src/app.tsx`（`layout` 导出）

- `menuHeaderRender`：自定义侧边栏头部（SyncOutlined 图标 + "金蝶数据同步"）
- `footerRender: false`：隐藏页脚
- `actionsRender: () => []`：顶部无操作区（无登录/头像）
- `links`：侧边栏底部显示版本号
- `childrenRender`：根据 `navTheme` 动态切换 `antdTheme.darkAlgorithm` / `defaultAlgorithm`
- `SettingDrawer`：开发调试用设置抽屉（支持切换亮/暗色）

### 7.3 主题 Token

**文件：** `config/config.ts`（antd configProvider）

```typescript
theme: {
  token: {
    fontFamily: 'AlibabaSans, sans-serif',
    colorPrimary: '#38bdf8',
    colorInfo: '#38bdf8',
    colorSuccess: '#34d399',
    colorWarning: '#fbbf24',
    colorError: '#f87171',
    borderRadius: 10,
  },
}
```

**defaultSettings.ts** 中的 token：
- 侧边栏背景 `#0d1526`（近黑蓝）
- 菜单文字 `rgba(226,232,240,0.72)`
- 选中项背景 `rgba(56,189,248,0.16)`
- Header 背景 `rgba(13,21,38,0.85)`（半透明）
- PageContainer 背景 `transparent`

### 7.4 Tailwind CSS

**入口：** `tailwind.css` → `src/global.tsx` 引入

```css
@import "tailwindcss/index.css";
@source "./src";
```

配置在 `config/config.ts` 中：`tailwindcss: {}`（默认配置）。

页面中大量使用 Tailwind 工具类：`space-y-6`、`grid grid-cols-1 lg:grid-cols-2`、`text-xs`、`bg-gray-50` 等。

---

## 八、开发流程

### 8.1 常用命令

```bash
# 开发服务器（代理到 :8000，MOCK=none）
npm run dev          # 或 npm run start

# 生产构建
npm run build        # 使用 config.prod.ts，输出到 dist/

# 预览构建产物（端口 8000）
npm run preview

# Lint + 类型检查
npm run lint         # biome lint + tsc --noEmit

# 格式化（Biome）
npm run biome        # biome check --write

# 测试
npm run test         # vitest run
npm run test:watch   # vitest（watch 模式）
npm run test:ui      # vitest --ui
npm run test:coverage # vitest run --coverage

# 依赖诊断
npm run doctor       # react-doctor
```

### 8.2 环境变量

| 变量 | 说明 |
|------|------|
| `UMI_ENV` | 环境标识（dev/test），决定 proxy 配置 |
| `MOCK` | `none` 禁用 mock |
| `NODE_ENV` | `development` / `production` |
| `COMMIT_HASH` | 构建时注入的 git commit hash |
| `CI` | CI 环境标识 |

### 8.3 全局常量（define）

构建时注入：
- `process.env.COMMIT_HASH`
- `__APP_VERSION__`（来自 package.json）
- `__UMI_VERSION__`
- `__UTOO_VERSION__`

---

## 九、与后端 API 的对应关系

前端 API 函数（`src/services/api.ts`）与后端接口（参考 `docs/API_DESIGN.md`）的映射：

| 前端函数 | 方法 | 路径 | 后端文档对应 |
|----------|------|------|-------------|
| `startSync` | POST | `/api/sync/start` | 四、同步控制 |
| `getSyncStatus` | GET | `/api/sync/status` | 四、同步控制 |
| `getSyncLogs` | GET | `/api/sync/logs` | -（前端特有） |
| `stopSync` | POST | `/api/sync/stop` | 四、同步控制 |
| `getConfig` | GET | `/api/config` | 二、配置相关 |
| `updateConfig` | PUT | `/api/config` | 二、配置相关 |
| `getForms` | GET | `/api/forms` | 三、表单管理 |
| `updateForm` | PUT | `/api/forms/:name` | 三、表单管理 |
| `getHistory` | GET | `/api/history` | 六、历史查询 |
| `getHistoryDetail` | GET | `/api/history/runs/:id/details` | 六、历史查询 |
| `getDashboardToday` | GET | `/api/dashboard/today` | 五、仪表盘 |
| `getDashboardTrend7d` | GET | `/api/dashboard/trend/7d` | 五、仪表盘（对应 `/api/trend/7d`） |
| `getDashboardTopForms7d` | GET | `/api/dashboard/top-forms/7d` | 五、仪表盘（对应 `/api/top-forms/7d`） |
| `getDashboardHealth` | GET | `/api/dashboard/health` | -（前端特有） |
| `getDashboardRecent` | GET | `/api/dashboard/recent` | -（前端特有） |
| `getScheduleJobs` | GET | `/api/schedule` | -（前端特有） |
| `createScheduleJob` | POST | `/api/schedule/job` | -（前端特有） |
| `updateScheduleJob` | PUT | `/api/schedule/job/:id` | -（前端特有） |
| `deleteScheduleJob` | DELETE | `/api/schedule/job/:id` | -（前端特有） |
| `getStats` | GET | `/api/stats/summary` | 七、统计查询 |
| `getDiagnostics` | GET | `/api/diagnostics` | 八、诊断接口 |
| `getLogs` | GET | `/api/logs/recent` | -（前端特有） |
| `getTasks` | GET | `/api/tasks` | -（前端特有） |
| `getTaskStats` | GET | `/api/tasks/stats` | -（前端特有） |
| `runTask` | POST | `/api/tasks/:id/run` | -（前端特有） |
| `enableTask` | POST | `/api/tasks/:id/enable` | -（前端特有） |
| `pauseTask` | POST | `/api/tasks/:id/pause` | -（前端特有） |
| `batchEnableTasks` | POST | `/api/tasks/batch-enable` | -（前端特有） |
| `batchPauseTasks` | POST | `/api/tasks/batch-pause` | -（前端特有） |
| `batchRunTasks` | POST | `/api/tasks/batch-run` | -（前端特有） |
| `getDataSources` | GET | `/api/datasources` | -（前端特有） |
| `testAllDatasources` | POST | `/api/datasources/test` | -（前端特有） |
| `getFormsStats` | GET | `/api/forms/stats` | -（前端特有） |
| `getVersion` | GET | `/api/version` | -（前端特有） |
| `archiveMaintenanceData` | POST | `/api/maintenance/archive` | 九、维护接口 |

**说明：**
- 前端已为 Go 后端扩展了较多接口（任务管理、调度、日志、数据源等），超出原始 API_DESIGN.md 草案范围。
- 所有接口统一 `{ ok, data }` 响应包装。

---

## 十、关键设计说明

1. **无登录设计**：系统面向内网运维使用，`access.ts` 直接开放所有权限。
2. **深色科技主题**：`realDark` + 青蓝主色 + 半透明玻璃质感，适配数据监控场景。
3. **概览页架构**：按运维决策优先级分层（状态 → KPI → 趋势 → 详情），各面板组件化，新增面板只需加组件 + 一行引用。
4. **同步执行页**：双轮询（状态 1s + 日志 2s）+ 自动滚动，提供类终端实时反馈。
5. **定时任务编辑**：3 步向导（基本信息 → Cron → 表单选择），降低配置门槛。
6. **Tailwind + antd 混用**：布局用 Tailwind，业务组件用 antd/ProComponents。
