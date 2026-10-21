#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
API_ARGS=()
ARGS=()
PRODUCTION=0
VIEWER_PORT=3000
CONFIG_REQUESTED=0
while (($#)); do
  case "$1" in
    --replays|--config)
      if [[ $# -lt 2 || -z "$2" ]]; then echo "$1 requires a path." >&2; exit 2; fi
      API_ARGS+=("$1" "$2"); CONFIG_REQUESTED=1; shift 2 ;;
    --production) PRODUCTION=1; shift ;;
    --port|-p)
      if [[ $# -lt 2 ]]; then echo "$1 requires a port." >&2; exit 2; fi
      VIEWER_PORT="$2"; ARGS+=("$1" "$2"); shift 2 ;;
    --help|-h)
      printf '%s\n' 'Agewise local replay coach' 'Usage: ./run-viewer.sh [--production] [--replays PATH ...] [--config FILE] [--port 3000]' 'Folder precedence: --replays > AOE2_REPLAY_DIR > --config / agewise.local.json > discovery.' 'Folder changes require restarting the API and viewer. Paths with spaces must be quoted.' 'Setup: docs/setup.md. Startup does not install or update dependencies.'
      exit 0 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
if [[ -n "${AOE2_REPLAY_DIR:-}" || -f "$ROOT/agewise.local.json" ]]; then CONFIG_REQUESTED=1; fi
NODE_BIN="${AOE2_NODE_BIN:-}"
if [[ -z "$NODE_BIN" ]]; then
  for candidate in "$HOME/.local/share/pi-node/current/bin/node" /usr/bin/node "$(command -v node 2>/dev/null || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]] && [[ "$("$candidate" -p 'process.platform' 2>/dev/null || true)" == linux ]]; then NODE_BIN="$candidate"; break; fi
  done
fi
if [[ -z "$NODE_BIN" ]]; then echo 'Linux Node.js required. See docs/setup.md.' >&2; exit 1; fi
if [[ ! -f "$ROOT/viewer/node_modules/next/dist/bin/next" ]]; then echo 'Viewer dependencies missing. Run npm ci in viewer as described in docs/setup.md; startup never installs packages.' >&2; exit 1; fi
API_PORT="${AOE2_COACH_API_PORT:-8765}"
API_URL="${NEXT_PUBLIC_COACH_API_URL:-http://127.0.0.1:${API_PORT}}"
api_health() { curl -fsS "$API_URL/api/health" 2>/dev/null || true; }
api_is_current() {
  local health="${1:-$(api_health)}"
  [[ "$health" == *'"api_version": 4'* && "$health" == *'"matchup_version": 1'* && "$health" == *'"provenance_version": 2'* && "$health" == *'"situation_version": 1'* && "$health" == *'"situation_review_version": 2'* && "$health" == *'"observations_version": 1'* && "$health" == *'"reviewed_moments_version": 1'* && "$health" == *'"practice_version": 1'* && "$health" == *'"practice_controls_version": 1'* && "$health" == *'"gameplay_version": 2'* && "$health" == *'"progress_version": 1'* && "$health" == *'"takeaway_version": 1'* && "$health" == *'"reasoning_version": 1'* && "$health" == *'"library_visuals_version": 1'* && "$health" == *'"replay_settings_version": 1'* ]]
}
export NEXT_PUBLIC_COACH_API_URL="$API_URL"
export NEXT_TELEMETRY_DISABLED=1
API_PID=""
NEXT_PID=""
cleanup() {
  if [[ -n "$NEXT_PID" ]]; then kill "$NEXT_PID" 2>/dev/null || true; wait "$NEXT_PID" 2>/dev/null || true; fi
  if [[ -n "$API_PID" ]]; then kill "$API_PID" 2>/dev/null || true; wait "$API_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
HEALTH="$(api_health)"
if [[ -n "$HEALTH" ]] && ! api_is_current "$HEALTH"; then echo "An older Agewise API is already running at $API_URL. Stop that API/viewer and restart this launcher." >&2; exit 1; fi
if [[ -n "$HEALTH" && "$CONFIG_REQUESTED" == 1 ]]; then echo 'Replay folder settings were requested, but an API is already running. Stop it before restarting; existing folder settings will not be silently reused.' >&2; exit 1; fi
if [[ "$PRODUCTION" == 1 ]]; then
  if (echo > "/dev/tcp/127.0.0.1/${VIEWER_PORT}") 2>/dev/null; then echo "Stop the viewer on port $VIEWER_PORT before building production mode." >&2; exit 1; fi
  (cd "$ROOT/viewer" && "$NODE_BIN" node_modules/next/dist/bin/next build)
fi
if [[ -z "$HEALTH" ]]; then
  mkdir -p "$ROOT/data"
  "$ROOT/run.sh" --port "$API_PORT" "${API_ARGS[@]}" >"$ROOT/data/replay-lab-api.log" 2>&1 &
  API_PID=$!
  for _ in $(seq 1 120); do
    if api_is_current; then break; fi
    if ! kill -0 "$API_PID" 2>/dev/null; then echo 'Could not start local API. Check data/replay-lab-api.log and your folder settings.' >&2; exit 1; fi
    sleep 0.5
  done
  if ! api_is_current; then echo 'Timed out starting local API.' >&2; exit 1; fi
fi
echo "Agewise: http://127.0.0.1:${VIEWER_PORT} (local API: $API_URL)"
cd "$ROOT/viewer"
if [[ "$PRODUCTION" == 1 ]]; then
  "$NODE_BIN" node_modules/next/dist/bin/next start --hostname 127.0.0.1 "${ARGS[@]}" &
else
  "$NODE_BIN" node_modules/next/dist/bin/next dev --webpack --hostname 127.0.0.1 "${ARGS[@]}" &
fi
NEXT_PID=$!
wait "$NEXT_PID"
