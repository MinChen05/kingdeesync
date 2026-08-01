// Package retry 提供指数退避重试机制。
// 用于金蝶 API 调用、数据库写入等可恢复性失败的场景。
package retry

import (
	"context"
	"errors"
	"fmt"
	"log"
	"math"
	"math/rand"
	"net"
	"net/http"
	"strings"
	"time"
)

// Config 重试配置。
type Config struct {
	// MaxAttempts 最大尝试次数（含首次），默认 4。
	MaxAttempts int
	// InitialInterval 初始重试间隔，默认 1s。
	InitialInterval time.Duration
	// MaxInterval 最大重试间隔，默认 10s。
	MaxInterval time.Duration
	// BackoffFactor 退避系数，默认 2.0。
	BackoffFactor float64
	// Jitter 是否添加随机抖动，默认 true。
	Jitter bool
}

// DefaultConfig 返回默认重试配置。
func DefaultConfig() Config {
	return Config{
		MaxAttempts:     4,
		InitialInterval: 1 * time.Second,
		MaxInterval:     10 * time.Second,
		BackoffFactor:   2.0,
		Jitter:          true,
	}
}

// ShouldRetryFn 自定义判断是否重试的函数。
// 返回 true 表示该错误可重试。
type ShouldRetryFn func(err error) bool

// DefaultShouldRetry 默认的可重试判断逻辑：
// - HTTP 5xx
// - 连接超时 / 连接拒绝 / 连接重置
// - DNS 解析失败
// - 包含 "timeout" / "context deadline exceeded" / "connection refused" 的错误
func DefaultShouldRetry(err error) bool {
	if err == nil {
		return false
	}

	msg := strings.ToLower(err.Error())

	// 超时类
	if strings.Contains(msg, "timeout") || strings.Contains(msg, "context deadline exceeded") {
		return true
	}

	// 连接类
	var opErr *net.OpError
	if errors.As(err, &opErr) {
		if errors.Is(opErr, net.ErrClosed) ||
			strings.Contains(msg, "connection refused") ||
			strings.Contains(msg, "connection reset") {
			return true
		}
	}

	// HTTP 5xx（如果错误信息中包含状态码）
	if strings.Contains(msg, "http") && (strings.Contains(msg, "500") || strings.Contains(msg, "502") ||
		strings.Contains(msg, "503") || strings.Contains(msg, "504")) {
		return true
	}

	// DNS 解析失败
	var dnsErr *net.DNSError
	if errors.As(err, &dnsErr) {
		return true
	}

	return false
}

// Retry 执行带重试的操作。
// fn: 要执行的操作，返回 error。
// cfg: 重试配置。
// shouldRetry: 自定义可重试判断，nil 则使用 DefaultShouldRetry。
func Retry(fn func() error, cfg Config, shouldRetry ShouldRetryFn) error {
	return RetryContext(context.Background(), fn, cfg, shouldRetry)
}

// RetryContext executes a retryable operation while honoring cancellation.
func RetryContext(ctx context.Context, fn func() error, cfg Config, shouldRetry ShouldRetryFn) error {
	if ctx == nil {
		ctx = context.Background()
	}
	if cfg.MaxAttempts <= 0 {
		cfg.MaxAttempts = DefaultConfig().MaxAttempts
	}
	if cfg.InitialInterval <= 0 {
		cfg.InitialInterval = DefaultConfig().InitialInterval
	}
	if cfg.MaxInterval <= 0 {
		cfg.MaxInterval = DefaultConfig().MaxInterval
	}
	if cfg.BackoffFactor <= 0 {
		cfg.BackoffFactor = DefaultConfig().BackoffFactor
	}
	if shouldRetry == nil {
		shouldRetry = DefaultShouldRetry
	}

	var lastErr error
	for attempt := 1; attempt <= cfg.MaxAttempts; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}
		err := fn()
		if err == nil {
			return nil
		}

		lastErr = err

		if !shouldRetry(err) {
			log.Printf("[RETRY] Attempt %d/%d: non-retryable error: %v", attempt, cfg.MaxAttempts, err)
			return err
		}

		if attempt == cfg.MaxAttempts {
			log.Printf("[RETRY] Attempt %d/%d: exhausted, last error: %v", attempt, cfg.MaxAttempts, err)
			break
		}

		// 计算退避间隔
		interval := calculateInterval(cfg, attempt)
		log.Printf("[RETRY] Attempt %d/%d failed: %v. Retrying in %v...", attempt, cfg.MaxAttempts, err, interval)
		timer := time.NewTimer(interval)
		select {
		case <-timer.C:
		case <-ctx.Done():
			if !timer.Stop() {
				select {
				case <-timer.C:
				default:
				}
			}
			return ctx.Err()
		}
	}

	return fmt.Errorf("all %d attempts failed: %w", cfg.MaxAttempts, lastErr)
}

// RetryWithResult 执行带重试的操作，并返回结果。
// fn: 要执行的操作，返回 (T, error)。
func RetryWithResult[T any](fn func() (T, error), cfg Config, shouldRetry ShouldRetryFn) (T, error) {
	return RetryWithResultContext(context.Background(), fn, cfg, shouldRetry)
}

// RetryWithResultContext is the context-aware variant of RetryWithResult.
func RetryWithResultContext[T any](ctx context.Context, fn func() (T, error), cfg Config, shouldRetry ShouldRetryFn) (T, error) {
	var zero T
	err := RetryContext(ctx, func() error {
		result, err := fn()
		if err != nil {
			return err
		}
		zero = result
		return nil
	}, cfg, shouldRetry)
	return zero, err
}

// calculateInterval 计算第 attempt 次重试的间隔。
func calculateInterval(cfg Config, attempt int) time.Duration {
	// 指数退避: initial * factor^(attempt-1)
	backoff := float64(cfg.InitialInterval) * math.Pow(cfg.BackoffFactor, float64(attempt-1))

	// 限制最大值
	if backoff > float64(cfg.MaxInterval) {
		backoff = float64(cfg.MaxInterval)
	}

	interval := time.Duration(backoff)

	// 添加抖动（0~100% 随机）
	if cfg.Jitter {
		jitter := float64(interval) * rand.Float64()
		interval = time.Duration(jitter)
	}

	return interval
}

// IsHTTPRetryableStatusCode 判断 HTTP 状态码是否可重试。
func IsHTTPRetryableStatusCode(statusCode int) bool {
	return statusCode == http.StatusTooManyRequests || // 429
		statusCode >= 500 && statusCode < 600
}
