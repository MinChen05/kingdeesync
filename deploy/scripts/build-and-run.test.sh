#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_SCRIPT="$SCRIPT_DIR/build-and-run.sh"
TEST_ROOT="$(mktemp -d)"
MOCK_BIN="$TEST_ROOT/bin"
COMMAND_LOG="$TEST_ROOT/commands.log"
OUTPUT_LOG="$TEST_ROOT/output.log"

cleanup() {
  rm -rf "$TEST_ROOT"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/deploy/scripts" "$MOCK_BIN"
cp "$SOURCE_SCRIPT" "$TEST_ROOT/deploy/scripts/build-and-run.sh"
touch "$TEST_ROOT/config.local.ini"

cat >"$MOCK_BIN/podman" <<'MOCK'
#!/usr/bin/env bash
printf 'podman %s\n' "$*" >>"$MOCK_LOG"
if [[ "${MOCK_FAIL_BUILD:-}" == "web" && "$1" == "build" && "$*" == *"web.Dockerfile"* ]]; then
  exit 1
fi
exit 0
MOCK

cat >"$MOCK_BIN/curl" <<'MOCK'
#!/usr/bin/env bash
printf 'curl %s\n' "$*" >>"$MOCK_LOG"
exit 0
MOCK
chmod +x "$MOCK_BIN/podman" "$MOCK_BIN/curl"

run_script() {
  : >"$COMMAND_LOG"
  set +e
  MOCK_LOG="$COMMAND_LOG" MOCK_FAIL_BUILD="${1:-}" PATH="$MOCK_BIN:$PATH" \
    bash "$TEST_ROOT/deploy/scripts/build-and-run.sh" >"$OUTPUT_LOG" 2>&1
  SCRIPT_STATUS=$?
  set -e
}

fail() {
  printf 'not ok - %s\n' "$1" >&2
  printf '%s\n' '--- command log ---' >&2
  cat "$COMMAND_LOG" >&2
  printf '%s\n' '--- script output ---' >&2
  cat "$OUTPUT_LOG" >&2
  exit 1
}

run_script web
[[ "$SCRIPT_STATUS" -ne 0 ]] || fail '前端构建失败时脚本应返回非零状态'
grep -q '^podman build .*Dockerfile' "$COMMAND_LOG" || fail '未执行 API 镜像构建'
if grep -Eq '^podman (pod rm|pod create|run )' "$COMMAND_LOG"; then
  fail '构建失败后不应删除或重建现有 Pod'
fi
printf '%s\n' 'ok 1 - 前端构建失败不会中断运行中的服务'

run_script
[[ "$SCRIPT_STATUS" -eq 0 ]] || fail '构建成功时脚本应正常退出'
build_lines="$(grep -n '^podman build ' "$COMMAND_LOG" | cut -d: -f1)"
rm_line="$(grep -n '^podman pod rm ' "$COMMAND_LOG" | cut -d: -f1)"
[[ "$(printf '%s\n' "$build_lines" | wc -l)" -eq 2 ]] || fail '应同时构建前后端镜像'
[[ -n "$rm_line" ]] || fail '构建成功后未替换 Pod'
[[ "$(printf '%s\n' "$build_lines" | sort -n | tail -n 1)" -lt "$rm_line" ]] || fail '必须在两个镜像构建完成后才能删除 Pod'
printf '%s\n' 'ok 2 - 两个镜像构建完成后才替换 Pod'

curl_lines="$(grep '^curl ' "$COMMAND_LOG" || true)"
[[ "$(printf '%s\n' "$curl_lines" | wc -l)" -eq 2 ]] || fail '应执行两次健康检查'
if printf '%s\n' "$curl_lines" | grep -qv -- '--retry-connrefused'; then
  fail '健康检查必须启用连接拒绝重试'
fi
last_curl_line="$(grep -n '^curl ' "$COMMAND_LOG" | tail -n 1 | cut -d: -f1)"
latest_tag_lines="$(grep -n '^podman tag .*:latest' "$COMMAND_LOG" | cut -d: -f1)"
[[ "$(printf '%s\n' "$latest_tag_lines" | wc -l)" -eq 2 ]] || fail '健康检查后应更新前后端 latest 标签'
[[ "$(printf '%s\n' "$latest_tag_lines" | sort -n | head -n 1)" -gt "$last_curl_line" ]] || fail '健康检查通过后才能更新 latest 标签'
printf '%s\n' 'ok 3 - 健康检查等待端口就绪且通过后才更新 latest'

printf '%s\n' 'All deployment script tests passed.'
