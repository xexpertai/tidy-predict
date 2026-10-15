#!/usr/bin/env bash
# Everything that needs the local Gemma server, in one go (start it, run the checks, stop it).
# On a shared 10 GB laptop wrap it as:
#   flock ~/workspace/.heavy.lock systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=256M eval/run_with_model.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=${PORT:-8097}
export TIDY_LLM_URL=http://127.0.0.1:$PORT
R=eval/results
DEMO=data/raw/online_retail_II.csv
LABEL="Demo data: UCI Online Retail II (real, anonymised orders of a UK online gift shop, CC BY 4.0), replayed as of 27 Nov 2011"

if [ "${SKIP_APP_ONLY:-0}" != 1 ]; then
echo "== 1. app run without the model (measures the app alone)"
/usr/bin/time -v .venv/bin/tidy-predict "$DEMO" --as-of 2011-11-27 --no-llm --out out/demo-template --label "$LABEL" \
  > $R/demo_template.log 2> $R/demo_template.err || { tail -20 $R/demo_template.err; exit 1; }
grep -E "Maximum resident|Elapsed" $R/demo_template.err
fi

echo "== 2. start Gemma"
PORT=$PORT CTX=4096 scripts/start-model.sh > $R/llama-server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null; wait $SRV 2>/dev/null' EXIT
for i in $(seq 1 120); do curl -sf -m 2 $TIDY_LLM_URL/health >/dev/null && break; sleep 2; done
curl -sf -m 2 $TIDY_LLM_URL/health >/dev/null || { echo "model server did not start"; tail $R/llama-server.log; exit 1; }

echo "== 3. header mapping eval"
.venv/bin/python eval/columns_eval.py $R | tail -1

echo "== 4. note eval (one note per backtest week)"
.venv/bin/python eval/note_eval.py $R | tail -1

echo "== 5. demo run with Gemma"
/usr/bin/time -v .venv/bin/tidy-predict "$DEMO" --as-of 2011-11-27 --out out/demo --label "$LABEL" \
  > $R/demo.log 2> $R/demo.err || { tail -20 $R/demo.err; exit 1; }
grep -E "Maximum resident|Elapsed" $R/demo.err
ps -o rss= -p $SRV | awk '{printf "llama-server RSS %.0f MB\n", $1/1024}'

if [ "${RECORD:-0}" = 1 ]; then
  echo "== 6. record the web demo (real run through the local page)"
  .venv/bin/tidy-predict serve --port 8765 > $R/serve.log 2>&1 &
  WEB=$!
  trap 'kill $WEB 2>/dev/null; kill $SRV 2>/dev/null; wait 2>/dev/null' EXIT
  for i in $(seq 1 30); do curl -sf -m 2 http://127.0.0.1:8765/ >/dev/null && break; sleep 1; done
  rm -rf demo/raw
  # the browser runs in its own small scope so it can't push this one over its memory limit
  systemd-run --user --scope -q -p MemoryMax=1G -p MemorySwapMax=0 \
    .venv/bin/python scripts/record_demo.py data/raw/online_retail_II.csv 2011-11-27 demo/raw | tee $R/record.log
fi
echo "== done"
