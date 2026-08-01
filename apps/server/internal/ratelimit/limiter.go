// Package ratelimit 提供基于 token bucket 的限流器。
// 用于控制金蝶 API 调用的 QPS，避免触发对方的限流策略。
package ratelimit

import (
	"context"
	"log"
	"sync"

	"golang.org/x/time/rate"
)

var (
	// globalLimiter 全局金蝶 API 限流器（单例）。
	globalLimiter *Limiter
	mu            sync.Mutex
)

// Limiter 封装 golang.org/x/time/rate.Limiter，提供友好的配置接口。
type Limiter struct {
	mu      sync.RWMutex
	limit   *rate.Limiter
	qps     float64
	enabled bool
}

// Config 限流器配置。
type Config struct {
	// QPS 每秒最大请求数，0 表示不限流。
	QPS float64
}

// New 创建一个新的限流器。
func New(cfg Config) *Limiter {
	if cfg.QPS <= 0 {
		return &Limiter{enabled: false, qps: 0}
	}

	// rate.Limit 是每秒令牌数，rate.Burst 是桶容量。
	// 桶容量设为 QPS*2，允许短时突发。
	burst := int(cfg.QPS * 2)
	if burst < 1 {
		burst = 1
	}

	return &Limiter{
		limit:   rate.NewLimiter(rate.Limit(cfg.QPS), burst),
		qps:     cfg.QPS,
		enabled: true,
	}
}

// Wait 等待直到获取令牌，或上下文取消。
func (l *Limiter) Wait() error {
	return l.WaitContext(context.Background())
}

// WaitContext waits for a token while honoring context cancellation.
func (l *Limiter) WaitContext(ctx context.Context) error {
	if l == nil {
		return nil
	}
	if ctx == nil {
		ctx = context.Background()
	}
	l.mu.RLock()
	enabled := l.enabled
	limit := l.limit
	l.mu.RUnlock()
	if !enabled || limit == nil {
		return nil
	}
	return limit.WaitN(ctx, 1)
}

// Allow 判断当前请求是否允许（不阻塞）。
func (l *Limiter) Allow() bool {
	if l == nil {
		return true
	}
	l.mu.RLock()
	enabled := l.enabled
	limit := l.limit
	l.mu.RUnlock()
	if !enabled || limit == nil {
		return true
	}
	return limit.Allow()
}

// SetQPS 动态调整 QPS。
func (l *Limiter) SetQPS(qps float64) {
	if l == nil {
		return
	}
	l.mu.Lock()
	defer l.mu.Unlock()
	if qps <= 0 {
		l.enabled = false
		l.qps = 0
		return
	}

	limit := rate.Limit(qps)
	burst := int(qps * 2)
	if burst < 1 {
		burst = 1
	}

	if l.limit == nil {
		l.limit = rate.NewLimiter(limit, burst)
	} else {
		l.limit.SetLimit(limit)
		l.limit.SetBurst(burst)
	}
	l.qps = qps
	l.enabled = true
	log.Printf("[RATELIMIT] QPS adjusted to %.2f", qps)
}

// ///////////////////////////////////////////////////////////////////
// 全局限流器（用于金蝶 API，单例模式）
// ///////////////////////////////////////////////////////////////////

// InitGlobalLimiter 初始化全局金蝶 API 限流器。
// qps: 每秒最大请求数，0 表示不限流。
func InitGlobalLimiter(qps float64) {
	mu.Lock()
	defer mu.Unlock()

	if globalLimiter != nil {
		globalLimiter.SetQPS(qps)
		return
	}

	globalLimiter = New(Config{QPS: qps})
	if qps > 0 {
		log.Printf("[RATELIMIT] Global Kingdee API limiter initialized: QPS=%.2f", qps)
	} else {
		log.Println("[RATELIMIT] Global Kingdee API limiter disabled (QPS=0)")
	}
}

// GlobalWait 等待全局限流器获取令牌。
func GlobalWait() error {
	return GlobalWaitContext(context.Background())
}

// GlobalWaitContext waits for the global limiter while honoring cancellation.
func GlobalWaitContext(ctx context.Context) error {
	mu.Lock()
	limiter := globalLimiter
	mu.Unlock()

	if limiter == nil {
		return nil
	}

	return limiter.WaitContext(ctx)
}

// GlobalSetQPS 动态调整全局限流器 QPS。
func GlobalSetQPS(qps float64) {
	mu.Lock()
	limiter := globalLimiter
	if limiter == nil {
		globalLimiter = New(Config{QPS: qps})
		mu.Unlock()
		return
	}
	mu.Unlock()
	limiter.SetQPS(qps)
}
