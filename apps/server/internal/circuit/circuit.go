// Package circuit 提供熔断器封装，基于 github.com/sony/gobreaker。
// 用于在金蝶 API 连续失败时自动熔断，避免雪崩。
package circuit

import (
	"log"
	"sync"
	"time"

	gobreaker "github.com/sony/gobreaker"
)

var (
	// globalCB 全局金蝶 API 熔断器（单例）。
	globalCB *Breaker
	mu       sync.Mutex
)

// Breaker 封装 gobreaker.CircuitBreaker，提供日志和状态回调。
type Breaker struct {
	cb   *gobreaker.CircuitBreaker
	name string
}

// Config 熔断器配置。
type Config struct {
	// Name 熔断器名称，用于日志标识。
	Name string
	// MaxRequests Half-Open 状态下允许的最大请求数，默认 1。
	MaxRequests uint32
	// Timeout Open 状态持续多久后进入 Half-Open，默认 60s。
	Timeout time.Duration
	// ReadyToTripThreshold 连续失败多少次触发熔断，默认 5。
	ReadyToTripThreshold int
}

// DefaultConfig 返回默认配置。
func DefaultConfig() Config {
	return Config{
		Name:                 "kingdee-api",
		MaxRequests:          1,
		Timeout:              60 * time.Second,
		ReadyToTripThreshold: 5,
	}
}

// New 创建一个新的熔断器。
func New(cfg Config) *Breaker {
	if cfg.Name == "" {
		cfg.Name = DefaultConfig().Name
	}
	if cfg.MaxRequests == 0 {
		cfg.MaxRequests = DefaultConfig().MaxRequests
	}
	if cfg.Timeout == 0 {
		cfg.Timeout = DefaultConfig().Timeout
	}
	if cfg.ReadyToTripThreshold <= 0 {
		cfg.ReadyToTripThreshold = DefaultConfig().ReadyToTripThreshold
	}

	threshold := uint32(cfg.ReadyToTripThreshold)
	settings := gobreaker.Settings{
		Name:        cfg.Name,
		MaxRequests: cfg.MaxRequests,
		Timeout:     cfg.Timeout,
		ReadyToTrip: func(counts gobreaker.Counts) bool {
			return counts.TotalFailures >= threshold
		},
		OnStateChange: func(name string, from gobreaker.State, to gobreaker.State) {
			log.Printf("[CIRCUIT] %s: state changed %s -> %s", name, from, to)
		},
	}

	cb := gobreaker.NewCircuitBreaker(settings)

	log.Printf("[CIRCUIT] %s: initialized (maxRequests=%d, timeout=%v, threshold=%d)",
		cfg.Name, cfg.MaxRequests, cfg.Timeout, cfg.ReadyToTripThreshold)

	return &Breaker{
		cb:   cb,
		name: cfg.Name,
	}
}

// Execute 通过熔断器执行操作（无返回值版本）。
func (b *Breaker) Execute(fn func() error) error {
	_, err := b.cb.Execute(func() (interface{}, error) {
		return nil, fn()
	})
	return err
}

// State 返回当前熔断器状态。
func (b *Breaker) State() gobreaker.State {
	return b.cb.State()
}

// Counts 返回当前统计信息。
func (b *Breaker) Counts() gobreaker.Counts {
	return b.cb.Counts()
}

// Name 返回熔断器名称。
func (b *Breaker) Name() string {
	return b.name
}

// String 返回熔断器状态字符串。
func (b *Breaker) String() string {
	return b.cb.State().String()
}

// ErrOpen 熔断器处于 Open 状态时返回的错误。
var ErrOpen = gobreaker.ErrOpenState

// ///////////////////////////////////////////////////////////////////
// 全局熔断器（用于金蝶 API，单例模式）
// ///////////////////////////////////////////////////////////////////

// InitGlobalBreaker 初始化全局金蝶 API 熔断器。
func InitGlobalBreaker(cfg Config) {
	mu.Lock()
	defer mu.Unlock()

	globalCB = New(cfg)
}

// GetGlobalBreaker 获取全局熔断器，nil 表示未初始化。
func GetGlobalBreaker() *Breaker {
	mu.Lock()
	defer mu.Unlock()
	return globalCB
}

// GlobalExecute 通过全局熔断器执行操作。
func GlobalExecute(fn func() error) error {
	mu.Lock()
	cb := globalCB
	mu.Unlock()

	if cb == nil {
		return fn()
	}

	return cb.Execute(fn)
}
