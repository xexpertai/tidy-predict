#!/usr/bin/env bash
# Download a CPU build of llama.cpp and Gemma 4 E2B-it (Q4_0 GGUF, ~2.8 GB) into this folder only
# (.tools/ and models/). No sudo, nothing global. Also pre-fetches the TabPFN-2 regressor weights
# (~30 MB) so later runs work with the network off.
set -euo pipefail
cd "$(dirname "$0")/.."
LLAMA_TAG="${LLAMA_TAG:-b11555}"
MODEL_REPO="${MODEL_REPO:-ggml-org/gemma-4-E2B-it-GGUF}"
MODEL_FILE="${MODEL_FILE:-gemma-4-E2B-it-Q4_0.gguf}"

if [ ! -x ".tools/llama/llama-$LLAMA_TAG/llama-server" ]; then
  mkdir -p .tools/llama
  curl -fL -o .tools/llama.tgz \
    "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/llama-$LLAMA_TAG-bin-ubuntu-x64.tar.gz"
  tar xzf .tools/llama.tgz -C .tools/llama && rm .tools/llama.tgz
fi
mkdir -p models
if [ ! -s "models/$MODEL_FILE" ]; then
  curl -fL -o "models/$MODEL_FILE" "https://huggingface.co/$MODEL_REPO/resolve/main/$MODEL_FILE"
fi
ls -lh "models/$MODEL_FILE"
.venv/bin/python - <<'PY'
from tabpfn import TabPFNRegressor
from tabpfn.constants import ModelVersion
import numpy as np
r = TabPFNRegressor.create_default_for_version(ModelVersion.V2, device="cpu", n_estimators=1)
r.fit(np.random.rand(20, 3), np.random.rand(20)); r.predict(np.random.rand(2, 3))
print("TabPFN-2 regressor weights cached")
PY
