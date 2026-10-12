package gormdb

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/require"
)

// TestSaveCursorCheckpointRoundTrip 验证游标断点持久化的读写往返：
// 保存后可通过 GetCheckpoint 完整取回游标 JSON、行数与 run 归属。
func TestSaveCursorCheckpointRoundTrip(t *testing.T) {
	setupStateTestDB(t)

	previous := []interface{}{float64(10086), "ENTRY-42"}
	cpJSON, err := json.Marshal(previous)
	require.NoError(t, err)

	require.NoError(t, SaveCursorCheckpoint("采购订单", "run-1", 50000, string(cpJSON)))

	cp, err := GetCheckpoint("采购订单")
	require.NoError(t, err)
	require.NotNil(t, cp)
	require.Equal(t, "run-1", cp.RunID)
	require.EqualValues(t, 50000, cp.LastPosition)

	var restored []interface{}
	require.NoError(t, json.Unmarshal([]byte(cp.CursorValue), &restored))
	// JSON 往返后数值仍为 float64、字符串保持字符串，与 compareCursorValues 的运行时类型一致
	require.Equal(t, previous, restored)
}

// TestSaveCursorCheckpointPreservesLastSyncTime 验证游标写入不会清空增量水位
// （原因：SaveCursorCheckpoint 与 StartRow 路径共用一行记录）。
func TestSaveCursorCheckpointPreservesLastSyncTime(t *testing.T) {
	setupStateTestDB(t)

	require.NoError(t, SaveCheckpointForRun("销售出库单", "run-a", 123, "2026-10-12 10:00:00"))
	require.NoError(t, SaveCursorCheckpoint("销售出库单", "run-b", 456, `[{"x":1}]`))

	cp, err := GetCheckpoint("销售出库单")
	require.NoError(t, err)
	require.Equal(t, "2026-10-12 10:00:00", cp.LastSyncTime)
	require.Equal(t, "run-b", cp.RunID)
	require.Equal(t, `[{"x":1}]`, cp.CursorValue)
}

// TestSaveCheckpointForRunClearsCursor 验证 StartRow 路径写入时清除残留游标，
// 防止表单切换分页方式后被旧游标误导恢复。
func TestSaveCheckpointForRunClearsCursor(t *testing.T) {
	setupStateTestDB(t)

	require.NoError(t, SaveCursorCheckpoint("物料", "run-a", 100, `["M"]`))
	require.NoError(t, SaveCheckpointForRun("物料", "run-b", 200, "2026-10-12 11:00:00"))

	cp, err := GetCheckpoint("物料")
	require.NoError(t, err)
	require.Empty(t, cp.CursorValue)
	require.EqualValues(t, 200, cp.LastPosition)
}
