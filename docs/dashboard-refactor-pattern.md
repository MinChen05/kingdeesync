# Dashboard 样板重构模式

**日期：** 2026-06-18
**状态：** 已验证（Dashboard Phase 0-5 完成）

---

## 组件提取顺序

按依赖关系从底向上提取：

```
1. 最小组件（无页面依赖）
   └── DataTable（columns / rows / empty state）

2. 页面私有子组件（依赖最小组件）
   └── DashboardStatusCards（依赖 Win11SummaryCard）
   └── DashboardCharts（依赖 HorizontalBarChart / SimpleLineChart）
   └── DashboardFailTable（依赖 DataTable）

3. 页面主文件（编排子组件 + 服务调用）
   └── DashboardPage
```

**原则**：先提取无依赖的原子组件，再提取依赖它们的子组件，最后改主页面。

---

## 接口设计原则

### 子组件职责边界

| 职责 | 子组件 | 页面 |
|------|--------|------|
| UI 渲染 | ✅ | ❌ 不手写 widget |
| 数据格式化 | ✅ 纯展示格式化 | ✅ 业务格式化 |
| 服务调用 | ❌ 禁止 | ✅ 唯一入口 |
| 业务状态 | ❌ 不保存 | ✅ 唯一持有者 |
| 事件通知 | ✅ Signal 或回调 | ✅ 处理事件 |

### 数据流

```
页面 → 子组件.update(data)    # 数据推送，单向
子组件 → 页面.on_xxx()        # 事件通知，回调或 Signal
```

### 接口风格

- **输入**：通过 `__init__` 参数配置，通过 `update()` / `set_data()` 推送数据
- **输出**：通过回调函数（`on_xxx: Callable`）或 Qt Signal 通知页面
- **不推荐**：让页面直接访问子组件内部 widget（如 `self._charts.trend_chart`），除非是测试断言

---

## 测试策略

### 组件级测试

| 测试类型 | 示例 |
|----------|------|
| 实例化 | `assertIsInstance(card, DashboardStatusCards)` |
| 数据更新 | `card.update(...)` → 断言 `card.value_label.text()` |
| 事件触发 | `btn.click()` → 断言回调被调用 |
| Token 使用 | 断言 `minimumHeight() == SizeTokens.XXX` |

### 页面级测试

| 测试类型 | 示例 |
|----------|------|
| 组件集成 | `assertIsInstance(page._charts, DashboardCharts)` |
| 行为回归 | 触发操作 → 断言 service 被调用 / 页面状态变化 |
| 分辨率 | `page.resize(1366, 768)` → 断言关键组件 `isVisible()` |
| 导航 | 点击 → 断言 `switch_to_page` / `apply_quick_filter` 被调用 |

### 不推荐的测试

- 像素级截图对比（过脆、CI 不稳定）
- 子组件内部 widget 直接访问（破坏封装）
- Mock 所有 service（只 mock 直接依赖）

---

## 常见陷阱

| 陷阱 | 后果 | 正确做法 |
|------|------|---------|
| 子组件调用 service | 耦合、无法独立测试 | 数据通过 `update()` 推入 |
| 子组件保存业务状态 | 多源头数据不一致 | 状态只在页面持有 |
| 提前抽象（排序/分页/筛选） | 过度设计、增加维护成本 | 最小接口先行，按需扩展 |
| 页面直接访问子组件内部 widget | 破坏封装、重构困难 | 通过子组件公开接口操作 |
| 忽略 token 规范 | 裸 hex / 裸像素累积 | 新增尺寸/颜色必须来自 design_tokens.py |
| 不写测试就提取 | 回归风险 | 测试先行，提取后测试必须通过 |

---

## DataTable 扩展边界

当前最小版本（Phase 3）：

```python
class DataTable(QFrame):
    def __init__(self, headers: list[str], *, parent=None)
    def set_data(rows: list[list[str]]) -> None
    def clear() -> None
    def set_empty_text(text: str) -> None
    @property table -> QTableWidget
```

**History 阶段再扩展**：
- 分页（`set_page(n)` / `set_page_size(n)`）
- 行选择回调（`row_clicked = Signal(int)`）
- 列宽配置（`set_column_widths(list[int])`）
- 加载态（`set_loading(bool)`）

**不要提前实现**：排序、筛选联动、虚拟滚动。
