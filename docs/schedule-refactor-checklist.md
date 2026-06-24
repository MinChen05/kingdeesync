# Schedule 页面重构检查清单

**日期：** 2026-06-18
**状态：** Schedule 重构完成

---

## Phase 0: 准备

- [x] 补充 Schedule 回归测试（自动调度开关、间隔输入、预设按钮、状态面板、日志面板可见）
- [x] 确认 1366×768 下所有断言通过
- [x] 创建本检查清单
- [x] 记录当前实测行数

## Phase 1: ScheduleStatusPanel 提取

- [x] 创建 `src/gui/pages/_schedule_status_panel.py`
- [x] 封装 status_text / lbl_last_exec / lbl_next_exec
- [x] 提供 set_status / set_last_exec / set_next_exec / reset 接口
- [x] SchedulePage 使用该组件（别名兼容）
- [x] 测试：组件实例化、QFrame 类型、set 方法、reset、页面集成

## Phase 2: PresetButtonGroup 提取

- [x] 创建 `src/gui/pages/_schedule_preset_buttons.py`
- [x] 封装 15/30/60/120 分钟预设按钮
- [x] 提供 set_active(minutes) 方法
- [x] 提供 on_selected 回调参数
- [x] SchedulePage 使用该组件（别名兼容 interval_presets）
- [x] _refresh_interval_presets 委托给 preset_group.set_active
- [x] 测试：实例化、set_active、回调、页面集成

## Phase 3: 集成验证与收尾

- [x] 1366×768 集成测试保持通过
- [x] PresetButtonGroup 点击更新 spin_interval + active class
- [x] 全量 GUI 测试通过（167 passed）
- [x] git diff --check clean
- [x] 更新 frontend-refactoring-plan.md（Schedule 标记完成）

---

## 最终行数

| 文件 | 行数 |
|------|------|
| schedule_page.py | 544 |
| _schedule_status_panel.py | 44 |
| _schedule_preset_buttons.py | 41 |

## 最终已迁移组件

| 组件 | 来源 | 用途 |
|------|------|------|
| LogPanel | components/common.py | 日志面板 |
| FieldRow | components/common.py | 配置行（启用自动调度 + 执行间隔） |
| ScheduleStatusPanel | pages/_schedule_status_panel.py | 状态面板（运行状态 + 最近/下次执行） |
| PresetButtonGroup | pages/_schedule_preset_buttons.py | 快捷预设按钮（15/30/60/120 分钟） |

## 职责边界

| 职责 | 组件 | 页面 |
|------|------|------|
| 日志面板 UI | LogPanel | ❌ |
| 配置行 UI | FieldRow | ❌ |
| 状态面板 UI | ScheduleStatusPanel | ❌ |
| 预设按钮 UI | PresetButtonGroup | ❌ |
| 调度状态 / timer / handler | ❌ | ✅ |
| 配置读写 / 保存 | ❌ | ✅ |
| start_scheduler / stop_scheduler | ❌ | ✅ |
| check_status | ❌ | ✅ |
