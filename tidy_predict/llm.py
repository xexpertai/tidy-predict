"""Tiny client for a local llama.cpp server (OpenAI-compatible API) running Gemma.

Nothing here talks to the internet: the default URL is 127.0.0.1. If the server isn't running,
callers fall back to deterministic code, so the tool still works (just with a template note).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("TIDY_LLM_URL", "http://127.0.0.1:8088")


class LLMUnavailable(RuntimeError):
    pass


def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise LLMUnavailable(str(e)) from e


def available(url: str = DEFAULT_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def model_name(url: str = DEFAULT_URL) -> str:
    try:
        with urllib.request.urlopen(f"{url}/v1/models", timeout=3) as r:
            data = json.load(r)
        name = data["data"][0]["id"]
        return os.path.basename(name).removesuffix(".gguf")
    except Exception:
        return "local model"


def chat(messages: list[dict], *, schema: dict | None = None, max_tokens: int = 400,
         temperature: float = 0.2, seed: int = 7, url: str = DEFAULT_URL, timeout: float = 300) -> tuple[str, dict]:
    """Return (text, info). With ``schema`` the output is grammar-constrained JSON."""
    body: dict = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature, "seed": seed}
    if schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
    t0 = time.time()
    r = _post(f"{url}/v1/chat/completions", body, timeout)
    text = r["choices"][0]["message"].get("content") or ""
    info = {"seconds": round(time.time() - t0, 1), "usage": r.get("usage", {}),
            "tokens_per_s": (r.get("timings") or {}).get("predicted_per_second")}
    return text, info


MODEL_FIELDS = {
    "invoice_date": "date (and maybe time) of the sale",
    "quantity": "number of units sold on the line",
    "product": "which product was sold (its name, or its code if there is no name column)",
}


def map_columns(headers: list[str], sample_rows: list[list[str]], url: str = DEFAULT_URL) -> tuple[dict, dict]:
    """Ask the local model only for the fields the forecast cannot do without. Answers can only be real
    headers or null (JSON schema), and the caller re-checks them."""
    choice = {"anyOf": [{"type": "string", "enum": list(headers)}, {"type": "null"}]}
    schema = {"type": "object", "properties": {f: choice for f in MODEL_FIELDS}, "required": list(MODEL_FIELDS),
              "additionalProperties": False}
    preview = "\n".join([" | ".join(headers)] + [" | ".join(map(str, r)) for r in sample_rows[:3]])
    msg = ("A small shop exported its sales. Here are the column headers and the first rows:\n\n"
           f"{preview}\n\nFor each field, give the header that holds it, or null if no column does.\n"
           + "\n".join(f"- {f}: {d}" for f, d in MODEL_FIELDS.items()))
    text, info = chat([{"role": "user", "content": msg}], schema=schema, max_tokens=200, temperature=0, url=url)
    return json.loads(text), info
