package retry

import (
	"context"
	"errors"
	"testing"
	"time"
)

func TestRetryContextCancellationDuringBackoff(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	time.AfterFunc(10*time.Millisecond, cancel)

	started := time.Now()
	err := RetryContext(ctx, func() error {
		return errors.New("retryable")
	}, Config{
		MaxAttempts:     3,
		InitialInterval: time.Hour,
		MaxInterval:     time.Hour,
		BackoffFactor:   1,
		Jitter:          false,
	}, func(error) bool { return true })

	if !errors.Is(err, context.Canceled) {
		t.Fatalf("RetryContext error = %v, want context canceled", err)
	}
	if elapsed := time.Since(started); elapsed > time.Second {
		t.Fatalf("RetryContext returned after %v, want prompt cancellation", elapsed)
	}
}
