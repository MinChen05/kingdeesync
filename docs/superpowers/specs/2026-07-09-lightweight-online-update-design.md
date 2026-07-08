---
comet_change: add-lightweight-online-update
role: technical-design
canonical_spec: openspec
status: draft
---

# 轻量在线更新技术设计

## 结论

采用“内网 HTTPS 静态 `latest.json` + 完整 zip 发布包 + 独立 updater 进程 + 本地配置保护”的最小可行方案。（原因：当前项目是 Python/PySide6 + PyInstaller 桌面程序，静态 manifest 可以避免新增服务端复杂度，完整包替换比增量补丁更容易验证和回滚）

本变更不涉及 SQL Server 表结构调整，不执行数据库迁移，不写业务表，不改变金蝶同步写入链路。（原因：在线更新只负责客户端程序升级，数据库变更必须单独评审、备份并校验行数）

## 范围

- 在桌面端提供手动“检查更新”入口，第一版不做静默后台安装。（原因：用户确认能降低生产客户端误升级风险）
- 从内网 HTTPS 静态地址读取 `latest.json`，比较本地版本与远程版本。（原因：静态文件托管最小可行，也便于内网部署）
- 下载完整发布 zip，校验 SHA256 后交给独立 updater 安装。（原因：完整包减少逐文件依赖分析和补丁兼容风险）
- updater 替换程序文件时保护 `config.local.ini`、`config.ini`、`config.ini.backup`、`logs/`。（原因：这些文件属于现场运行状态，升级不能覆盖或删除）
- 安装失败时从备份回滚，并在下次启动展示失败原因。（原因：现场客户端必须优先保持可启动、可诊断）

## 版本与 Manifest

本地版本来源新增为 `src/version.py`，提供 `APP_VERSION` 常量和只读访问函数。（原因：GUI、更新服务、打包脚本需要共享同一个版本来源）

第一版 manifest 使用静态 JSON 文件，推荐地址形态如下：

```text
https://intranet.example.com/kingdee-sync/updates/stable/latest.json
```

`latest.json` 格式：

```json
{
  "app": "kingdee-sync",
  "version": "1.4.0",
  "channel": "stable",
  "release_date": "2026-07-09",
  "min_supported_version": "1.0.0",
  "package_url": "https://intranet.example.com/kingdee-sync/releases/kingdee-sync-1.4.0.zip",
  "sha256": "64位hex编码",
  "size": 12345678,
  "force": false,
  "notes": [
    "修复同步异常提示",
    "优化桌面界面"
  ]
}
```

校验规则：

- `app` 必须等于 `kingdee-sync`。（原因：避免误读其他产品 manifest）
- `version`、`min_supported_version` 必须可按语义化版本比较。（原因：避免字符串比较导致 `1.10.0` 小于 `1.9.0`）
- `channel` 第一版固定支持 `stable`。（原因：先限制发布通道，避免测试包进入生产）
- `package_url` 必须使用 HTTPS。（原因：降低传输链路篡改风险）
- `sha256` 必须是 64 位十六进制字符串。（原因：下载包必须具备完整性校验依据）
- `size` 必须为正整数，下载后可选比对文件大小。（原因：提前发现截断下载或错误文件）

## 组件设计

### `src/services/update_service.py`

`UpdateService` 只负责非 GUI 更新逻辑：拉取 manifest、校验字段、比较版本、下载 zip、计算 SHA256、返回结构化结果。（原因：业务逻辑与界面解耦，便于用 mock 覆盖网络和哈希分支）

它不得导入数据库写入模块，也不得调用同步服务。（原因：更新检查不应触发任何 SQL Server 业务写入）

### `src/updater.py`

独立 updater 通过命令行参数运行，接收安装目录、已验证 zip、主进程 PID、目标 exe 名称、旧版本和新版本。（原因：主程序运行时不能稳定覆盖自身 exe/dll，独立进程边界更清晰）

updater 负责：

1. 等待主进程退出。（原因：避免 Windows 文件占用导致替换失败）
2. 校验安装目录在预期目录内。（原因：避免错误参数覆盖任意路径）
3. 解压 zip 到临时目录并拒绝 zip-slip 路径。（原因：防止恶意包写出安装目录）
4. 备份当前程序文件。（原因：替换失败时可以恢复）
5. 替换程序文件，同时保护本地配置和日志。（原因：升级不能破坏现场配置与历史日志）
6. 启动新版本主程序。（原因：用户可立即确认升级结果）
7. 失败时回滚并写入 `update-failed.json`。（原因：下次启动可以展示可诊断错误）

### GUI 入口

第一版入口放在系统设置页，新增当前版本展示、“检查更新”按钮、更新可用信息和错误反馈。（原因：设置页已经承载系统配置与连接测试，用户自然会在这里寻找升级入口）

