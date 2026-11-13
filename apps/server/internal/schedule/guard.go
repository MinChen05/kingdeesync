package schedule

import (
	"context"
	"log"
	"sync"
	"time"

	"github.com/kingdee-sync/go/internal/config"
	"github.com/kingdee-sync/go/internal/db"
)

// 目标库内存授予排队守卫（ADR-0007 落地清单）。
// SQL Server 的授予队列按 FIFO 放行：一个拿不到内存的外部大请求会拖住其后所有
// 需要授予的查询，同步本轮注定空耗到看门狗超时，还会清空快照表、堆积暂存表。
var (
	grantGuardDefault  = 60 * time.Second
	grantGuardProbeTTL = 5 * time.Second

	// targetGrantWait 可注入，便于在无目标库连接的测试中验证判定逻辑
	targetGrantWait = db.MaxGrantWait

	// grantGuardThreshold 读取守卫阈值（原因：与本包 scheduledSyncRunner 的注入风格一致，
	// 避免为测试在 config 包暴露全局写入口）
	grantGuardThreshold = guardThresholdFromConfig

	skipNotifyMu   sync.Mutex
	skipNotifyHook func(jobName, reason string)
)

// guardThresholdFromConfig 优先取配置；配置未加载时回退包级默认值。
// 显式配置 -1 表示关闭守卫，因此只把 0 视为"未配置"。
func guardThresholdFromConfig() time.Duration {
	if d := config.GetGrantWaitGuard(); d != 0 {
		return d
	}
	return grantGuardDefault
}

// SetGrantQueueSkipNotifier 注册跳过本轮的通知回调（原因：跳过不产生 run 记录，
// 不通知就会变成静默停摆，与"仅异常打扰"的既有告警策略一致地走钉钉）。
func SetGrantQueueSkipNotifier(h func(jobName, reason string)) {
	skipNotifyMu.Lock()
	defer skipNotifyMu.Unlock()
	skipNotifyHook = h
}

func resolveGrantGuardThreshold() time.Duration {
	return grantGuardThreshold()
}

// shouldSkipForGrantQueue 判断目标库是否正被内存授予排队拖住。
// 判定不确定时一律放行（fail-open）：守卫的目的是省掉注定超时的空跑，
// 不能反过来把目标库的短暂抖动放大成同步停摆。
func shouldSkipForGrantQueue() (bool, string) {
	threshold := resolveGrantGuardThreshold()
	if threshold <= 0 {
		return false, ""
	}

	ctx, cancel := context.WithTimeout(context.Background(), grantGuardProbeTTL)
	defer cancel()

	wait, err := targetGrantWait(ctx)
	if err != nil {
		log.Printf("[Schedule] 目标库排队状态查询失败，按放行处理: %v", err)
		return false, ""
	}
	if wait < threshold {
		return false, ""
	}

	reason := "目标库内存授予排队 " + formatDurationShort(wait) +
		"（阈值 " + formatDurationShort(threshold) + "），本轮跳过：继续执行只会空耗预算并清空快照表"
	return true, reason
}

// GuardGrantQueueForTrigger 供调度入口之外的触发路径（API 手动同步等）复用同一排队守卫，
// 判定跳过时与调度侧一致地发出告警。
// （原因：2026-11-03 事故中慢的是 API 手动触发的全量，手动路径不经过 runJob、
// 完全绕过守卫，同样会发起注定超时的空跑并清空快照表，见 ADR-0007）
func GuardGrantQueueForTrigger(source string) (bool, string) {
	skip, reason := shouldSkipForGrantQueue()
	if skip {
		notifyGrantQueueSkip(source, reason)
	}
	return skip, reason
}

func notifyGrantQueueSkip(jobName, reason string) {
	skipNotifyMu.Lock()
	hook := skipNotifyHook
	skipNotifyMu.Unlock()
	if hook != nil {
		hook(jobName, reason)
	}
}

// formatDurationShort 把时长压成告警里可读的紧凑形式（原因：钉钉正文有长度观感约束）
func formatDurationShort(d time.Duration) string {
	switch {
	case d >= time.Hour:
		return d.Round(time.Minute).String()
	case d >= time.Minute:
		return d.Round(time.Second).String()
	default:
		return d.Round(time.Millisecond).String()
	}
}
