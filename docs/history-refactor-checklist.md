# History 页面重构检查清单

**日期：** 2026-06-18
**状态：** History 重构完成

---

## Phase 0: 准备

- [x] 补充 History 回归测试（筛选区、数据表、分页区、查询/导出/跳转行为）
- [x] 确认 1366×768 下所有断言通过
- [x] 创建本检查清单
- [x] 记录当前实测行数

## Phase 1: 最小 DataTable 迁移

- [x] 将 HistoryPage 中手写 QTableWidget 创建逻辑迁移为 DataTable
- [x] 保留分页控件（btn_prev / btn_next / lbl_curr_page / jump_box / lbl_page_info）
- [x] 保留 load_history / prev_page / next_page / export_data / apply_quick_filter 行为
- [x] DataTable 只负责显示 rows，不负责分页状态
- [x] 状态列 StatusChip 通过 data_table.table 属性设置 cell widget
- [x] 测试：DataTable 使用、行数正确、StatusChip 保持、分页保持

## Phase 2: HistoryFilterPanel 提取

- [x] 创建 `src/gui/pages/_history_filter_panel.py`
- [x] 封装搜索框、时间范围、状态、类型 4 个筛选控件
- [x] 保留 1366 宽度下 2x2 布局、宽屏 1x4 布局（resizeEvent 内部处理）
- [x] 提供 search_text / selected_days / selected_status / selected_sync_type 只读属性
- [x] 提供 set_quick_filter() 方法供 apply_quick_filter 使用
- [x] 支持 returnPressed 触发查询回调
- [x] 测试：1366×768 compact 布局、1600×900 wide 布局、属性、set_quick_filter、returnPressed

## Phase 3: HistoryPaginationCard 提取

- [x] 创建 `src/gui/pages/_history_pagination_card.py`
- [x] 封装 lbl_page_info / btn_prev / btn_next / lbl_curr_page / jump_box
- [x] 提供 update_state(current_page, total_records, page_size) 方法
- [x] 提供 on_prev / on_next / on_jump 回调参数
- [x] HistoryPage 别名属性兼容现有测试
- [x] 测试：实例化、first page 禁用、middle page 启用、页面集成

## Phase 4: 集成验证与收尾

- [x] 1366×768 集成测试（FilterPanel、DataTable、PaginationCard、primary actions 可见）
- [x] 分页行为回归（prev/next 更新 current_page、jump_box 触发 load_history）
- [x] 全量 GUI 测试通过（147 passed）
- [x] git diff --check clean
- [x] 更新 frontend-refactoring-plan.md（History 标记完成）

---

## 最终行数

| 文件 | 行数 |
|------|------|
| history_page.py | 254 |
| _history_filter_panel.py | 107 |
| _history_pagination_card.py | 68 |

## 最终职责边界

| 职责 | 组件 | 页面 |
|------|------|------|
| 筛选控件 UI + 响应式 | HistoryFilterPanel | ❌ |
| 分页控件 UI + 状态更新 | HistoryPaginationCard | ❌ |
| 数据表格展示 | DataTable | ❌ |
| 状态列 StatusChip | StatusChip + DataTable | ❌ |
| 筛选值读取 | ✅ 属性 | ✅ 读取 |
| 分页状态 | ❌ | ✅ current_page / total_records / page_size |
| load_history / 查询 | ❌ | ✅ |
| prev_page / next_page | ❌ | ✅ |
| export_data | ❌ | ✅ |
| apply_quick_filter | ❌ | ✅ |
| btn_query / btn_export | ❌ | ✅ |
