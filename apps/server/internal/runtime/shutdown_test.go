package runtime

import (
	"context"
	"os"
	"sync"
	"syscall"
	"testing"
	"time"
)

type fakeScheduler struct {
	mu     sync.Mutex
	paused bool
}

func (s *fakeScheduler) Pause() {
	s.mu.Lock()
	s.paused = true
	s.mu.Unlock()
}

type fakeEngine struct {
	mu             sync.Mutex
	active         bool
	rejected       bool
	gracefulCalled bool
	writeStarted   chan struct{}
	releaseWrite   chan struct{}
	cancelObserved chan struct{}
}

func (e *fakeEngine) RejectNewRuns() {
	e.mu.Lock()
	e.rejected = true
	e.mu.Unlock()
}

func (e *fakeEngine) GracefulStop(ctx context.Context) error {
	e.mu.Lock()
	e.gracefulCalled = true
	active := e.active
	e.mu.Unlock()
	if !active {
		return nil
	}
	close(e.writeStarted)
	select {
	case <-e.releaseWrite:
		return nil
	case <-ctx.Done():
		close(e.cancelObserved)
		return ctx.Err()
	}
}

func TestSIGTERMPausesRejectsAndDrainsActiveWrite(t *testing.T) {
	scheduler := &fakeScheduler{}
	engine := &fakeEngine{
		active:         true,
		writeStarted:   make(chan struct{}),
		releaseWrite:   make(chan struct{}),
		cancelObserved: make(chan struct{}),
	}
	coordinator := NewShutdownCoordinatorWithTimeout(scheduler, engine, time.Second)
	signals := make(chan os.Signal, 1)
	signals <- syscall.SIGTERM
	shutdownDone := make(chan error, 1)
	go func() { shutdownDone <- coordinator.WaitForSignal(context.Background(), signals) }()

	<-engine.writeStarted
	scheduler.mu.Lock()
	paused := scheduler.paused
	scheduler.mu.Unlock()
	engine.mu.Lock()
	rejected, gracefulCalled := engine.rejected, engine.gracefulCalled
	engine.mu.Unlock()
	if !paused || !rejected || !gracefulCalled {
		t.Fatalf("shutdown state paused=%v rejected=%v graceful=%v", paused, rejected, gracefulCalled)
	}
	select {
	case err := <-shutdownDone:
		t.Fatalf("shutdown returned before active write drained: %v", err)
	case <-time.After(20 * time.Millisecond):
	}
	select {
	case <-engine.cancelObserved:
		t.Fatal("active write was canceled before shutdown deadline")
	default:
	}
	close(engine.releaseWrite)
	if err := <-shutdownDone; err != nil {
		t.Fatal(err)
	}
}

func TestShutdownTimeoutCancelsActiveRunContext(t *testing.T) {
	scheduler := &fakeScheduler{}
	engine := &fakeEngine{
		active:         true,
		writeStarted:   make(chan struct{}),
		releaseWrite:   make(chan struct{}),
		cancelObserved: make(chan struct{}),
	}
	coordinator := NewShutdownCoordinatorWithTimeout(scheduler, engine, 10*time.Millisecond)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	if err := coordinator.Shutdown(ctx); err != context.DeadlineExceeded {
		t.Fatalf("shutdown error = %v, want deadline exceeded", err)
	}
	select {
	case <-engine.cancelObserved:
	case <-time.After(time.Second):
		t.Fatal("active run did not observe shutdown cancellation")
	}
}

func TestDefaultShutdownTimeoutIsSixtySeconds(t *testing.T) {
	if DefaultShutdownTimeout != 60*time.Second {
		t.Fatalf("default shutdown timeout = %v", DefaultShutdownTimeout)
	}
}
