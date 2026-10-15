#!/usr/bin/env bash
# Run tidy-predict's real forecast (TabPFN-2 regressor) on the full demo file inside a Linux network
# namespace with NO network at all (unshare -rn), after the weights are cached. Writes eval/results/offline_check.log.
set -uo pipefail
cd "$(dirname "$0")/.."
LOG=eval/results/offline_check.log
{
  echo "date: $(date -Is)"
  echo "command: unshare -rn .venv/bin/tidy-predict data/raw/online_retail_II.csv --as-of 2011-11-27 --no-llm --out out/offline"
  unshare -rn sh -c 'echo "network interfaces inside the namespace:"; ip -brief link; echo "internet reachable? $(curl -s -m 5 -o /dev/null -w %{http_code} https://huggingface.co || echo no)"'
  HF_HUB_OFFLINE=1 unshare -rn .venv/bin/tidy-predict data/raw/online_retail_II.csv --as-of 2011-11-27 --no-llm \
    --out out/offline --label "offline check" 2>&1 | grep -v -i -E "warn|_validate_num|tabpfn-client|consider using"
  echo "exit: ${PIPESTATUS[0]}"
  python3 -c "import json;r=json.load(open('out/offline/run.json'));print('target week',r['target_week'],'| forecast seconds',r['forecast_seconds'],'| products',len(r['facts']['items']),'| first item',r['facts']['items'][0])"
} > "$LOG" 2>&1
cat "$LOG"
