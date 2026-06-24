# Sync 页面重构检查清单

**日期：** 2026-06-18
**状态：** Sync 重构完成

---

## Phase 0: 准备

- [x] 补充 Sync 回归测试（配置区、指标区、进度区、日志区、按钮可见性）
- [x] 确认 1366×768 下所有断言通过
- [x] 创建本检查清单
- [x] 记录当前实测行数

## Phase 1: SyncProgressCard 提取

- [x] 创建 `src/gui/pages/_sync_progress_card.py`
- [x] 继承 QFrame，自身设置 `property("ui", "win11-progress-card")`
- [x] 封装 progress_bar / progress_status_lbl
- [x] 提供 set_progress / set_status / reset 接口
- [x] SyncPage 使用该组件（别名兼容）
- [x] 测试：组件实例化、QFrame 类型、set_progress、set_status、reset、页面集成

## Phase 2: 集成验证与收尾

- [x] 1366×768 集成测试（按钮、配置区、执行区、日志区可见）
- [x] on_sync_progress / on_sync_finished 行为回归
- [x] 全量 GUI 测试通过
- [x] git diff --check clean
- [x] 更新 frontend-refactoring-plan.md（Sync 标记完成）

---

## 最终行数

| 文件 | 行数 |
|------|------|
| sync_page.py | 607 |
| _sync_progress_card.py | 48 |

## 最终已迁移组件

| 组件 | 来源 | 用途 |
|------|------|------|
| FieldRow | components/common.py | 配置行（表单范围 + 同步模式） |
| MetricCard | components/common.py | 执行指标卡（已同步记录、已用时间、运行状态） |
| LogPanel | components/common.py | 日志面板（clear/copy/export） |
| SyncProgressCard | pages/_sync_progress_card.py | 进度条 + 状态文本 |

## 职责边界

| 职责 | 组件 | 页面 |
|------|------|------|
| 配置行 UI | FieldRow | ❌ |
| 指标卡 UI | MetricCard | ❌ |
| 日志面板 UI | LogPanel | ❌ |
| 进度条 UI | SyncProgressCard | ❌ |
| 启动同步 / worker 信号 | ❌ | ✅ |
| 配置读取 / 按钮状态 | ❌ | ✅ |
| on_sync_progress / on_sync_finished | ❌ | ✅ |
