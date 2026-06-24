# styles.css → ColorTokens 映射表

**日期：** 2026-06-17
**状态：** Phase 2 完成

## 统计摘要

- 总 hex 出现：1136 次（不变，只替换值不增减出现次数）
- 唯一 hex 值：618 个（Phase 1 减 1，Phase 2 减 4）
- 精确命中 ColorTokens：139 次（12.2%）
- 近似命中：~35 次（剩余）
- 无 token：~962 次

## 映射分类

### A. 精确命中（CSS 值 = Token 值）

| CSS Hex | Token | 出现次数 | 语义 |
|---------|-------|---------|------|
| #FFFFFF | SURFACE_BASE | 81 | 白色背景/表面 |
| #4CA8F8 | ACCENT_600 | 7 | 主强调色 |
| #C24D4D | DANGER | 6 | 危险/错误 |
| #2578DA | ACCENT_700 | 5 | 深强调色 |
| #2E95D9 | SUCCESS | 3 | 成功（蓝色） |
| #F7FBFF | SURFACE_SUBTLE | 1 | 次级表面 |
| #F1C1C1 | DANGER_BORDER | 1 | 危险边框 |
| #B0861A | WARNING | 1 | 警告 |

### B. 近似命中（Phase 2 已替换 ✅）

| CSS Hex | 近似 Token | Token 值 | 出现 | 差异 | 状态 |
|---------|-----------|---------|------|------|------|
| #F8FBFF | SURFACE_SUBTLE | #F7FBFF | 11 | Δ1 in blue | ✅ 已替换 |
| #64748B | NEUTRAL_500 | #647F97 | 12 | Δ11 green, Δ12 blue | ✅ Phase 1 替换 |
| #EDF2F8 | NEUTRAL_100 | #EBF2F8 | 6 | Δ2 in red | ✅ 已替换 |
| #D7E6F3 | NEUTRAL_200 | #D7E3ED | 3 | Δ3 green, Δ6 blue | ✅ 已替换 |
| #EEF5FF | SURFACE_MUTED | #EEF6FD | 2 | Δ1 green, Δ2 blue | ✅ 已替换 |

### C. 高频无 Token（需新增或保留）

#### 文本色（CSS 独有色系，与 ColorTokens 不同）

| CSS Hex | 出现 | 用途 | 最近 Token | 建议 |
|---------|------|------|-----------|------|
| #1F2937 | 12 | 正文文本 | NEUTRAL_900 #14263A | 新增或保留 |
| #334155 | 16 | 菜单/次要文本 | NEUTRAL_700 #284157 | 新增或保留 |
| #0F172A | 16 | 深色标题 | 无 | 新增 |
| #64748B | 12 | 弱化文本 | NEUTRAL_500 #647F97 | 可替换 |
| #475569 | 7 | 次要文本 | 无 | 保留 |
| #708198 | 6 | 辅助文本 | 无 | 保留 |
| #1D1D1F | 6 | 深色文本 | 无 | 保留 |

#### 成功色（CSS 用绿色，Token 用蓝色）

| CSS Hex | 出现 | 语义 |
|---------|------|------|
| #16A67D | 18 | 成功主色（绿） |
| #0F8A6B | 7 | 成功深色 |
| #0F7B42 | 6 | 成功更深 |
| #178B68 | 6 | 成功中等 |
| #D2E9E0 | 8 | 成功边框 |
| #F8FFFC | 6 | 成功背景 |
| #EAFBF5 | 5 | 成功浅背景 |

**注意**：ColorTokens.SUCCESS = #2E95D9（蓝色），CSS 用绿色系。两者色相不同，替换会改变视觉语义。

#### 边框色

| CSS Hex | 出现 | 最近 Token | 建议 |
|---------|------|-----------|------|
| #DBE3F0 | 15 | STROKE_DEFAULT #D4E5F3 | 色差较大，保留 |

#### 背景色

| CSS Hex | 出现 | 最近 Token | 建议 |
|---------|------|-----------|------|
| #EDF6FF | 10 | ACCENT_100 #D8EEFF | 色差较大，保留 |
| #E8F0FF | 7 | ACCENT_50 #EFF8FF | 色差较大，保留 |

## Phase 1 落地（已完成）

替换 #64748B → NEUTRAL_500 (#647F97)：
- 12 次出现，语义为弱化文本
- 色差极小（Δ11 green, Δ12 blue），肉眼不可辨
- 替换后统一弱化文本色到 token 体系

## Phase 2 落地（已完成）

低风险近似命中替换，共 22 处：

| 替换 | Token | 次数 | 用途 | 风险 |
|------|-------|------|------|------|
| #F8FBFF → #F7FBFF | SURFACE_SUBTLE | 11 | 菜单栏/状态栏/表头/卡片/工具栏背景 | 极低，Δ1 blue |
| #EDF2F8 → #EBF2F8 | NEUTRAL_100 | 6 | 网格线/边框/hover 背景 | 极低，Δ2 red |
| #D7E6F3 → #D7E3ED | NEUTRAL_200 | 3 | 边框 | 极低，Δ3 green Δ6 blue |
| #EEF5FF → #EEF6FD | SURFACE_MUTED | 2 | 选中卡片/内联横幅背景 | 极低，Δ1 green Δ2 blue |

所有替换均为背景/边框/网格线用途，无文本色替换，无状态色替换。

## Phase 3 落地（已完成）

新增 CSS 文本色语义 token，CSS 已使用相同色值无需替换：

