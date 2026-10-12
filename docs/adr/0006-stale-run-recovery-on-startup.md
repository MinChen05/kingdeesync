# ADR-0006: 启动时自动恢复超时的 running 运行

- **状态**：Accepted
- **日期**：2026-08-06（提交 `186b1ef`）
- **相关**：`api/contract`（状态机）、`RecoverStaleRunningRuns`

## 背景

进程 panic 或被强杀时，进行中的同步运行在状态库里遗留为 `running`。
后果连锁：引擎级"同一时刻仅一个活跃 run"保护被幽灵 run 占住，
后续调度与手动触发全部被拒；前端持续显示虚假的"同步中"。
（同类问题另有 `deffe76`：API 路径 `formQuery` 为 nil 触发 panic，是脏 running 的来源之一。）

## 决策

服务启动时执行 `RecoverStaleRunningRuns`：

- 超过 **3 小时**仍为 `running` 的运行判定为脏数据，自动标记 `failed`。
- 同时清理启动前已存在的历史脏数据。
- 阈值 3 小时 > API 同步超时 2 小时（ADR-0001），保证不误杀仍在合法执行的运行。

状态契约层面，`failed_abnormal_exit` 是唯一"只能由恢复流程产生"的状态，
正常执行路径不能转入（`api/contract.CanTransition`），保持事故痕迹可审计。

## 后果

- 正面：崩溃后无需手工改库即可恢复调度能力；自愈行为有 `recovery_test.go` 覆盖。
- 负面：3 小时阈值是经验值——若未来合法运行超过 2 小时上限，须同步调整本阈值；
  被标 `failed` 的运行不会自动重跑，需人工或调度下次触发。
