#!/usr/bin/env bash
# Re-run the note check eval with the current prompt (adds the sell-out sentence). Wrap in flock + systemd-run like run_with_model.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
export TIDY_LLM_URL=http://127.0.0.1:8098
PORT=8098 CTX=4096 scripts/start-model.sh > eval/results/llama-server-note.log 2>&1 &
SRV=$!; trap 'kill $SRV 2>/dev/null; wait 2>/dev/null' EXIT
for i in $(seq 1 120); do curl -sf -m 2 $TIDY_LLM_URL/health >/dev/null && break; sleep 2; done
.venv/bin/python eval/note_eval.py eval/results | tail -1
