#!/usr/bin/env bash
# Record the demo end to end on this laptop: local Gemma (llama.cpp) + the web page + Playwright.
# Heavy processes are memory-capped (systemd scopes) and serialised on a lock shared with other jobs.
# Usage: scripts/video/record_session.sh <export.csv> <as-of YYYY-MM-DD> <out dir>
set -euo pipefail
cd "$(dirname "$0")/../.."
SRC=$1; ASOF=$2; OUT=$3; APP_PORT=${APP_PORT:-8765}
CAP=(systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=256M)
exec 9>"${HEAVY_LOCK:-$HOME/workspace/.heavy.lock}"; flock 9
"${CAP[@]}" scripts/start-model.sh > "$OUT.model.log" 2>&1 &
MODEL=$!
"${CAP[@]}" .venv/bin/tidy-predict serve --port "$APP_PORT" > "$OUT.serve.log" 2>&1 &
APP=$!
trap 'kill $MODEL $APP 2>/dev/null; pkill -f llama-server 2>/dev/null || true' EXIT
for i in $(seq 1 120); do curl -sf "127.0.0.1:8088/health" >/dev/null && break; sleep 2; done
curl -sf 127.0.0.1:8088/health >/dev/null || { echo "model server did not come up"; exit 1; }
echo "model up after $((i*2)) s"
.venv/bin/python scripts/record_demo.py "$SRC" "$ASOF" "$OUT" "http://127.0.0.1:$APP_PORT"
