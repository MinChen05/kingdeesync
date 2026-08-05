package webhook

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
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
	url string
}

// NewDingTalkNotifier creates a notifier for DingTalk alerts.
func NewDingTalkNotifier(webhookURL string) *DingTalkNotifier {
	return &DingTalkNotifier{url: webhookURL}
}

// OnCompleted sends a success notification.
func (n *DingTalkNotifier) OnCompleted(runID string, duration float64, formCount int) {
	if n.url == "" {
		return
	}
	content := fmt.Sprintf("运行 %s 成功完成\n耗时: %.1f 秒\n同步表单: %d 个", runID[:8], duration, formCount)
	New().SendDingTalk(n.url, "同步成功", content)
}

// OnFailed sends a failure notification.
func (n *DingTalkNotifier) OnFailed(runID, message string, duration float64) {
	if n.url == "" {
		return
	}
	content := fmt.Sprintf("运行 %s 失败\n耗时: %.1f 秒\n错误: %s", runID[:8], duration, message)
	New().SendDingTalk(n.url, "同步失败", content)
}