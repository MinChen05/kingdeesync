package kind

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// flakyBodyServer 构造一个前 badReads 次“响应头已返回、响应体截断断流”的
// 金蝶报表替身：hijack 后声明远超实际写入量的 Content-Length 再关闭连接，
// 使客户端 io.ReadAll 失败（原因：复现 issue #9 生产故障面——大响应在
// 读体阶段于 client 120s 超时边界截断，请求阶段本身是成功的）。
func flakyBodyServer(t *testing.T, badReads int32, goodBody []byte) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	var hits atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if hits.Add(1) <= badReads {
			hj, ok := w.(http.Hijacker)
			if !ok {
				t.Error("httptest server 不支持 Hijacker，无法模拟读体截断")
				return
			}
			conn, bw, err := hj.Hijack()
			if err != nil {
				t.Errorf("hijack 失败: %v", err)
				return
			}
			_, _ = bw.WriteString("HTTP/1.1 200 OK\r\nContent-Length: 4096\r\n\r\n{\"partial\":")
			_ = bw.Flush()
			_ = conn.Close()
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(goodBody)
	}))
	t.Cleanup(srv.Close)
	return srv, &hits
}

func TestDoReportWithBodyReadFirstSuccess(t *testing.T) {
	good := []byte(`[["1001","库存现金"]]`)
	srv, hits := flakyBodyServer(t, 0, good)
	c := NewKingdeeClient()

	got, err := c.doReportWithBodyRead(context.Background(), srv.URL, map[string]any{}, 3, time.Millisecond)
	if err != nil {
		t.Fatalf("预期成功，实得错误: %v", err)
	}
	if string(got) != string(good) {
		t.Fatalf("响应体不匹配: got %q, want %q", got, good)
	}
	if hits.Load() != 1 {
		t.Fatalf("首次成功不应重试，请求数 = %d, want 1", hits.Load())
	}
}

func TestDoReportWithBodyReadRetriesTruncatedRead(t *testing.T) {
	good := []byte(`[["1001","库存现金"]]`)
	srv, hits := flakyBodyServer(t, 1, good)
	c := NewKingdeeClient()

	got, err := c.doReportWithBodyRead(context.Background(), srv.URL, map[string]any{}, 3, time.Millisecond)
	if err != nil {
		t.Fatalf("读体截断应重试后成功，实得错误: %v", err)
	}
	if string(got) != string(good) {
		t.Fatalf("重试后响应体不匹配: got %q, want %q", got, good)
	}
	if hits.Load() != 2 {
		t.Fatalf("应恰好重试一次，请求数 = %d, want 2", hits.Load())
	}
}

func TestDoReportWithBodyReadExhaustedReturnsBodyReadError(t *testing.T) {
	srv, hits := flakyBodyServer(t, 10, []byte(`[]`))
	c := NewKingdeeClient()

	_, err := c.doReportWithBodyRead(context.Background(), srv.URL, map[string]any{}, 2, time.Millisecond)
	if err == nil {
		t.Fatal("重试耗尽应返回错误")
	}
	var bre *bodyReadError
	if !errors.As(err, &bre) {
		t.Fatalf("错误应可识别为 *bodyReadError 供调用方区分包装文案，实得: %T %v", err, err)
	}
	if !strings.Contains(err.Error(), "read response body") {
		t.Fatalf("错误信息应包含读体阶段标识，实得: %v", err)
	}
	if hits.Load() != 2 {
		t.Fatalf("请求数应等于尝试次数，= %d, want 2", hits.Load())
	}
}

func TestDoReportWithBodyReadCanceledContextSendsNothing(t *testing.T) {
	srv, hits := flakyBodyServer(t, 0, []byte(`[]`))
	c := NewKingdeeClient()

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	_, err := c.doReportWithBodyRead(ctx, srv.URL, map[string]any{}, 3, time.Millisecond)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("已取消上下文应返回 context.Canceled，实得: %v", err)
	}
	if hits.Load() != 0 {
		t.Fatalf("已取消上下文不应发出请求，请求数 = %d", hits.Load())
	}
}

func TestDoReportWithBodyReadCancelDuringBackoff(t *testing.T) {
	srv, hits := flakyBodyServer(t, 10, []byte(`[]`))
	c := NewKingdeeClient()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	// 首次读体截断后进入退避（100ms），50ms 时取消：应中止等待并返回取消错误
	go func() {
		time.Sleep(50 * time.Millisecond)
		cancel()
	}()

	_, err := c.doReportWithBodyRead(ctx, srv.URL, map[string]any{}, 3, 100*time.Millisecond)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("退避期间取消应返回 context.Canceled，实得: %v", err)
	}
	if hits.Load() != 1 {
		t.Fatalf("取消后不应再发第二次请求，请求数 = %d, want 1", hits.Load())
	}
}
