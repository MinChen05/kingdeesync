# 文档索引

## 基线说明

- Python 代码线是当前唯一主线。
- 默认数据库为 SQLServer，来源于 [config.ini](/d:/Kingdee/config.ini) 的 `[DATABASE] type = sqlserver`。
- MySQL 仅保留兼容支持，不再作为文档默认假设。
- `.NET` 目录是迁移工程，不是当前交付主线。
- 本地部署应优先使用未入库的 `config.local.ini`，仓库中的 `config.ini` 仅作为脱敏模板。

## 本目录建议关注

- 根目录 [README.md](/d:/Kingdee/README.md)：项目总览、启动方式、门禁、迁移口径。
- [../dotnet/README.md](/d:/Kingdee/dotnet/README.md)：`.NET` 迁移现状、限制和 parity 用法。
- [../src/config/form-queries.json](/d:/Kingdee/src/config/form-queries.json)：Python / .NET 共用的查询模板。
- [../src/config/tables.json](/d:/Kingdee/src/config/tables.json)：表单到 writer / 目标表映射。

## 当前约定

- 所有默认部署说明都应以 SQLServer 为主。
- 所有架构说明都应以 Python 主线为准。
- 涉及 `.NET` 的内容必须明确标注“迁移中”或“对账用途”，避免误读为正式替代。

## 常用命令

```bash
python main.py
python main.py check
python -m unittest tests.test_config_manager tests.test_filter_builder tests.test_sync_run_repository -v
python src/tools/compare_python_dotnet_batch.py --mode full --tables 表单A,表单B
```
