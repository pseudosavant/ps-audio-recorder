#!/bin/bash

set -euo pipefail

# Simple smoke test for ps-replaygain service.
# - Creates a tiny MP3 test file (prefers ffmpeg/sox+lame; otherwise expects a provided MP3 path)
# - Copies it into /srv/recordings
# - Tails journal logs and asserts the watcher reports "replaygain OK"

usage() {
  echo "Usage: $0 [existing.mp3]"
  echo "If no MP3 is provided, attempts to generate a 1s silent MP3 using ffmpeg or sox+lame."
}

WATCH_DIR=${WATCH_DIR:-/srv/recordings}
UNIT=${UNIT:-ps-replaygain}
TMP_DIR=$(mktemp -d)
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

echo "[info] Using watch dir: $WATCH_DIR"
if [[ ! -d "$WATCH_DIR" ]]; then
  echo "[error] Watch directory not found: $WATCH_DIR" >&2
  exit 1
fi

make_mp3() {
  local out="$1"
  if command -v ffmpeg >/dev/null 2>&1; then
    ffmpeg -hide_banner -loglevel error -f lavfi -i anullsrc=r=48000:cl=stereo -t 1 -c:a libmp3lame -q:a 2 "$out"
    return 0
  fi
  if command -v sox >/dev/null 2>&1 && command -v lame >/dev/null 2>&1; then
    sox -n -r 48000 -c 2 "$TMP_DIR/silence.wav" trim 0.0 1.0
    lame --silent "$TMP_DIR/silence.wav" "$out"
    return 0
  fi
  return 1
}

SRC_MP3=${1:-}
if [[ -n "$SRC_MP3" ]]; then
  if [[ ! -f "$SRC_MP3" ]]; then
    echo "[error] Provided MP3 not found: $SRC_MP3" >&2
    exit 1
  fi
  TEST_MP3="$SRC_MP3"
else
  TEST_MP3="$TMP_DIR/test.mp3"
  if ! make_mp3 "$TEST_MP3"; then
    echo "[error] Could not generate a test MP3. Please provide an existing .mp3 path." >&2
    usage
    exit 2
  fi
fi

BASENAME="smoke-$(date +%s).mp3"
DEST="$WATCH_DIR/$BASENAME"
echo "[info] Copying test MP3 to $DEST"
cp -f "$TEST_MP3" "$DEST"

echo "[info] Waiting for service logs from $UNIT (timeout 20s)"
START_TS=$(date +%s)
FOUND=0
while true; do
  # Fetch last 50 lines to avoid long tails
  LOGS=$(journalctl -u "$UNIT" -n 50 --no-pager 2>/dev/null || true)
  if echo "$LOGS" | grep -F "replaygain OK: $DEST" >/dev/null 2>&1; then
    FOUND=1
    break
  fi
  NOW=$(date +%s)
  if (( NOW - START_TS > 20 )); then
    break
  fi
  sleep 1
done

if (( FOUND == 1 )); then
  echo "[pass] ReplayGain processed: $DEST"
  exit 0
else
  echo "[fail] Did not observe processing log for: $DEST within 20s" >&2
  echo "Recent logs:" >&2
  journalctl -u "$UNIT" -n 100 --no-pager >&2 || true
  exit 3
fi
