package circuit

import "testing"

// TestInitGlobalBreakerIsIdempotent 验证全局熔断器初始化幂等：
// 重复 InitGlobalBreaker 不得替换已存在的熔断器（原因：替换会清零累计失败计数，
// "连续 N 次失败才熔断"在每次建金蝶客户端都初始化的场景下永远无法触发）。
func TestInitGlobalBreakerIsIdempotent(t *testing.T) {
	old := globalCB
	t.Cleanup(func() { globalCB = old })
	globalCB = nil

	InitGlobalBreaker(DefaultConfig())
	first := GetGlobalBreaker()
	if first == nil {
		t.Fatal("InitGlobalBreaker must set the global breaker")
	}

	// 累计一次失败，模拟熔断计数已产生
	_ = GlobalExecute(func() error { return errFake })

	InitGlobalBreaker(DefaultConfig())
	second := GetGlobalBreaker()
	if second != first {
		t.Fatal("second InitGlobalBreaker must not replace the global breaker")
	}
	if second.Counts().ConsecutiveFailures != 1 {
		t.Fatalf("consecutive error count lost after re-init: got %d, want 1", second.Counts().ConsecutiveFailures)
	}
}

type fakeError struct{}

func (fakeError) Error() string { return "fake" }

var errFake = fakeError{}
