package db

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/kingdee-sync/go/internal/config"
)

// MaxGrantWait 返回目标库当前最长的内存授予排队时长（wait_type = RESOURCE_SEMAPHORE）。
// 非 SQL Server 目标返回 0 且不带错误，由调用方按"无需守卫"处理。
// （原因：SQL Server 的授予队列按 FIFO 放行，一个拿不到内存的大请求会拖住其后所有
// 需要授予的查询，无论多小。2026-11-02 事故中外部报表作业排队 9.7 小时，
// 令同步每轮 1800 秒 0 行写入，见 docs/superpowers/reports/ 同名说明）
func MaxGrantWait(ctx context.Context) (time.Duration, error) {
	if DB == nil {
		return 0, fmt.Errorf("database not initialized")
	}
	if cfg := config.Get(); cfg != nil {
		if eff := cfg.GetEffectiveDatabase(); eff.Type != "" && !strings.EqualFold(eff.Type, "sqlserver") {
			return 0, nil
		}
	}

	var ms int64
	err := DB.QueryRowContext(ctx,
		"SELECT ISNULL(MAX(wait_duration_ms), 0) FROM sys.dm_os_waiting_tasks WHERE wait_type = 'RESOURCE_SEMAPHORE'").Scan(&ms)
	if err != nil {
		return 0, fmt.Errorf("query memory grant queue: %w", err)
	}
	if ms < 0 {
		ms = 0
	}
	return time.Duration(ms) * time.Millisecond, nil
}
