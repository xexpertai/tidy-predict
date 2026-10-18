#!/usr/bin/env bash
# Re-record the live demo run (real TabPFN-2, real local Gemma, plain English headers) for video v9.
# Wrap: flock ~/workspace/.heavy.lock systemd-run --user --scope -p MemoryMax=4500M -p MemorySwapMax=256M eval/record_v9.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=8097
export TIDY_LLM_URL=http://127.0.0.1:$PORT
PORT=$PORT CTX=4096 scripts/start-model.sh > eval/results/llama-server-v9.log 2>&1 &
SRV=$!
.venv/bin/tidy-predict serve --port 8777 > eval/results/serve-v9.log 2>&1 &
WEB=$!
trap 'kill $WEB $SRV 2>/dev/null; wait 2>/dev/null' EXIT
for i in $(seq 1 120); do curl -sf -m 2 $TIDY_LLM_URL/health >/dev/null && break; sleep 2; done
for i in $(seq 1 30); do curl -sf -m 2 http://127.0.0.1:8777/ >/dev/null && break; sleep 1; done
rm -rf demo/raw-v9
systemd-run --user --scope -q -p MemoryMax=1G -p MemorySwapMax=0 \
  .venv/bin/python scripts/record_demo.py data/raw/gift_shop_orders.csv 2011-11-27 demo/raw-v9 http://127.0.0.1:8777 | tee eval/results/record-v9.log
