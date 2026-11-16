package syncengine

import (
	"bytes"
	"log"
	"strings"
	"sync"
	"testing"
)

// 注册回调后 logMsg 必须把完整字段透传给回调
// （原因：修复调度轮从未注册回调导致实时日志全部丢弃的 bug 的正向回归）。
func TestLogMsgDeliversToRegisteredCallback(t *testing.T) {
	e := &SyncEngine{}
	var mu sync.Mutex
	var got []string
	e.SetLogCallback(func(runID, formName, level, message string) {
		mu.Lock()
		defer mu.Unlock()
		got = append(got, runID+"|"+formName+"|"+level+"|"+message)
	}, "run-1")
	if !e.HasLogCallback() {
		t.Fatal("SetLogCallback 之后 HasLogCallback 应为 true")
	}

	e.logMsg("科目余额表", "INFO", "已拉取 100 条")
	e.logMsg("科目余额表", "WARN", "接近表单预算")

	mu.Lock()
	defer mu.Unlock()
	want := []string{
		"run-1|科目余额表|INFO|已拉取 100 条",
		"run-1|科目余额表|WARN|接近表单预算",
	}
	if len(got) != len(want) {
		t.Fatalf("回调收到 %d 条，期望 %d 条：%v", len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("回调第 %d 条 = %q，期望 %q", i, got[i], want[i])
		}
	}
}

// 未注册回调时只告警一次，不再每行刷 Skipping
// （原因：调度轮历史上每轮 60+ 行 [LOG-MSG] Skipping 噪声，降噪为每个断线 episode 一次）。
func TestLogMsgWithoutCallbackWarnsOnce(t *testing.T) {
	var buf bytes.Buffer
	oldOut := log.Writer()
	log.SetOutput(&buf)
	t.Cleanup(func() { log.SetOutput(oldOut) })

	e := &SyncEngine{}
	for i := 0; i < 5; i++ {
		e.logMsg("表单A", "INFO", "进度")
	}
	if n := strings.Count(buf.String(), "[LOG-MSG]"); n != 1 {
		t.Fatalf("cb 为 nil 时告警行数 = %d，期望 1：%s", n, buf.String())
	}
	out := buf.String()
	if !strings.Contains(out, "cb nil=true") || !strings.Contains(out, "表单A") {
		t.Fatalf("告警内容缺少关键诊断字段：%s", out)
	}

	// 注册回调后恢复投递，且告警位重置（原因：断线 episode 边界由 SetLogCallback 定义）
	delivered := false
	e.SetLogCallback(func(string, string, string, string) { delivered = true }, "run-2")
	e.logMsg("表单A", "INFO", "进度")
	if !delivered {
		t.Fatal("注册回调后 logMsg 未投递")
	}

	// 再次断开（注册 nil 回调）应允许再告警一次，且仍只一次
	e.SetLogCallback(nil, "run-2")
	e.logMsg("表单A", "INFO", "断线1")
	e.logMsg("表单A", "INFO", "断线2")
	if n := strings.Count(buf.String(), "[LOG-MSG]"); n != 2 {
		t.Fatalf("二次断线累计告警行数 = %d，期望 2：%s", n, buf.String())
	}
}

// cb 已注册但 runID 为空时也走同一条一次性告警路径
// （原因：覆盖原 rid-empty 分支的降噪行为）。
func TestLogMsgEmptyRunIDWarnsOnce(t *testing.T) {
	var buf bytes.Buffer
	oldOut := log.Writer()
	log.SetOutput(&buf)
	t.Cleanup(func() { log.SetOutput(oldOut) })

	e := &SyncEngine{}
	called := false
	e.SetLogCallback(func(string, string, string, string) { called = true }, "")
	e.logMsg("表单B", "INFO", "进度1")
	e.logMsg("表单B", "INFO", "进度2")
	if called {
		t.Fatal("runID 为空时不应投递回调")
	}
	if n := strings.Count(buf.String(), "[LOG-MSG]"); n != 1 {
		t.Fatalf("runID 为空时告警行数 = %d，期望 1：%s", n, buf.String())
	}
	if !strings.Contains(buf.String(), "run id empty=true") {
		t.Fatalf("告警内容缺少 run id empty 诊断字段：%s", buf.String())
	}
}
