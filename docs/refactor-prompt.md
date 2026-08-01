# 金蝶数据同步系统前端重构 — 执行提示词（2026-07-30 校准）

你是一个资深前端架构师，请帮我分析并重构一个 **金蝶 ERP 数据同步系统** 的 React 前端项目。

## 一、项目背景

这是一个将金蝶云星空 ERP 数据同步到 Apache Doris 分析型数据库的工具。数据处理链路为：

```
金蝶 Cloud API → Go 同步引擎 → Doris 写入 → React 前端查询展示
```

Go 后端提供 REST API（端口 8000），前端通过 Umi 代理调用。所有接口返回 `{ ok, data }` 包装结构。主要功能：

- **仪表盘（Overview）**：同步状态概览、健康度、7 天趋势图、异常表单 Top5、近期运行
- **同步控制（Sync）**：启动/停止同步、实时进度、日志查看、上次同步摘要
- **数据管理（Data）**：表单配置管理、数据源状态
- **监控中心（Monitor）**：错误日志、历史记录、运行详情抽屉、系统诊断
- **调度管理（Schedule）**：定时任务 CRUD、调度器启停
- **系统设置（System）**：配置编辑、维护操作

## 二、当前技术栈（2026-07-30 核实）

- React 19（19.2.7）
- UmiJS v4 Max（`max dev` / `max build`，路由与构建）
- Ant Design 6（6.5.1）+ Ant Design Pro Components
- **`@tanstack/react-query`（^5.101.2，实际数据请求方案，10+ 文件引用）**
- **ahooks 已移除**（提交 `9088ca4` 完成迁移，package.json 中无 ahooks 依赖，src 中仅残留 2 条注释提及）
- Tailwind CSS 4（4.3.2，辅助样式）
- Vitest + Testing Library（测试，目前 5 个测试文件）
- Biome（lint/format）

## 三、当前目录结构（2026-07-30 核实）

```
apps/web/
├── config/                    # Umi 配置（注意：不在 src 下）
│   ├── routes.ts              #   6 个页面路由
│   ├── config.ts / config.dev.ts / config.prod.ts
│   └── proxy.ts
└── src/
    ├── pages/
    │   ├── Overview/          # 每页已有 index.tsx + hooks.ts + types.ts + components/ 分层
    │   ├── sync/              # （结构同上）
    │   ├── data/
    │   ├── monitor/
    │   ├── schedule/
    │   └── system/
    ├── components/            # 共享组件（GlobalSyncIndicator/PageHeader/Panel/SyncStatusTag/SyncTypeTag）
    ├── services/
    │   ├── api.ts             # 手写 API 封装（364 行，页面唯一数据入口，无直接 request 调用）
    │   └── generated-api.ts   # OpenAPI 生成的类型（152 行）
    ├── utils/                 # format.ts、chinaDivision.ts
    └── typings.d.ts
```

## 四、现有问题（逐项核实，附证据）

1. **页面级组件偏大**：入口文件已很薄（56–118 行），但页面级组件臃肿——`FormsManager.tsx` 287 行、`RunDetailDrawer.tsx` 255 行、`JobTable.tsx` 247 行、`SyncConfigPanel.tsx` 241 行、`ErrorLogPanel.tsx` 237 行；共享组件 `GlobalSyncIndicator.tsx` 265 行。

2. **`any` 类型传播**：共约 22 处 `any` 散布在源码中，集中在：
   - `JobTableProps`（5 处）：`onCreate: (job: any) => void`、`onUpdate: (id: number, job: any) => void`
   - `schedule/index.tsx`（8 处）：handler 参数和 catch 块
   - `FormsManager.tsx`（4 处）：catch 块和 Table render 回调
   - `HistoryTable.tsx`（2 处）、`TrendChart.tsx`（1 处）、`JobEditDrawer.tsx`（1 处）
   - `monitor/components/ErrorForms.tsx`（1 处）：`forms: any[]`

3. **同名组件分叉实现**：`ErrorForms` 在 `pages/Overview/components/` 和 `pages/monitor/components/` 各有一份，Props（`topForms: TopForm[]` vs `forms: any[]`）、样式、文案均已分叉。

4. **暗色值硬编码**：组件内联 style 写死 `#e2e8f0`、`#f87171`、`#34d399`、`#38bdf8`、`#94a3b8` 等色值，集中在 `GlobalSyncIndicator.tsx`（约 20 处）、`HealthGrid.tsx`（约 7 处）、`MetricCards.tsx`（约 10 处），未走主题 token，后续换肤/暗色模式无法统一控制。

5. **`api.ts` 类型定义内联**：364 行的 `api.ts` 内联定义了所有响应类型（`ConfigData`、`FormItem`、`HistoryRun`、`ScheduleJob` 等），未抽离到各页面 `types.ts`，导致类型复用困难且文件偏大。

6. **测试覆盖不足**：仅 5 个测试文件（SyncStatusTag、SyncTypeTag、RunDetailDrawer、api.test.ts、format.test.ts），6 个页面的 hooks 均无测试。

## 五、重构目标

1. **拆分大组件**：将 200+ 行的页面组件按职责拆小（列表行、筛选栏、详情区块各自独立），保持现有 index/hooks/types/components 分层不变。

2. **类型完善**：消灭所有 `any`/`any[]`，为全部组件 Props、API 响应、hook 返回值补全 TypeScript 类型，与 `generated-api.ts` 对齐；将 `api.ts` 中的内联类型抽离到各页面 `types.ts`。

3. **消除分叉**：合并两份 `ErrorForms` 为共享组件（props 并集 + 展示差异通过可选 props 表达），提升至 `src/components/`。

4. **主题 token 化**：将硬编码暗色值收拢为统一的主题常量/design token（CSS 变量或 antd theme token），为后续暗色模式打基础。

5. **测试覆盖**：为 6 个页面的 hooks 和合并后的共享组件补单元测试。

## 六、约束条件

- 不改变现有 6 个页面的路由结构和功能行为
- 保持 Ant Design 6 + Pro Components 组件体系不变
- API 接口不变（Go 后端 REST API，`{ ok, data }` 包装）
- 不引入新的 UI 组件库
- 数据请求方案保持 `@tanstack/react-query` 不变
- 验收标准：`npm run lint`（biome + tsc）通过、`npm test` 全部通过、`npm run build` 成功

## 七、建议执行顺序

1. 类型完善（api.ts 类型抽离 → 消灭 any，为后续重构打底）
2. 合并 ErrorForms、建立共享层
3. 按页面拆分大组件（data → monitor → schedule → sync → Overview → system）
4. 逐页补 hooks 与组件测试
5. 主题 token 化（放最后，避免与组件拆分产生冲突）
