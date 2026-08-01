#!/bin/bash
# Stop Go server for kingdee-sync

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_DIR="$PROJECT_ROOT/.run"

if [ -f "$RUN_DIR/go-server.pid" ]; then
  PID=$(cat "$RUN_DIR/go-server.pid")
  if kill -0 $PID 2>/dev/null; then
    echo "Stopping Go server (PID: $PID)..."
    kill $PID
    sleep 2
    kill -9 $PID 2>/dev/null || true
    echo "Go server stopped."
  else
    echo "Go server not running (stale PID file)."
  fi
  rm -f "$RUN_DIR/go-server.pid"
else
  echo "No managed Go server PID file found."
fi
