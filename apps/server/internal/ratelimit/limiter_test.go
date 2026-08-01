package ratelimit

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestWaitContextHonorsDeadlineAfterTokensAreConsumed(t *testing.T) {
	limiter := New(Config{QPS: 1})
	if !limiter.Allow() || !limiter.Allow() {
		t.Fatal("failed to consume the limiter burst")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	if err := limiter.WaitContext(ctx); err == nil {
		t.Fatal("WaitContext unexpectedly acquired a token after deadline")
	}

	canceled, cancelNow := context.WithCancel(context.Background())
	cancelNow()
	if err := limiter.WaitContext(canceled); !errors.Is(err, context.Canceled) {
		t.Fatalf("WaitContext canceled error = %v, want context canceled", err)
	}
}

func TestGlobalLimiterBasicBehavior(t *testing.T) {
	InitGlobalLimiter(0)
	defer InitGlobalLimiter(0)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := GlobalWaitContext(ctx); err != nil {
		t.Fatalf("disabled global limiter returned error: %v", err)
	}

	GlobalSetQPS(1000)
	if err := GlobalWaitContext(context.Background()); err != nil {
		t.Fatalf("enabled global limiter returned error: %v", err)
	}
	GlobalSetQPS(0)
}
