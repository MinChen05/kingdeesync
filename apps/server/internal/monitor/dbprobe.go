// Package monitor 提供目标数据库的定期探活能力。
// （原因：周日只跑全量不跑增量，目标库宕机此前只能等下一次任务触发才被发现，存在近一天的监控盲区）
package monitor

import (
	"context"
	"log"
	"sync"
	"time"
)

// ProbeResult 描述一次状态翻转。healthy=true 表示恢复，此时 DownFor 为总中断时长。
type ProbeResult struct {
	Healthy   bool
	DownSince time.Time
	DownFor   time.Duration
}

// DBProbe 周期性调用 probe，仅在通/断状态翻转时触发 onTransition 回调。
type DBProbe struct {
	probe        func(context.Context) error
	interval     time.Duration
	onTransition func(ProbeResult)
	done         chan struct{}
	stopOnce     sync.Once

	// 状态机字段，仅在探活 goroutine / check 中访问；测试通过 check 驱动。
	hasState  bool
	healthy   bool
	downSince time.Time
}

// New 创建一个探活器。interval 小于 1 秒时兜底为 1 秒，避免异常配置导致忙轮询。
func New(probe func(context.Context) error, interval time.Duration, onTransition func(ProbeResult)) *DBProbe {
	if interval < time.Second {
		interval = time.Second
	}
	return &DBProbe{
		probe:        probe,
		interval:     interval,
		onTransition: onTransition,
		done:         make(chan struct{}),
	}
}

// Start 启动后台探活循环，启动后立即执行第一次探活。
func (p *DBProbe) Start() {
	go func() {
		p.check()
		ticker := time.NewTicker(p.interval)
		defer ticker.Stop()
		for {
			select {
			case <-p.done:
				return
			case <-ticker.C:
				p.check()
			}
		}
	}()
}

// Stop 停止探活循环，可安全多次调用。
func (p *DBProbe) Stop() {
	p.stopOnce.Do(func() { close(p.done) })
}

// check 执行一次探活并推进状态机：
// - 首次探活即失败也回调（启动时目标库已断必须立即可知）
// - 持续失败不重复回调（避免告警轰炸）
// - 恢复时携带总中断时长
func (p *DBProbe) check() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	err := p.probe(ctx)
	healthy := err == nil

	switch {
	case !p.hasState:
		p.hasState = true
		p.healthy = healthy
		if !healthy {
			p.downSince = time.Now()
			log.Printf("[DBPROBE] target database unreachable at startup: %v", err)
			p.emit(ProbeResult{Healthy: false, DownSince: p.downSince})
		}
	case healthy && !p.healthy:
		downFor := time.Since(p.downSince)
		log.Printf("[DBPROBE] target database recovered after %v", downFor)
		p.healthy = true
		p.emit(ProbeResult{Healthy: true, DownSince: p.downSince, DownFor: downFor})
		p.downSince = time.Time{}
	case !healthy && p.healthy:
		p.healthy = false
		p.downSince = time.Now()
		log.Printf("[DBPROBE] target database became unreachable: %v", err)
		p.emit(ProbeResult{Healthy: false, DownSince: p.downSince})
	}

	setLastState(healthy, time.Now())
}

func (p *DBProbe) emit(r ProbeResult) {
	if p.onTransition == nil {
		return
	}
	p.onTransition(r)
}

// 包级最近状态，供 dashboard 等只读展示方使用。
var (
	lastStateMu      sync.RWMutex
	lastStateHealthy *bool
	lastStateAt      time.Time
)

func setLastState(healthy bool, at time.Time) {
	lastStateMu.Lock()
	defer lastStateMu.Unlock()
	lastStateHealthy = &healthy
	lastStateAt = at
}

// LastState 返回最近一次探活结果与时间；从未探活时 ok=false。
func LastState() (healthy bool, at time.Time, ok bool) {
	lastStateMu.RLock()
	defer lastStateMu.RUnlock()
	if lastStateHealthy == nil {
		return false, time.Time{}, false
	}
	return *lastStateHealthy, lastStateAt, true
}
