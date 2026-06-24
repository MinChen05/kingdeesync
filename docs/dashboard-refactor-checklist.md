# Dashboard 样板页重构检查清单

**日期：** 2026-06-18
**状态：** Phase 0-5 全部完成

---

## Phase 0: 准备

- [x] 补充 Dashboard 回归测试（summary cards、刷新按钮、响应式布局）
- [x] 确认 1366×768 下所有断言通过
- [x] 定义 DataTable 最小接口草案
- [x] 创建本检查清单

## Phase 1: DashboardStatusCards 提取

- [x] 创建 `src/gui/pages/_dashboard_status_cards.py`
- [x] 提取 `DashboardSummaryCard` 类
- [x] 提取 4 张 summary cards 为 `DashboardStatusCards` 组件
- [x] 页面通过组件接口更新数据
- [x] 测试：组件实例化、数据更新、token 使用
- [x] DashboardPage 使用该组件
- [x] 现有刷新/加载逻辑不变

## Phase 2: DashboardCharts 提取

- [x] 创建 `src/gui/pages/_dashboard_charts.py`
- [x] 提取趋势图 + 体积图 + 时间范围按钮
- [x] 通过回调 `on_window_days_changed` 通知页面窗口切换
- [x] 保持现有 `HorizontalBarChart` / `SimpleLineChart` 不变
- [x] 测试：组件实例化、7天/30天按钮回调、页面使用组件
- [x] DashboardPage 使用该组件
- [x] 现有刷新/加载逻辑不变

## Phase 3: DashboardFailTable + DataTable

- [x] 实现最小 DataTable 组件（components/data_table.py）
- [x] 创建 DashboardFailTable 组件（pages/_dashboard_fail_table.py）
- [x] 从 dashboard_page.py 提取失败表单表，接入 DashboardFailTable
- [x] 保留点击行跳转历史记录行为
- [x] 测试：DataTable 实例化、set_data、clear、DashboardFailTable 点击回调
- [x] DashboardPage 使用 DashboardFailTable

## Phase 4: 集成验证

- [x] Dashboard 页面重构后集成测试（128 passed）
- [x] 1366×768 分辨率验证（集成测试验证主操作区、summary cards、图表、失败表可见）
- [x] 全量 GUI 测试通过
- [x] git diff --check clean
- [x] Dashboard 页面无新增裸 hex / 内联 setStyleSheet
- [x] 新增组件无裸布局尺寸
- [x] QSS token governance 测试通过（4/4）

### 组件结构验证

- DashboardPage → DashboardStatusCards ✅
- DashboardPage → DashboardCharts ✅
- DashboardPage → DashboardFailTable ✅
- DashboardFailTable → DataTable ✅

### 行为回归验证

- refresh_dashboard 数据流正常 ✅
- 7天/30天切换仍刷新数据（回调 _on_window_days_changed） ✅
- 趋势图/吞吐图仍能接收数据 ✅
- 失败行点击仍跳转 History 并应用筛选 ✅

## Phase 5: 样板文档

- [x] 记录重构模式和组件提取规范（docs/dashboard-refactor-pattern.md）
- [x] 更新 frontend-guidelines.md（新增页面重构样板章节）
- [x] 更新 frontend-refactoring-plan.md（标记 Dashboard 完成，History 为下一目标）

---

## 最终实际行数

| 文件 | 行数 | 说明 |
|------|------|------|
| dashboard_page.py | 526 | 主页面（Phase 0 基线约 625 行） |
| _dashboard_status_cards.py | 59 | 状态卡片组件 |
| _dashboard_charts.py | 95 | 图表组件 |
| _dashboard_fail_table.py | 32 | 失败表组件 |
| data_table.py | 55 | 通用最小 DataTable |

## DataTable 最小接口

```python
class DataTable(QFrame):
    def __init__(self, headers: list[str], *, parent=None)
    def table -> QTableWidget          # 底层表格访问
    def set_empty_text(text: str)      # 设置空态文案
    def set_data(rows: list[list[str]]) # 替换所有行
    def clear()                        # 清空
    # property("ui", "win11-data-table-wrapper")
```

**不包含**：排序、分页、复杂加载态、列宽自定义、行选择回调。
这些能力在 History 页面重构阶段再按需扩展。

---

## 验收结果

| 检查项 | 结果 |
|--------|------|
| GUI 测试 | 128 passed ✅ |
| Token 使用 | 无裸 hex、无内联 setStyleSheet ✅ |
| QSS 护栏 | 4/4 passed ✅ |
| 分辨率 | 1366×768 集成测试通过 ✅ |
| 行为不变 | 所有回归测试通过 ✅ |
