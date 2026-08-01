package kind

import (
	"context"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/kingdee-sync/go/internal/config"
)

type cancelAfterResponseTransport struct {
	base        http.RoundTripper
	requestSent chan struct{}
	once        sync.Once
	calls       atomic.Int32
}

func (t *cancelAfterResponseTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	t.calls.Add(1)
	resp, err := t.base.RoundTrip(req)
	if err != nil {
		return nil, err
	}
	t.once.Do(func() { close(t.requestSent) })
	<-req.Context().Done()
	resp.Body.Close()
	return nil, req.Context().Err()
}

func TestRealKingdeeQueryCancellation(t *testing.T) {
	if os.Getenv("KIND_REAL_CANCELLATION_TEST") != "1" {
		t.Skip("requires explicit real-connection authorization")
	}
	if _, err := config.Load(filepath.Join("..", "..", "..", "config.local.ini")); err != nil {
		t.Fatalf("load configured Kingdee connection: %v", err)
	}
	cfg := config.Get()
	if cfg == nil || cfg.Kingdee.LoginURL == "" || cfg.Kingdee.QueryURL == "" {
		t.Fatal("Kingdee endpoints are not configured")
	}
	cfg.Kingdee.PageSize = 1
	cfg.Kingdee.MaxPages = 2

	client := NewKingdeeClient()
	loginCtx, loginCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer loginCancel()
	if err := client.LoginContext(loginCtx); err != nil {
		t.Fatalf("configured Kingdee login failed: %v", err)
	}

	transport := &cancelAfterResponseTransport{
		base:        client.httpClient.Transport,
		requestSent: make(chan struct{}),
	}
	client.httpClient.Transport = transport
	queryCtx, cancel := context.WithCancel(context.Background())
	errCh := make(chan error, 1)
	go func() {
		_, err := client.QueryDataContext(queryCtx, QueryParams{
			FormID:       "BD_MATERIAL",
			FieldKeys:    "FMATERIALID",
			Filter:       "FNUMBER = '100101010001'",
			Limit:        1,
			StartRow:     0,
			FieldKeyList: []string{"FMATERIALID"},
		})
		errCh <- err
	}()

	select {
	case <-transport.requestSent:
		cancel()
	case <-time.After(15 * time.Second):
		cancel()
		t.Fatal("configured Kingdee query did not reach the transport")
	}
	if err := <-errCh; !errors.Is(err, context.Canceled) {
		t.Fatalf("query cancellation error = %v, want context canceled", err)
	}
	if calls := transport.calls.Load(); calls != 1 {
		t.Fatalf("query request attempts = %d, want 1 with no next page request", calls)
	}
}
