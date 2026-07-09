#!/bin/bash
# bringup.sh

set -e  # 有錯就停止執行，避免錯誤持續下去

# Load secrets from repo-root .env (gitignored) so nodes can read API keys
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
  echo "🔑 Loading secrets from $ENV_FILE"
  set -a; . "$ENV_FILE"; set +a
else
  echo "⚠️  No .env found at $ENV_FILE (copy .env.example to .env and fill in your keys)"
fi

echo "🔧 設定 ROS2 環境..."
colcon build
source install/setup.bash
echo "🚀 啟動各節點中..."
ros2 run path_planning pp_node &
PP_PID=$!

ros2 run mission_manager followpp_server &
FOLLOW_PID=$!

CLEANED_UP=0
force_kill_pid() {
  local PID="$1"
  if [ -z "$PID" ]; then
    return
  fi
  if kill -0 "$PID" 2>/dev/null; then
    pkill -TERM -P "$PID" 2>/dev/null || true
    kill "$PID" 2>/dev/null || true
    sleep 1
  fi
  if kill -0 "$PID" 2>/dev/null; then
    echo "⚠️  Process $PID still running, sending SIGKILL..."
    pkill -KILL -P "$PID" 2>/dev/null || true
    kill -9 "$PID" 2>/dev/null || true
  fi
}

cleanup() {
  if [ "$CLEANED_UP" -eq 1 ]; then
    return
  fi
  CLEANED_UP=1
  echo "🛑 停止背景節點..."
  force_kill_pid "$PP_PID"
  force_kill_pid "$FOLLOW_PID"
  wait $PP_PID $FOLLOW_PID 2>/dev/null || true
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

echo "✅ 所有節點已啟動，Control Node 在前景執行。"
ros2 run mission_manager control_node_v3
EXIT_CODE=$?

cleanup
exit $EXIT_CODE
