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
printf 'podman %s [TMPDIR=%s]\n' "$*" "${TMPDIR:-}" >>"$MOCK_LOG"
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

# run_script <失败模式> [KEY=VAL ...]（额外变量透传给被测脚本）
run_script() {
  : >"$COMMAND_LOG"
  set +e
  MOCK_LOG="$COMMAND_LOG" MOCK_FAIL_BUILD="${1:-}" PATH="$MOCK_BIN:$PATH" \
    env "${@:2}" bash "$TEST_ROOT/deploy/scripts/build-and-run.sh" >"$OUTPUT_LOG" 2>&1
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

# 构建临时目录必须固定在磁盘上（原因：继承会话的 TMPDIR 可能是小 tmpfs，
# 2026-11-02 部署即在 web 镜像提交层时因 no space left on device 失败）
run_script
[[ "$SCRIPT_STATUS" -eq 0 ]] || fail '默认构建应成功'
[[ "$(head -n 1 "$COMMAND_LOG")" == *'[TMPDIR=/var/tmp]' ]] || fail '默认应使用磁盘上的 /var/tmp 作为构建临时目录'
grep -q '^构建临时目录: /var/tmp' "$OUTPUT_LOG" || fail '应打印实际生效的构建临时目录'
printf '%s\n' 'ok 4 - 构建使用磁盘 TMPDIR 并打印决策'

run_script "" "BUILD_TMPDIR=$TEST_ROOT/buildtmp"
[[ "$SCRIPT_STATUS" -eq 0 ]] || fail '指定 BUILD_TMPDIR 时构建应成功'
[[ "$(head -n 1 "$COMMAND_LOG")" == *"[TMPDIR=$TEST_ROOT/buildtmp]" ]] || fail 'BUILD_TMPDIR 应覆盖默认临时目录'
[[ -d "$TEST_ROOT/buildtmp" ]] || fail '构建临时目录不存在时应自动创建'
printf '%s\n' 'ok 5 - BUILD_TMPDIR 显式指定被采用并自动创建'

run_script "" "BUILD_TMPDIR_MIN_MB=999999999"
[[ "$SCRIPT_STATUS" -ne 0 ]] || fail '可用空间不足时脚本必须失败'
grep -q '低于所需' "$OUTPUT_LOG" || fail '应给出空间不足的可读原因'
[[ ! -s "$COMMAND_LOG" ]] || fail '空间不足时不得调用任何 podman/curl（线上服务必须不受影响）'
printf '%s\n' 'ok 6 - 空间不足在任何 podman 调用前失败'

printf '%s\n' 'All deployment script tests passed.'
