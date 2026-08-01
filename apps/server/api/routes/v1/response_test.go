package v1

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestWriteProblemUsesHTTPStatusAndStableShape(t *testing.T) {
	recorder := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(recorder)
	WriteProblem(context, http.StatusConflict, Problem{
		Code:    "RUN_ALREADY_ACTIVE",
		Message: "同步任务正在运行",
	})
	require.Equal(t, http.StatusConflict, recorder.Code)
	require.JSONEq(t, `{"error":{"code":"RUN_ALREADY_ACTIVE","message":"同步任务正在运行"}}`, recorder.Body.String())
}

func TestWriteProblemWithDetails(t *testing.T) {
	recorder := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(recorder)
	WriteProblem(context, http.StatusBadRequest, Problem{
		Code:    "INVALID_REQUEST",
		Message: "缺少必填字段",
		Details: map[string]string{"field": "forms"},
	})
	require.Equal(t, http.StatusBadRequest, recorder.Code)
	require.JSONEq(t, `{"error":{"code":"INVALID_REQUEST","message":"缺少必填字段","details":{"field":"forms"}}}`, recorder.Body.String())
}

func TestWriteDataReturnsEnvelope(t *testing.T) {
	recorder := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(recorder)
	WriteData(context, http.StatusOK, Run{RunID: "run-001", Status: "running"})
	require.Equal(t, http.StatusOK, recorder.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(recorder.Body.Bytes(), &result))
	require.Contains(t, result, "data")
	data := result["data"].(map[string]any)
	require.Equal(t, "run-001", data["run_id"])
	require.Equal(t, "running", data["status"])
}

func TestWriteDataWithMetaReturnsEnvelopeAndPageMeta(t *testing.T) {
	recorder := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(recorder)
	WriteDataWithMeta(context, http.StatusOK, []Run{{RunID: "r1"}}, PageMeta{
		Page: 1, PageSize: 10, Total: 42,
	})
	require.Equal(t, http.StatusOK, recorder.Code)

	var result map[string]any
	require.NoError(t, json.Unmarshal(recorder.Body.Bytes(), &result))
	require.Contains(t, result, "meta")
	meta := result["meta"].(map[string]any)
	require.Equal(t, float64(1), meta["page"])
	require.Equal(t, float64(10), meta["page_size"])
	require.Equal(t, float64(42), meta["total"])
}

func TestEnvelopeWithoutMetaOmitsMeta(t *testing.T) {
	recorder := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(recorder)
	WriteData(context, http.StatusOK, "ok")
	require.Equal(t, http.StatusOK, recorder.Code)
	body := recorder.Body.String()
	require.NotContains(t, body, `"meta"`)
}
