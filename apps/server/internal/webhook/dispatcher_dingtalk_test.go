package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"testing"
)

func TestDingTalkNotifierSendAlert(t *testing.T) {
	var mu sync.Mutex
	var received string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		mu.Lock()
		received = string(body)
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	NewDingTalkNotifier(srv.URL, "").SendAlert("目标数据库不可用", "10.10.10.191:1433 无法连接")

	mu.Lock()
	defer mu.Unlock()
	if received == "" {
		t.Fatal("应收到一条钉钉消息")
	}
	var payload DingTalkPayload
	if err := json.Unmarshal([]byte(received), &payload); err != nil {
		t.Fatalf("payload 不是合法 JSON: %v", err)
	}
	if !strings.HasPrefix(payload.Text.Content, "【金蝶同步告警】目标数据库不可用") {
		t.Fatalf("消息缺少统一告警前缀，实际: %s", payload.Text.Content)
	}
	if !strings.Contains(payload.Text.Content, "10.10.10.191:1433") {
		t.Fatalf("消息正文缺少目标地址，实际: %s", payload.Text.Content)
	}
}

func TestDingTalkNotifierSendAlertEmptyURLNoop(t *testing.T) {
	// 未配置 webhook URL 时必须静默跳过而不是报错或 panic
	NewDingTalkNotifier("", "").SendAlert("目标数据库不可用", "内容")
}

// 验证加签配置下 URL 携带合法的 timestamp 与 sign（服务端用同一密钥重算比对）。
func TestDingTalkNotifierSignedURL(t *testing.T) {
	const secret = "SECtestsecretkey"
	var mu sync.Mutex
	var query string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		query = r.URL.RawQuery
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	webhookURL := srv.URL + "?access_token=test-token"
	NewDingTalkNotifier(webhookURL, secret).SendAlert("测试标题", "测试内容")

	mu.Lock()
	defer mu.Unlock()
	if query == "" {
		t.Fatal("应收到一条带查询参数的请求")
	}
	params, err := url.ParseQuery(query)
	if err != nil {
		t.Fatalf("查询参数解析失败: %v", err)
	}
	if params.Get("access_token") != "test-token" {
		t.Fatalf("原有 access_token 参数丢失: %s", query)
	}
	timestamp := params.Get("timestamp")
	if timestamp == "" {
		t.Fatal("缺少 timestamp 参数")
	}
	if _, err := strconv.ParseInt(timestamp, 10, 64); err != nil {
		t.Fatalf("timestamp 非毫秒时间戳: %s", timestamp)
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(timestamp + "\n" + secret))
	wantSign := base64.StdEncoding.EncodeToString(mac.Sum(nil))
	if got := params.Get("sign"); got != wantSign {
		t.Fatalf("sign 不匹配：期望 %q，实际 %q", wantSign, got)
	}
}

// 未配置密钥时 URL 不应被追加 timestamp/sign（兼容仅关键词/IP 白名单方式的机器人）。
func TestDingTalkNotifierNoSecretNoSignParams(t *testing.T) {
	var mu sync.Mutex
	var rawQuery string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		rawQuery = r.URL.RawQuery
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	NewDingTalkNotifier(srv.URL+"?access_token=t", "").SendAlert("标题", "内容")

	mu.Lock()
	defer mu.Unlock()
	if strings.Contains(rawQuery, "sign=") || strings.Contains(rawQuery, "timestamp=") {
		t.Fatalf("未配置密钥却追加了签名参数: %s", rawQuery)
	}
}
