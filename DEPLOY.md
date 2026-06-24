# 金蝶数据同步工具 - 服务器部署指南

## 快速部署

### 1. 解压程序
将 `金蝶数据同步工具` 文件夹复制到服务器目录，例如：
```
D:\Kingdee\
```

### 2. 运行配置向导
双击运行 `setup.bat` 或在命令行执行：
```bash
python setup_server.py
```

按照提示输入：
- **金蝶API配置**：域名/IP、账套ID、用户名、密码
- **数据库配置**：SQL Server 或 MySQL 连接信息
- **同步配置**：同步间隔、并发数等

配置向导会生成本机配置文件 `config.local.ini`。发布包只应包含 `config.example.ini` 模板，不要随包分发 `config.ini`、`config.local.ini` 或 `config.ini.backup`。

### 3. 创建数据库表
如果使用 SQL Server，执行建表脚本：
```bash
sqlcmd -S 服务器地址 -d 数据库名 -i src\tools\create_sqlserver_tables.sql
```

### 4. 启动程序
```bash
# GUI 模式
python main.py

# 或使用打包后的 EXE
金蝶数据同步工具.exe
```

## 配置文件说明

模板文件 `config.example.ini` 用于说明可配置项；实际运行配置保存在本机 `config.local.ini`。旧环境中已有的 `config.ini` 仍可兼容读取，但不建议提交或随包分发。

### [KINGDEE] - 金蝶API配置
| 参数 | 说明 | 示例 |
|------|------|------|
| login_url | 登录API地址 | http://192.168.1.100/k3cloud/... |
| query_url | 查询API地址 | http://192.168.1.100/k3cloud/... |
| acct_id | 账套ID | 229026784932743936 |
| username | 用户名 | administrator |
| password | 密码（支持加密） | ****** |

### [SQLSERVER] - SQL Server配置
| 参数 | 说明 | 示例 |
|------|------|------|
| host | 服务器地址 | 192.168.1.100 |
| port | 端口 | 1433 |
| database | 数据库名 | Kingdee |
| user | 用户名 | sa |
| password | 密码 | ****** |
| driver | ODBC 驱动 | ODBC Driver 18 for SQL Server |

### [SYNC] - 同步配置
| 参数 | 说明 | 默认值 |
|------|------|--------|
| auto_sync | 自动同步 | False |
| sync_interval | 同步间隔(分钟) | 120 |
| sync_type | 同步类型 | incremental |
| fetch_concurrency | 查询并发数 | 4 |
| table_concurrency | 表级并发数 | 8 |

## 安全建议

### 1. 密码保护
- 配置向导会自动加密密码
- 手动编辑时，可使用加密后的密文
- 配置文件权限设置为仅管理员可读

### 2. 网络安全
- 使用内网地址访问金蝶API
- 配置防火墙规则，仅允许必要端口
- 数据库使用强密码

### 3. 服务运行
建议使用 Windows 任务计划程序或 NSSM 将程序注册为服务：

```bash
# 使用 NSSM 安装服务
nssm install KingdeeSync "D:\Kingdee\金蝶数据同步工具.exe"
nssm set KingdeeSync AppDirectory "D:\Kingdee"
nssm start KingdeeSync
```

## 故障排查

### 1. 连接测试失败
- 检查金蝶API地址是否正确
- 确认账套ID、用户名、密码无误
- 检查网络连通性

### 2. 数据库连接失败
- 确认 SQL Server/MySQL 服务已启动
- 检查防火墙设置
- 验证用户名密码和数据库权限

### 3. 同步数据异常
- 查看日志文件：`logs/app.log`
- 检查金蝶系统中的数据是否正常
- 确认数据库表结构已创建

## 日志文件

日志位于 `logs/` 目录：
- `app.log` - 主日志文件
- `app.jsonl` - JSON格式日志
- `debug_startup.txt` - 启动调试信息

## 联系支持

如遇问题，请提供以下信息：
1. 错误日志内容
2. 配置文件（去除密码，优先提供 `config.local.ini` 的脱敏内容）
3. 操作系统版本
4. Python 版本
