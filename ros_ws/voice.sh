#!/bin/bash
# voice.sh — microphone front-end for the spoken-command demo.
#
# Run this ALONGSIDE ./bringup.sh (which already runs llm_node + control_node).
# It starts the wake-word listener and the speech-to-text service:
#
#   ww_node (wake word) --Trigger--> stt_node --command_text--> llm_node
#       --parsed_command--> control_node --> flight
#
# Needs a microphone plus PICOVOICE_ACCESS_KEY and GOOGLE_APPLICATION_CREDENTIALS
# in .env. List mic indices with:
#   python3 -c "import pvrecorder; print(pvrecorder.PvRecorder.get_available_devices())"

set -e

ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
  echo "🔑 Loading config from $ENV_FILE"
  set -a; . "$ENV_FILE"; set +a
fi

source install/setup.bash

echo "🎙️  Starting voice front-end (wake word + STT)..."
ros2 run voice_mod stt_node &
STT_PID=$!

cleanup() {
  echo "🛑 Stopping voice nodes..."
  kill "$STT_PID" 2>/dev/null || true
  wait "$STT_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

# Wake-word node in the foreground so Ctrl-C tears everything down
ros2 run voice_mod ww_node_service
