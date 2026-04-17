# .NET Migration

## 迁移定位

- 本目录是 Python 主线向 `.NET` 的迁移工程。
- 当前生产主线仍是 Python，不是 `.NET`。
- 默认数据库口径与主仓库一致，都是 SQLServer 优先。
- `.NET` 目前主要承担分层迁移、CLI 验证和 Python/.NET 结果对账。

## 当前已包含内容

1. 分层工程结构：
   - `Kingdee.SyncTool.Domain`
   - `Kingdee.SyncTool.Application`
   - `Kingdee.SyncTool.Infrastructure`
   - `Kingdee.SyncTool.Cli`
2. 共享配置接入：
   - 读取根目录 `config.ini`
   - 读取 `src/config/tables.json`
   - 读取 `src/config/form-queries.json`
3. CLI 能力：
   - `sync`
   - `check`
   - `schedule`
   - `parity`
4. 迁移期对账能力：
   - 通过 `parity` 导出批次摘要
   - 通过 Python 脚本做跨运行时比对

## 当前限制

1. `.NET` 不是当前发布主线。
2. UI 迁移尚未完成，GUI 仍由 Python/PySide6 承担。
3. 迁移验收仍以 Python 结果为基准做 parity 校验。

## 快速开始

1. 安装 `.NET SDK 8.0+`
2. 构建：

```bash
dotnet build .\dotnet\Kingdee.SyncTool.sln
```

3. 运行 CLI：

```bash
dotnet run --project .\dotnet\src\Kingdee.SyncTool.Cli\Kingdee.SyncTool.Cli.csproj -- sync --mode incremental
```

## Parity 对账

`.NET` 侧：

```bash
dotnet run --project .\dotnet\src\Kingdee.SyncTool.Cli\Kingdee.SyncTool.Cli.csproj -- parity --mode full --tables 表单A,表单B --output .\logs\dotnet-parity.json
```

Python 侧：

```bash
python src\tools\compare_python_dotnet_batch.py --mode full --tables 表单A,表单B --output .\logs\python-dotnet-parity.json
```

## 文档口径

- Python：当前主线。
- SQLServer：默认数据库。
- MySQL：兼容路径。
- .NET：迁移中，必须通过 parity 和阶段验收后才考虑替代对应 Python 模块。
