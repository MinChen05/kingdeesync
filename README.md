# 金蝶数据同步工具

## 当前状态

- Python 版本仍是当前主线，日常开发和发布以本仓库 Python 实现为准。
- 默认数据库是 SQLServer，和 [config.ini](/d:/Kingdee/config.ini) 中 `[DATABASE] type = sqlserver` 保持一致。
- MySQL 仍保留兼容能力，但不再作为默认主路径。
- `.NET` 目录处于迁移进行中状态，用于分层迁移、CLI 验证和 Python/.NET 对账，不是当前生产主线。

## 功能概览

- 支持增量、全量、完全同步三种模式。
- 支持销售、生产、主数据、库存、采购、应付、科目余额表等表单同步。
- 支持手动同步、定时同步、连接测试、运行日志、历史页和仪表盘。
- 支持 SQLServer staging merge、writer registry、sync run/log repository、GUI service 等拆分后的新结构。

## 默认配置

程序当前默认读取：

```ini
[DATABASE]
type = sqlserver
```

SQLServer 为默认主配置：

```ini
[SQLSERVER]
host = 10.10.10.191
database = Kingdee
driver = ODBC Driver 17 for SQL Server
```

MySQL 配置仍保留，用于兼容历史部署或回归对比：

```ini
[MYSQL]
host = 192.169.0.32
database = kingdee
```

## 快速开始

1. 安装 Python 3.11+。
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 启动 GUI：

```bash
python main.py
```

4. 运行门禁：

```bash
python main.py check
```

## 质量门禁

当前仓库以如下命令作为基础门禁：

```bash
python -m ruff check .
python -m mypy
```

高价值回归测试可用：

```bash
python -m unittest tests.test_config_manager tests.test_filter_builder tests.test_sync_run_repository -v
```

## Python / .NET 对账

仓库保留 Python 与 .NET 的同批次对账脚本：

```bash
python src/tools/compare_python_dotnet_batch.py --mode full --tables 表单A,表单B
```

该脚本用于迁移阶段的结果对比，不表示 `.NET` 版本已替代 Python 主线。

## 目录说明

- [main.py](/d:/Kingdee/main.py)：统一 CLI / GUI 入口。
- [src/config](/d:/Kingdee/src/config)：配置读取、访问器和共享 JSON 配置。
- [src/core](/d:/Kingdee/src/core)：同步编排、数据库写入、日志仓储、writer、upsert engine。
- [src/gui](/d:/Kingdee/src/gui)：GUI 页面、worker 和组件。
- [src/services](/d:/Kingdee/src/services)：面向 GUI 或报表的服务层。
- [dotnet](/d:/Kingdee/dotnet)：`.NET` 迁移工程。

## 迁移口径

- Python：当前主线。
- SQLServer：当前默认数据库。
- MySQL：兼容路径。
- .NET：迁移中，持续做 parity 与模块替换，不直接替代当前 Python 交付链路。
