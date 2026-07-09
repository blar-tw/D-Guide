#!/bin/bash
# bringup.sh — build and launch the D-Guide mission (flight + brain).
#
# Starts: path planner + flight executor + LLM command bridge, then the
# control node in the foreground. Add the microphone front-end separately
# with ./voice.sh for the full spoken-command demo.
#
# Flight executor (env FLIGHT_EXECUTOR):
#   dwa (default) -> obstacle_avoidance/dwa_navigator: waypoint following with
#                    live LiDAR obstacle avoidance (the demo).
#   simple        -> mission_manager/followpp_server: plain simple_goto, no
#                    avoidance (bring-up / no-LiDAR testing fallback).

set -e

# Load config + secrets from repo-root .env (gitignored)
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
  echo "🔑 Loading config from $ENV_FILE"
  set -a; . "$ENV_FILE"; set +a
else
  echo "⚠️  No .env found at $ENV_FILE (copy .env.example to .env and fill it in)"
fi

echo "🔧 Building workspace..."
colcon build
source install/setup.bash

FLIGHT_EXECUTOR="${FLIGHT_EXECUTOR:-dwa}"
if [ "$FLIGHT_EXECUTOR" = "simple" ]; then
  FLIGHT_CMD="ros2 run mission_manager followpp_server"
  echo "🛩️  Flight executor: simple_goto (no avoidance)"
else
  FLIGHT_CMD="ros2 run obstacle_avoidance dwa_navigator"
  echo "🛩️  Flight executor: DWA obstacle avoidance"
fi

echo "🚀 Starting nodes..."
ros2 run path_planning pp_node &
PP_PID=$!

$FLIGHT_CMD &
FLIGHT_PID=$!

ros2 run voice_mod llm_node &
LLM_PID=$!

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
  echo "🛑 Stopping background nodes..."
  force_kill_pid "$PP_PID"
  force_kill_pid "$FLIGHT_PID"
  force_kill_pid "$LLM_PID"
  wait $PP_PID $FLIGHT_PID $LLM_PID 2>/dev/null || true
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

echo "✅ Nodes up. Control node in foreground (type a destination, or speak via ./voice.sh)."
ros2 run mission_manager control_node
EXIT_CODE=$?

cleanup
exit $EXIT_CODE