| 新增 Token | 值 | CSS 文本用途 | 非文本用途（保留） |
|-----------|-----|------------|----------------|
| TEXT_PRIMARY_DEEP | #0F172A | 14 处 `color:`（深色标题/强调文本） | 2 处 `selection-color:` |
| TEXT_PRIMARY_SOFT | #1F2937 | 11 处 `color:`（正文文本） | 1 处 `background-color:` |
| TEXT_SECONDARY_DEEP | #334155 | 15 处 `color:`（菜单/次要文本） | 1 处 `border:` |

CSS 中这些色值已是正确 hex，本次通过新增 Python token 建立了代码侧引用点。
非文本用途（selection-color、background-color、border）不替换，保留原值。

## Phase 4 落地（已完成）

CSS 绿色成功色系分析与 token 建立：

| 新增 Token | 值 | CSS 用途 | 出现 |
|-----------|-----|---------|------|
| SUCCESS_GREEN | #16A67D | 主成功色：文本(7)、背景(6)、边框(5) | 18 |
| SUCCESS_GREEN_DARK | #0F8A6B | 深成功文本（含 selection-color） | 7 |
| SUCCESS_GREEN_DEEP | #0F7B42 | 深层强调文本 | 6 |
| SUCCESS_GREEN_MEDIUM | #178B68 | 中等成功文本 | 6 |
| SUCCESS_GREEN_BORDER | #D2E9E0 | 成功边框 | 8 |
| SUCCESS_GREEN_BG | #F8FFFC | 成功浅背景 | 6 |
| SUCCESS_GREEN_BG_LIGHT | #EAFBF5 | 成功极浅背景 | 5 |

**决策**：保留 ColorTokens.SUCCESS = #2E95D9（蓝色）不变。
- 蓝色 SUCCESS 用于 Python 侧 LogPanel 等组件的动态状态色
- CSS 侧使用绿色成功色系，两者并行不冲突
- 后续如需统一，应作为独立重构项，不混入 token 治理

**未替换**：CSS 已使用相同色值，本次只建立 token 对应关系。

## Phase 5 落地（已完成）

高频蓝色/边框/警告色语义 token 建立：

### 蓝色交互色系

| 新增 Token | 值 | CSS 用途 | 出现 |
|-----------|-----|---------|------|
| INTERACTIVE_SURFACE | #2563EB | 交互表面（按钮背景10、边框4、文本3） | 17 |
| INTERACTIVE_PRESSED | #1D4ED8 | 按下/激活态文本(13)、背景(1)、边框(1)、选区(1) | 16 |
| INTERACTIVE_PRIMARY | #0F6CBD | 主交互文本(10)、边框(3)、背景(2) | 15 |

### 边框色

| 新增 Token | 值 | CSS 用途 | 出现 |
|-----------|-----|---------|------|
| STROKE_SOFT_BLUE | #DBE3F0 | 蓝色调柔和边框（全为 border 用途） | 15 |

### 蓝色背景色

| 新增 Token | 值 | CSS 用途 | 出现 |
|-----------|-----|---------|------|
| ACCENT_BG_SOFT | #EDF6FF | 柔和蓝色背景（全为 background-color） | 10 |
| ACCENT_HOVER_BG | #E8F0FF | 蓝色 hover 背景（全为 background-color） | 7 |

### 警告色

| 新增 Token | 值 | CSS 用途 | 出现 |
|-----------|-----|---------|------|
| WARNING_ORANGE_DEEP | #B14E24 | 深橙警告色（背景7、边框3） | 10 |

**未替换**：CSS 已使用相同色值，本次只建立 token 对应关系。

**与现有 Token 关系**：
- INTERACTIVE_* 与 ACCENT_* 色相不同（#2563EB vs #2578DA），用途不同（CSS 交互 vs Python 组件），保留并行
- STROKE_SOFT_BLUE (#DBE3F0) 与 STROKE_DEFAULT (#D4E5F3) 色差明显，保留为独立 token
- WARNING_ORANGE_DEEP (#B14E24) 与 WARNING (#B0861A) 色相不同（橙 vs 黄），保留并行

## 后续阶段建议

Phase 1-5 语义 token 建立完成，后续进入机制化护栏/按需治理阶段。

### 剩余未治理色值摘要

4+ 次出现且不精确命中 ColorTokens 的色值共 24 个。暂不合并原因：

| 色值 | 出现 | 暂不合并原因 |
|------|------|-------------|
| #FFF1F0 | 8 | 浅红背景，与 DANGER_BG (#FCEEEE) 色差明显 |
| #475569 | 7 | 次要文本，与 NEUTRAL_700 (#284157) 色相不同 |
| #DC2626 | 6 | 标准红色，与 DANGER (#C24D4D) 色相不同 |
| #708198 | 6 | 辅助文本，低频且无明确语义归属 |
| #1D1D1F | 6 | 近黑文本，与 NEUTRAL_900 (#14263A) 色差明显 |
| #C42B1C | 6 | 深红，主题局部色 |
| #E6F2FF | 6 | 浅蓝背景，与 ACCENT_BG_SOFT (#EDF6FF) 不同 |
| #D8CCB9 | 6 | 米色边框，主题局部色 |
| #F1F5FB | 5 | 浅灰蓝背景，低频 |
| #059669 | 5 | 绿色，与 SUCCESS_GREEN (#16A67D) 不同 |

其余 14 个色值均为 4 次出现，属低频主题局部色或状态色。

### 后续治理原则

- 不建议继续盲目新增 token，应按真实 UI 语义和使用场景按需治理
- 优先治理影响一致性的问题（如同一语义多种色值）
- 主题局部色、低频状态色可保留原值
- 新增组件必须使用已有 token，不允许引入新裸 hex
