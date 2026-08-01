#!/bin/bash
# Start Go server for kingdee-sync
# Usage: deploy/scripts/start-server.sh [--port 8080]

PORT="${1:--port}"
if [ "$PORT" = "--port" ]; then
  PORT="${2:-8080}"
else
  PORT="${1:-8080}"
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUN_DIR="$PROJECT_ROOT/.run"
mkdir -p "$RUN_DIR"

# Kill any existing Go server instances (by port, more reliable)
echo "Stopping existing Go server instances..."
OLD_PID=$(ss -tlnp 2>/dev/null | grep ":$PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2)
if [ -n "$OLD_PID" ]; then
  kill -9 $OLD_PID 2>/dev/null || true
  sleep 2
fi
sleep 1

# Always rebuild to ensure latest code
cd "$PROJECT_ROOT/apps/server"
echo "Building Go server..."
go build -o "$RUN_DIR/server" ./cmd/server/ || exit 1

# Start server
echo "Starting Go server on port $PORT..."
cd "$PROJECT_ROOT"
SYNC_CONFIG_DIR="$PROJECT_ROOT/packages/sync-config" LISTEN_PORT=$PORT nohup "$RUN_DIR/server" > "$RUN_DIR/go-server.log" 2>&1 &
echo $! > "$RUN_DIR/go-server.pid"

sleep 3

# Check if started successfully
if kill -0 $(cat "$RUN_DIR/go-server.pid") 2>/dev/null; then
  echo "Go server started successfully (PID: $(cat "$RUN_DIR/go-server.pid"))"
  curl -s --max-time 3 http://127.0.0.1:$PORT/health
else
  echo "Failed to start Go server. Check $RUN_DIR/go-server.log"
  exit 1
fi
