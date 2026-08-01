#!/bin/bash
# Quick API format validation for Go backend
BASE="http://127.0.0.1:8080/api"
PASS=0
FAIL=0

check() {
  local name="$1"
  local url="$2"
  local method="${3:-GET}"
  local expected="$4"  # field that should exist in response.data

  echo -n "Testing $name ... "
  local resp
  if [ "$method" = "GET" ]; then
    resp=$(curl -s --max-time 5 "$url")
  else
    resp=$(curl -s --max-time 5 -X "$method" -H "Content-Type: application/json" "$url" -d '{"test":true}')
  fi

  if echo "$resp" | grep -q '"ok":true'; then
    if [ -n "$expected" ]; then
      if echo "$resp" | grep -q "\"$expected\""; then
        echo "✅ PASS"
        ((PASS++))
      else
        echo "❌ FAIL (missing field: $expected)"
        echo "   Response: $resp" | head -c 200
        echo
        ((FAIL++))
      fi
    else
      echo "✅ PASS"
      ((PASS++))
    fi
  else
    echo "❌ FAIL"
    echo "   Response: $resp" | head -c 200
    echo
    ((FAIL++))
  fi
}

echo "=== Go Backend API Format Validation ==="
echo

# Config
check "GET /config" "$BASE/config" GET "sync"
check "PUT /config" "$BASE/config" PUT "message"

# Forms
check "GET /forms" "$BASE/forms" GET "form_name"
check "GET /forms/mappings" "$BASE/forms/mappings" GET "field_count"

# Dashboard
check "GET /dashboard/today" "$BASE/dashboard/today" GET "sync_count"
check "GET /dashboard/trend/7d" "$BASE/dashboard/trend/7d" GET "date"
check "GET /dashboard/top-forms/7d" "$BASE/dashboard/top-forms/7d" GET "data"
check "GET /dashboard/health" "$BASE/dashboard/health" GET "kingdee_api"
check "GET /dashboard/recent" "$BASE/dashboard/recent" GET "data"
check "GET /dashboard/risks" "$BASE/dashboard/risks" GET "data"

# History
check "GET /history" "$BASE/history" GET "total"
check "GET /history?status=success" "$BASE/history?status=success" GET "runs"

# Stats
check "GET /stats/summary" "$BASE/stats/summary" GET "total_runs"
check "GET /stats/forms" "$BASE/stats/forms" GET "data"

# Schedule
check "GET /schedule/status" "$BASE/schedule/status" GET "enabled"
check "POST /schedule/start" "$BASE/schedule/start" POST "message"
check "POST /schedule/pause" "$BASE/schedule/pause" POST "message"
check "POST /schedule/update-interval" "$BASE/schedule/update-interval" POST "interval_minutes"

# Logs
check "GET /logs/recent" "$BASE/logs/recent" GET "total"
check "GET /logs/stats" "$BASE/logs/stats" GET "total"
check "GET /logs/scheduler" "$BASE/logs/scheduler" GET "total"

# Diagnostics
check "GET /diagnostics" "$BASE/diagnostics" GET "kingdee_api"
check "POST /diagnostics/test-connections" "$BASE/diagnostics/test-connections" POST "kingdee_api"

# Sync
check "GET /sync/status" "$BASE/sync/status" GET "status"
check "POST /sync/start" "$BASE/sync/start" POST "run_id"

# Tasks
check "GET /tasks" "$BASE/tasks" GET "task_name"
check "GET /tasks/stats" "$BASE/tasks/stats" GET "enabled_count"

# Datasources
check "GET /datasources" "$BASE/datasources" GET "name"

# Maintenance
check "POST /maintenance/archive" "$BASE/maintenance/archive" POST "message"

echo
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $((PASS + FAIL))"

if [ $FAIL -gt 0 ]; then
  exit 1
fi
