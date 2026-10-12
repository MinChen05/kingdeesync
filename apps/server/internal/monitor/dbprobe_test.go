package monitor

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

type transitionRecorder struct {
	mu      sync.Mutex
	results []ProbeResult
}

func (r *transitionRecorder) on(p ProbeResult) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.results = append(r.results, p)
}

func (r *transitionRecorder) snapshot() []ProbeResult {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]ProbeResult(nil), r.results...)
}

// 状态机核心行为：首探失败告警一次、持续失败不重复、恢复告警携带总时长、再次断连再告警。
func TestDBProbeStateMachine(t *testing.T) {
	down := false
	probe := func(context.Context) error {
		if down {
			return errors.New("dial tcp: i/o timeout")
		}
		return nil
	}
	rec := &transitionRecorder{}
	p := New(probe, time.Second, rec.on)

	// 1. 启动时即断连 → 必须告警一次
	down = true
	p.check()
	if got := rec.snapshot(); len(got) != 1 || got[0].Healthy {
		t.Fatalf("首次失败应告警一次断连，实际: %+v", got)
	}

	// 2. 持续失败 → 不重复告警
	p.check()
	p.check()
	if got := rec.snapshot(); len(got) != 1 {
		t.Fatalf("持续失败不应重复告警，实际 %d 条", len(got))
	}

	// 3. 恢复 → 告警恢复且携带总中断时长
	down = false
	p.check()
	got := rec.snapshot()
	if len(got) != 2 || !got[1].Healthy {
		t.Fatalf("恢复应告警第二条，实际: %+v", got)
	}
	if got[1].DownFor <= 0 || got[1].DownSince.IsZero() {
		t.Fatalf("恢复告警应携带中断开始时间与总时长，实际: %+v", got[1])
	}

	// 4. 恢复后持续正常 → 不再告警
	p.check()
	if got := rec.snapshot(); len(got) != 2 {
		t.Fatalf("恢复后持续正常不应告警，实际 %d 条", len(got))
	}

	// 5. 再次断连 → 再告警一次
	down = true
	p.check()
	if got := rec.snapshot(); len(got) != 3 || got[2].Healthy {
		t.Fatalf("再次断连应再告警，实际: %+v", got)
	}
}

// 启动时目标库正常 → 不应产生任何告警。
func TestDBProbeHealthyStartupSilent(t *testing.T) {
	probe := func(context.Context) error { return nil }
	rec := &transitionRecorder{}
	p := New(probe, time.Second, rec.on)
	p.check()
	p.check()
	if got := rec.snapshot(); len(got) != 0 {
		t.Fatalf("启动即健康不应告警，实际: %+v", got)
	}
}

// Start 立即探一次并按间隔重复；Stop 幂等且停止探活。
func TestDBProbeStartStop(t *testing.T) {
	var mu sync.Mutex
	var probes int
	probe := func(context.Context) error {
		mu.Lock()
		defer mu.Unlock()
		probes++
		return nil
	}
	p := New(probe, 1100*time.Millisecond, nil)
	p.Start()
	time.Sleep(1500 * time.Millisecond)
	p.Stop()
	p.Stop() // 幂等，不应 panic

	mu.Lock()
	first := probes
	mu.Unlock()
	if first < 2 {
		t.Fatalf("1.5 秒内 1.1s 间隔应至少探 2 次（含启动首探），实际 %d", first)
	}

	time.Sleep(1300 * time.Millisecond)
	mu.Lock()
	after := probes
	mu.Unlock()
	if after != first {
		t.Fatalf("Stop 后不应继续探活：Stop 前 %d 次，之后 %d 次", first, after)
	}
}

// 过小的 interval 被抬升为 1 秒，防止误配置导致忙轮询。
func TestDBProbeIntervalFloor(t *testing.T) {
	p := New(func(context.Context) error { return nil }, time.Millisecond, nil)
	if p.interval != time.Second {
		t.Fatalf("interval 兜底应为 1s，实际 %v", p.interval)
	}
}