GUI 只调用 `UpdateService` 并展示结果，不直接解压或替换文件。（原因：界面层不应承担高风险文件操作）

### 打包脚本

发布流程扩展 `create_deploy.py` 或新增 `scripts/release/build_update_package.py`，生成完整 zip、SHA256 和 `latest.json` 示例。（原因：让发布产物和 manifest 一起生成，降低人工填错 hash 的风险）

发布包必须排除 `config.ini`、`config.local.ini`、`config.ini.backup`、`logs/`。（原因：这些文件包含现场配置或运行数据，不能随包分发）

## 客户端流程

1. 用户在 GUI 点击“检查更新”。（原因：第一版保持显式操作）
2. 客户端下载 `latest.json`，超时时间建议 5 秒。（原因：避免网络异常卡住桌面界面）
3. 校验 manifest 并比较版本。（原因：只有可信且更新的版本才进入下载）
4. 有更新时展示版本、发布日期、更新说明、包大小。（原因：用户确认前应知道变更内容）
5. 用户确认后下载 zip 到临时目录。（原因：下载失败不影响当前安装目录）
6. 校验 SHA256，失败则删除下载包并阻止安装。（原因：不能安装损坏或被篡改的包）
7. 主程序启动 updater 并退出。（原因：释放 exe/dll 文件句柄）
8. updater 安装、回滚或记录失败状态。（原因：安装阶段必须具备恢复能力）
9. 新版本启动后读取上次更新状态并展示成功或失败。（原因：用户需要明确结果）

## 回滚策略

备份目录建议为：

```text
backups/update-<旧版本>-<YYYYMMDDHHMMSS>/
```

替换前先复制当前程序文件到备份目录，保护列表不参与覆盖：

```text
config.local.ini
config.ini
config.ini.backup
logs/
backups/
```

如果替换失败，updater 将备份恢复到安装目录，并写入：

```text
update-failed.json
```

失败记录包含 `from_version`、`to_version`、`stage`、`message`、`rollback_success`、`timestamp`。（原因：现场排障需要知道失败阶段和回滚是否成功）

## 安全边界

- 必须使用 HTTPS 下载 manifest 和 zip。（原因：降低中间人篡改风险）
- 必须校验 SHA256。（原因：确认下载包与发布端 manifest 一致）
- 必须拒绝 zip-slip。（原因：防止压缩包覆盖安装目录之外的文件）
- 必须限制 updater 的安装目录参数。（原因：避免 updater 被滥用为任意文件覆盖工具）
- 第一版不自动执行 SQL 脚本。（原因：数据库变更需要独立审批、备份和行数校验）
- 第一版不做代码签名强制校验，但将其列为后续增强。（原因：SHA256 依赖 manifest 可信，代码签名可进一步确认发布者身份）

## 配置热更新边界

适合后续配置热更新：

- 金蝶接口字段映射。（原因：映射变化频繁，适合远程配置降低发版频率）
- 表单启停状态和默认任务参数。（原因：属于业务配置，不必每次替换二进制）
- 查询字段列表和只读校验规则。（原因：可以在兼容版本范围内调整）
- UI 文案和非关键提示。（原因：低风险且不影响数据写入）

必须走程序更新：

- 数据库写入逻辑和 SQL 生成逻辑。（原因：直接影响数据正确性）
- 加密、认证、密码处理。（原因：属于安全敏感能力）
- updater 自身逻辑。（原因：更新器错误会影响后续所有升级）
- 新依赖、新 exe、新 dll、PySide6 结构性改动。（原因：需要二进制发布物承载）
- 数据库 schema 变更。（原因：必须单独说明影响、备份和行数校验）

## 测试策略

- 单元测试覆盖版本比较、manifest 校验、HTTPS 校验、SHA256 校验。（原因：这些是更新安全的核心分支）
- `UpdateService` 使用 mock 覆盖无更新、有更新、网络失败、manifest 无效、hash 不匹配。（原因：避免测试依赖真实网络）
- updater 使用 dry-run 临时目录测试保护文件、zip-slip 拒绝、替换失败回滚。（原因：文件替换风险高，必须先在隔离目录验证）
- GUI 测试使用 mocked `UpdateService` 覆盖检查中、无更新、有更新、失败反馈。（原因：界面状态不能依赖真实更新服务）
- 发布脚本测试确认 zip 排除本机配置与日志，并生成正确 SHA256。（原因：发布环节最容易误带敏感配置）
- 验证说明必须写明 SQL Server 写入影响为无。（原因：满足项目数据库变更约束）

## OpenSpec 对齐

本 Design Doc 对齐 `openspec/changes/add-lightweight-online-update/`，细化了已确认的静态 manifest、完整包、独立 updater、本地配置保护与回滚策略。（原因：OpenSpec 定义 WHAT，本文件定义 HOW）
