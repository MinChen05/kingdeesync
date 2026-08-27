# form-queries 配置说明（防漂移）

> 本文件是**容器运行时**读取的种子/兜底配置源。但**同步引擎以数据库为权威源**：只要数据库里已有该表单的记录，就完全不读本 JSON。本 JSON 只在数据库为空时用于全新部署初始化。

## 配置加载优先级（关键）

同步引擎通过 `config.GetFormQuery(formName)`（`apps/server/internal/config/config.go`）读取表单配置，顺序为：

1. **数据库（权威源，实时、无缓存）**：`go_form_queries` 表（SQLite `go_state.db`）。只要该表存在对应 `form_name` 记录，就返回数据库值，**完全不读本 JSON**。改库后下次同步即生效，无需重启。
2. **JSON（仅兜底 + 一次性种子）**：
   - 数据库 `go_form_queries` 表**完全为空**时，服务启动执行一次 `MigrateFormQueriesFromJSON`（`apps/server/internal/gormdb/gormdb.go`），把本 JSON 写入数据库；之后不再回灌。
   - 数据库没有该 form 记录时，回退到服务启动时加载进内存的 JSON 快照。

> **结论：要修改某个表单的同步配置，请改数据库（通过 Web 控制台 / API），而不是直接编辑本 JSON 文件。** 直接改 JSON 对已有数据库无效——数据库非空不会重新种子化，且数据库有记录时根本不读 JSON。

## 数据库权威源位置

| 环境 | 路径 |
|---|---|
| 容器内 | `/app/state/go_state.db`（`GORM_DB_PATH`） |
| 宿主机 | `.run/state/go_state.db` |

表：`go_form_queries`（`form_name` / `form_id` / `field_keys` / `filter_string` / `field_map` 等）。**判断某表单当前实际生效配置，一律以该表记录为准。**

## 各环境读取的 JSON 源

| 运行场景 | 工作目录(configDir) | 种子/兜底 JSON（按优先级） |
|---|---|---|
| 容器（生产） | `/app` | `packages/sync-config/form-queries.json`（bind mount，只读） |
| 本地 `go run`（cwd=项目根） | 项目根 | `packages/sync-config/form-queries.json` → `form-queries.json` |
| 本地 `go run`（cwd=`apps/server/cmd/server`） | `apps/server` | `apps/server/packages/sync-config/form-queries.json` → `apps/server/form-queries.json` |

> 数据库路径同理：容器用 `/app/state/go_state.db`，本地用 `configDir` 解析到的 `go_state.db`。

## 多副本对照（防改错文件）

仓库中存在多份 `form-queries.json`，**只有下表标注的场景会读取对应副本**，其余改动不会在运行时生效：

| 路径 | git 状态 | 运行时读取 | 角色 |
|---|---|---|---|
| `packages/sync-config/form-queries.json` | 跟踪 | ✅ 容器 + 项目根 go run | **权威种子源**，改种子默认值改这里 |
| `apps/server/packages/sync-config/form-queries.json` | 忽略 | ✅ 仅本地 go run(cwd=`apps/server/cmd/server`) | 本地开发副本，须与上一行保持一致 |
| `apps/server/form-queries.json` | 忽略 | ✅ 仅本地 go run 兜底候选 | 本地开发副本，须保持一致 |
| `form-queries.json`（仓库根目录） | 未跟踪 | ❌ 容器内不存在 | 游离参照文件，**改它不生效** |

## 修改配置的正确姿势

1. **改现有运行配置（推荐）**：用 Web 控制台 / API 写数据库。`GetFormQuery` 实时查库无缓存，保存后下次同步即生效，**无需重启**。
2. **改全新部署的种子默认值**：编辑 `packages/sync-config/form-queries.json`（权威种子源），并**同步** `apps/server/packages/sync-config/form-queries.json` 与 `apps/server/form-queries.json`，三份保持一致后再提交。
3. **避免**：只改仓库根目录 `form-queries.json`（运行时不读）；只改 `apps/server` 下副本而不同步 `packages/sync-config`（容器读不到）。

## 一致性自查

核对四份副本中同一表单（如应收单）的 `FieldKeys`/`FilterString` 是否一致：

```bash
python3 - <<'PY'
import json
files = ["form-queries.json", "packages/sync-config/form-queries.json",
         "apps/server/packages/sync-config/form-queries.json", "apps/server/form-queries.json"]
for f in files:
    d = json.load(open(f, encoding="utf-8"))["应收单"]
    print(f"{f}: {len(d['FieldKeys'].split(','))}字段 | {d['FilterString']}")
PY
```

> 注：各副本整文件 md5 可能不同（其他表单存在历史调试过滤差异），**最终生效值以数据库 `go_form_queries` 表实际记录为准**，本 JSON 仅用于全新部署初始化。
