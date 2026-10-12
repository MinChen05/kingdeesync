package webhook

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Payload is the JSON body sent to webhook endpoints.
type Payload struct {
	Event    string `json:"event"`    // "sync.completed" or "sync.failed"
	RunID    string `json:"run_id"`
	Status   string `json:"status"`
	Duration float64 `json:"duration_seconds"`
	Message  string `json:"message,omitempty"`
	Timestamp string `json:"timestamp"`
}

// Dispatcher sends webhook HTTP POST requests.
type Dispatcher struct {
	client *http.Client
}

// New creates a Dispatcher with a 10-second timeout.
func New() *Dispatcher {
	return &Dispatcher{
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// Send fires a POST to the given URL with exponential backoff (3 retries).
// （原因：webhook 接收端可能短暂不可用，重试避免单次网络抖动丢失通知）
func (d *Dispatcher) Send(url string, payload Payload) {
	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("[WEBHOOK] marshal error: %v", err)
		return
	}

	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(attempt) * 500 * time.Millisecond
			time.Sleep(backoff)
		}
		req, err := http.NewRequest("POST", url, bytes.NewReader(body))
		if err != nil {
			lastErr = err
			continue
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("User-Agent", "kingdee-sync/1.0")

		resp, err := d.client.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		resp.Body.Close()

		if resp.StatusCode < 500 {
			log.Printf("[WEBHOOK] %s -> %d (%s)", url, resp.StatusCode, payload.Event)
			lastErr = nil
			break
		}
		lastErr = fmt.Errorf("HTTP %d from %s", resp.StatusCode, url)
	}
	if lastErr != nil {
		log.Printf("[WEBHOOK] failed after 3 attempts: %v", lastErr)
	}
}

// FireCompleted sends a "sync.completed" webhook.
func (d *Dispatcher) FireCompleted(url, runID string, duration float64) {
	d.Send(url, Payload{
		Event:     "sync.completed",
		RunID:     runID,
		Status:    "success",
		Duration:  duration,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// FireFailed sends a "sync.failed" webhook.
func (d *Dispatcher) FireFailed(url, runID, message string, duration float64) {
	d.Send(url, Payload{
		Event:     "sync.failed",
		RunID:     runID,
		Status:    "failed",
		Duration:  duration,
		Message:   message,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	})
}

// ─── DingTalk Webhook ───

// DingTalkPayload is the markdown message format for DingTalk robot webhook.
type DingTalkPayload struct {
	MsgType string `json:"msgtype"`
	Text    struct {
		Content string `json:"content"`
	} `json:"text"`
}

// SendDingTalk sends a DingTalk notification via the generic Send method.
func (d *Dispatcher) SendDingTalk(url, title, content string) {
	payload := DingTalkPayload{
		MsgType: "text",
	}
	payload.Text.Content = fmt.Sprintf("【金蝶同步告警】%s\n%s", title, content)

	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("[DINGTALK] marshal error: %v", err)
		return
	}

	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			time.Sleep(time.Duration(attempt) * 500 * time.Millisecond)
		}
		req, err := http.NewRequest("POST", url, bytes.NewReader(body))
		if err != nil {
			lastErr = err
			continue
		}
		req.Header.Set("Content-Type", "application/json")
		resp, err := d.client.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		resp.Body.Close()
		if resp.StatusCode < 500 {
			log.Printf("[DINGTALK] %s -> %d", url, resp.StatusCode)
			lastErr = nil
			break
		}
		lastErr = fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	if lastErr != nil {
		log.Printf("[DINGTALK] failed after 3 attempts: %v", lastErr)
	}
}

// DingTalkNotifier wraps SendDingTalk for use as a completion hook.
type DingTalkNotifier struct {
	url    string
	secret string
}

// NewDingTalkNotifier creates a notifier for DingTalk alerts.
// secret 为机器人"加签"安全设置的密钥（SEC 开头）；为空表示机器人未启用加签。
func NewDingTalkNotifier(webhookURL, secret string) *DingTalkNotifier {
	return &DingTalkNotifier{url: webhookURL, secret: secret}
}

// sendURL 按钉钉加签规范（sign = urlEncode(base64(HMAC-SHA256(secret, timestamp+"\n"+secret))))
// 为 webhook URL 追加 timestamp 与 sign 参数；未配置密钥时原样返回。
// （原因：机器人开启"加签"安全设置时，仅带 access_token 的请求会被拒绝 errcode 310000）
func (n *DingTalkNotifier) sendURL() (string, error) {
	if n.secret == "" {
		return n.url, nil
	}
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)
	mac := hmac.New(sha256.New, []byte(n.secret))
	if _, err := mac.Write([]byte(timestamp + "\n" + n.secret)); err != nil {
		return "", fmt.Errorf("dingtalk sign hmac: %w", err)
	}
	sign := url.QueryEscape(base64.StdEncoding.EncodeToString(mac.Sum(nil)))
	sep := "?"
	if strings.Contains(n.url, "?") {
		sep = "&"
	}
	return fmt.Sprintf("%s%stimestamp=%s&sign=%s", n.url, sep, timestamp, sign), nil
}

// send 解析加签 URL 并发送。
func (n *DingTalkNotifier) send(title, content string) {
	if n.url == "" {
		return
	}
	signed, err := n.sendURL()
	if err != nil {
		log.Printf("[DINGTALK] sign error: %v", err)
		return
	}
	New().SendDingTalk(signed, title, content)
}

// OnFailed 发送异常完成通知（failed/partial/stopped/failed_abnormal_exit）。
// 成功完成不再推送（原因：用户要求仅异常打扰，正常运行静默）。
func (n *DingTalkNotifier) OnFailed(runID, status, message string, duration float64) {
	title := "同步失败"
	if status == "partial" {
		title = "同步部分失败"
	}
	content := fmt.Sprintf("运行 %s %s\n耗时: %.1f 秒\n详情: %s", runID[:8], status, duration, message)
	n.send(title, content)
}

// SendAlert 发送系统级告警（如目标数据库断连/恢复），不依赖具体同步 run。
// （原因：探活告警发生在两次同步任务之间，无法复用面向 run 生命周期的 OnFailed）
func (n *DingTalkNotifier) SendAlert(title, content string) {
	n.send(title, content)
}
