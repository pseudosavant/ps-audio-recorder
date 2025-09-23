#!/bin/bash

set -Eeuo pipefail

# Ensure a sane PATH under systemd
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/bin

# ReplayGain Auto-Processor (mp3gain)
# - Watches a directory for MP3 files and applies ReplayGain in track mode
# - Safe, idempotent, and resource-friendly for Raspberry Pi

# Defaults (can be overridden via environment file)
WATCH_PATH=${WATCH_PATH:-/srv/recordings}
RECURSIVE=${RECURSIVE:-1}                  # 1=yes, 0=no
LOG_LEVEL=${LOG_LEVEL:-info}               # info|debug|error
PROCESS_MODE=${PROCESS_MODE:-track}        # track|album (future)
EXCLUDE_REGEX=${EXCLUDE_REGEX:-'(\\.partial$|\\.part$|\\.tmp$)'}

# Optional: limit CPU/IO impact
NICE_LEVEL=${NICE_LEVEL:-15}
IONICE_CLASS=${IONICE_CLASS:-3}            # 3=idle IO

# Load environment overrides if present (same dir as script by default)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE_DEFAULT="$SCRIPT_DIR/replaygain-watcher.env"
if [[ -f "${ENV_FILE:-$ENV_FILE_DEFAULT}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE:-$ENV_FILE_DEFAULT}"
fi

# Enable shell tracing when debugging
if [[ "${LOG_LEVEL:-info}" == "debug" ]]; then
  set -x
fi

log() {
  local level="$1"; shift
  local ts
  ts="$(date +"%Y-%m-%dT%H:%M:%S%z")"
  # Level filtering
  case "$LOG_LEVEL" in
    debug) ;;
    info) [[ "$level" == debug ]] && return ;;
    error) [[ "$level" != error ]] && return ;;
  esac
  echo "$ts [$level] $*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    return 1
  fi
}

preflight() {
  log debug "boot: PATH=$PATH BASH_VERSION=${BASH_VERSION:-unknown}"
  local missing=()
  for cmd in inotifywait mp3gain stat awk sed tr; do
    if ! require_cmd "$cmd"; then
      missing+=("$cmd")
    fi
  done
  if ((${#missing[@]} > 0)); then
    log error "Missing required commands: ${missing[*]} — will retry in 60s"
    sleep 60
    return 1
  fi

  if [[ ! -d "$WATCH_PATH" ]]; then
    log error "Watch path not accessible: $WATCH_PATH — will retry in 10s"
    sleep 10
    return 1
  fi

  # Optional tools
  if command -v ionice >/dev/null 2>&1; then
    IONICE_AVAILABLE=1
  else
    IONICE_AVAILABLE=0
  fi
}

is_hidden_or_excluded() {
  local path="$1"
  # hidden path segments
  if [[ "$path" == .* || "$path" == */.* ]]; then
    return 0
  fi
  # exclude common temp/partial patterns
  if [[ "$path" =~ $EXCLUDE_REGEX ]]; then
    return 0
  fi
  return 1
}

has_mp3_ext() {
  local path="$1"
  local lower
  lower="$(echo -n "$path" | tr 'A-Z' 'a-z')"
  [[ "$lower" == *.mp3 ]]
}

settle_file() {
  local f="$1"
  # Wait until size is stable across two checks
  local last_size size attempts=0
  if [[ ! -f "$f" ]]; then
    return 1
  fi
  last_size="$(stat -c%s "$f" 2>/dev/null || echo -1)"
  while :; do
    sleep 1
    size="$(stat -c%s "$f" 2>/dev/null || echo -1)"
    if [[ "$size" -ge 0 && "$size" == "$last_size" ]]; then
      return 0
    fi
    last_size="$size"
    attempts=$((attempts+1))
    if (( attempts >= 30 )); then
      # 30s max wait
      return 1
    fi
  done
}

declare -A LAST_PROC_TS
DEBOUNCE_SEC=${DEBOUNCE_SEC:-10}

process_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    log error "File disappeared before processing: $file"
    return 1
  fi

  if ! settle_file "$file"; then
    log error "File did not settle within timeout: $file"
    return 1
  fi

  local mode_flag="-r"
  if [[ "$PROCESS_MODE" == "album" ]]; then
    mode_flag="-a"
  fi

  # Debounce: avoid re-processing same file too frequently
  local now ts_prev
  now=$(date +%s)
  ts_prev=${LAST_PROC_TS["$file"]:-0}
  if (( now - ts_prev < DEBOUNCE_SEC )); then
    log debug "debounce: $file"
    return 0
  fi

  # Build command with optional ionice
  local cmd=(mp3gain -q "$mode_flag" -k "$file")
  if (( IONICE_AVAILABLE == 1 )); then
    if nice -n "$NICE_LEVEL" ionice -c "$IONICE_CLASS" "${cmd[@]}"; then
      LAST_PROC_TS["$file"]=$now
      log info "replaygain OK: $file"
      return 0
    else
      local rc=$?
      log error "replaygain FAIL($rc): $file"
      return $rc
    fi
  fi

  if nice -n "$NICE_LEVEL" "${cmd[@]}"; then
    LAST_PROC_TS["$file"]=$now
    log info "replaygain OK: $file"
    return 0
  else
    local rc=$?
    log error "replaygain FAIL($rc): $file"
    return $rc
  fi
}

main_loop() {
  local -a INOTIFY_OPTS=("-m" "-e" "close_write,create,move,attrib")
  if [[ "$RECURSIVE" == "1" ]]; then
    INOTIFY_OPTS+=("-r")
  fi

  log info "Watching: $WATCH_PATH (recursive=$RECURSIVE)"
  # Using format: EVENTS|FULLPATH
  inotifywait "${INOTIFY_OPTS[@]}" --format '%e|%w%f' "$WATCH_PATH" | while IFS='|' read -r events fullpath; do
    # Normalize path (remove duplicate slashes)
    fullpath="$(echo -n "$fullpath" | sed 's://*:/:g')"

    # Filter: files only, mp3 ext, skip hidden/temp
    if [[ -d "$fullpath" ]]; then
      continue
    fi
    if is_hidden_or_excluded "$fullpath"; then
      log debug "skip excluded: $fullpath ($events)"
      continue
    fi
    if ! has_mp3_ext "$fullpath"; then
      log debug "skip non-mp3: $fullpath ($events)"
      continue
    fi

    # Only process on events that plausibly indicate finalization or content change
    if [[ "$events" =~ CLOSE_WRITE|MOVED_TO|ATTRIB|CREATE ]]; then
      process_file "$fullpath" || true
    fi
  done
}

# Supervisory loop: keep running even if dependencies/path are temporarily missing
while :; do
  if preflight; then
    main_loop || true
  fi
  sleep 3
done
