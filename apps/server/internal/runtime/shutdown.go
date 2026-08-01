package runtime

import (
	"context"
	"os"
	"sync"
	"time"
)

const DefaultShutdownTimeout = 60 * time.Second

type Scheduler interface {
	Pause()
}

type Engine interface {
	RejectNewRuns()
	GracefulStop(context.Context) error
}

// ShutdownCoordinator is the single process-level shutdown controller. It
// pauses dispatch and closes task admission before asking the engine to drain.
type ShutdownCoordinator struct {
	scheduler Scheduler
	engine    Engine
	timeout   time.Duration
	once      sync.Once
	err       error
}

func NewShutdownCoordinator(scheduler Scheduler, engine Engine) *ShutdownCoordinator {
	return NewShutdownCoordinatorWithTimeout(scheduler, engine, DefaultShutdownTimeout)
}

func NewShutdownCoordinatorWithTimeout(scheduler Scheduler, engine Engine, timeout time.Duration) *ShutdownCoordinator {
	if timeout <= 0 {
		timeout = DefaultShutdownTimeout
	}
	return &ShutdownCoordinator{scheduler: scheduler, engine: engine, timeout: timeout}
}

func (c *ShutdownCoordinator) Shutdown(ctx context.Context) error {
	c.once.Do(func() {
		if c.scheduler != nil {
			c.scheduler.Pause()
		}
		if c.engine != nil {
			c.engine.RejectNewRuns()
			c.err = c.engine.GracefulStop(ctx)
		}
	})
	return c.err
}

// WaitForSignal keeps signal delivery injectable so tests never need to send
// SIGTERM to their own process.
func (c *ShutdownCoordinator) WaitForSignal(ctx context.Context, signals <-chan os.Signal) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-signals:
		shutdownCtx, cancel := context.WithTimeout(context.Background(), c.timeout)
		defer cancel()
		return c.Shutdown(shutdownCtx)
	}
}
