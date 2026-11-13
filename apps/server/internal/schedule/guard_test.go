package schedule

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

// withGuardStub 注入排队探测与阈值，测试结束后恢复
// （原因：守卫阈值来自全局配置，改注入点而非改配置单例，避免测试间串味）
func withGuardStub(t *testing.T, probe func(context.Context) (time.Duration, error), threshold time.Duration) {
	t.Helper()
	oldProbe, oldThreshold := targetGrantWait, grantGuardThreshold
	targetGrantWait = probe
	grantGuardThreshold = func() time.Duration { return threshold }
	t.Cleanup(func() {
		targetGrantWait = oldProbe
		grantGuardThreshold = oldThreshold
	})
}

func TestShouldSkipForGrantQueue(t *testing.T) {
	longWait := func(context.Context) (time.Duration, error) { return 10 * time.Minute, nil }
	shortWait := func(context.Context) (time.Duration, error) { return 5 * time.Second, nil }
	failing := func(context.Context) (time.Duration, error) { return 0, errors.New("target db unreachable") }

	t.Run("超过阈值则跳过并给出原因", func(t *testing.T) {
		withGuardStub(t, longWait, time.Minute)
		skip, reason := shouldSkipForGrantQueue()
		if !skip {
			t.Fatal("排队 10 分钟应跳过本轮")
		}
		if !strings.Contains(reason, "内存授予排队") {
			t.Fatalf("reason = %q, 应写明内存授予排队", reason)
		}
	})

	t.Run("未达阈值放行", func(t *testing.T) {
		withGuardStub(t, shortWait, time.Minute)
		if skip, _ := shouldSkipForGrantQueue(); skip {
			t.Fatal("排队 5 秒不应触发跳过")
		}
	})

	t.Run("查询失败按放行处理", func(t *testing.T) {
		withGuardStub(t, failing, time.Minute)
		if skip, _ := shouldSkipForGrantQueue(); skip {
			t.Fatal("守卫探测失败时必须放行（原因：不能把目标库抖动放大成同步停摆）")
		}
	})

	t.Run("阈值非正数关闭守卫", func(t *testing.T) {
		withGuardStub(t, longWait, -1)
		if skip, _ := shouldSkipForGrantQueue(); skip {
			t.Fatal("阈值为 -1 时应关闭守卫，即使排队再久也放行")
		}
	})
}

func TestResolveGrantGuardThresholdFallsBackToDefault(t *testing.T) {
	oldThreshold := grantGuardThreshold
	t.Cleanup(func() { grantGuardThreshold = oldThreshold })

	// 配置未加载：默认阈值 60 秒
	grantGuardThreshold = func() time.Duration {
		if d := guardThresholdFromConfig(); d != 0 {
			return d
		}
		return grantGuardDefault
	}
	if got := resolveGrantGuardThreshold(); got != grantGuardDefault {
		t.Fatalf("默认阈值 = %v, want %v", got, grantGuardDefault)
	}
}

func TestNotifyGrantQueueSkipInvokesHook(t *testing.T) {
	oldHook := skipNotifyHook
	t.Cleanup(func() { skipNotifyHook = oldHook })

	var gotJob, gotReason string
	SetGrantQueueSkipNotifier(func(jobName, reason string) { gotJob, gotReason = jobName, reason })

	notifyGrantQueueSkip("default_incremental", "排队过久")
	if gotJob != "default_incremental" || gotReason != "排队过久" {
		t.Fatalf("回调收到 job=%q reason=%q", gotJob, gotReason)
	}

	// 未注册回调时不得 panic（原因：非主程序入口的测试与工具也会调用调度逻辑）
	SetGrantQueueSkipNotifier(nil)
	notifyGrantQueueSkip("default_incremental", "排队过久")
}

func TestFormatDurationShort(t *testing.T) {
	if got := formatDurationShort(9*time.Hour + 40*time.Minute); !strings.Contains(got, "9h") {
		t.Fatalf("小时级时长 = %q", got)
	}
	if got := formatDurationShort(1500 * time.Millisecond); got != "1.5s" {
		t.Fatalf("秒级时长 = %q, want 1.5s", got)
	}
}

func TestGuardGrantQueueForTrigger(t *testing.T) {
	oldHook := skipNotifyHook
	t.Cleanup(func() { skipNotifyHook = oldHook })

	t.Run("跳过时与调度侧一致地告警", func(t *testing.T) {
		withGuardStub(t, func(context.Context) (time.Duration, error) { return 10 * time.Minute, nil }, time.Minute)
		var gotSource, gotReason string
		SetGrantQueueSkipNotifier(func(source, reason string) { gotSource, gotReason = source, reason })

		skip, reason := GuardGrantQueueForTrigger("API 手动触发")
		if !skip {
			t.Fatal("排队 10 分钟时 API 触发路径应被拦截")
		}
		if gotSource != "API 手动触发" || gotReason != reason {
			t.Fatalf("告警收到 source=%q reason=%q, want source=API 手动触发 reason=%q", gotSource, gotReason, reason)
		}
	})

	t.Run("放行时不告警", func(t *testing.T) {
		withGuardStub(t, func(context.Context) (time.Duration, error) { return 5 * time.Second, nil }, time.Minute)
		notified := false
		SetGrantQueueSkipNotifier(func(string, string) { notified = true })

		if skip, _ := GuardGrantQueueForTrigger("API 手动触发"); skip {
			t.Fatal("排队 5 秒不应拦截 API 触发")
		}
		if notified {
			t.Fatal("放行时不应发出跳过告警")
		}
	})
}
