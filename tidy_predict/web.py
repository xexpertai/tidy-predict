"""A one-page local web UI: drop in an order export, watch each step, read the restock note.

Standard library only. It listens on 127.0.0.1, so nothing is reachable from other machines, and
the uploaded file is written to ./runs/<id>/ on this computer and nowhere else.
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
import traceback
import uuid
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .cli import PipelineError, run_pipeline
from .report import CSS

RUNS = Path("runs")
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
ALLOWED = {"report.html", "forecast.csv", "issues.csv", "clean_sales.csv", "run.json"}

FOOT = ("<footer><div class=built>Built with PriorLabs-TabPFN</div>Forecasts: TabPFN-2 · Note: Gemma via llama.cpp · "
        "both run on this computer. Nothing is uploaded anywhere.</footer>")
EXTRA_CSS = """
form{display:grid;gap:14px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:18px}
label{font-weight:600;font-size:14px}input[type=text],input[type=date]{font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;width:100%}
.drop{border:2px dashed #b9c9bf;border-radius:8px;padding:22px;text-align:center;background:var(--soft)}
button{font:inherit;font-weight:600;background:var(--accent);color:#fff;border:0;border-radius:6px;padding:10px 16px;cursor:pointer;justify-self:start}
.log{font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#1e2321;color:#e8efe9;border-radius:8px;padding:14px 16px;min-height:120px;white-space:pre-wrap}
.log .t{color:#8fb59c}.spin{display:inline-block;animation:p 1s infinite}@keyframes p{50%{opacity:.3}}
iframe{width:100%;height:1400px;border:1px solid var(--line);border-radius:8px;background:#fff}
.links a{margin-right:14px}
"""


def page(title: str, body: str) -> bytes:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}{EXTRA_CSS}</style></head><body><main>"
            f"{body}{FOOT}</main></body></html>").encode()


HOME = """<h1>tidy-predict</h1>
<p class=sub>Drop in a shop's order export. Get back a cleaned file, next week's units per product, and a short
restock note. Everything runs on this computer.</p>
<form method=post action=/run enctype=multipart/form-data>
  <div class=drop><label for=f>Order export (.csv or .xlsx)</label><br><input id=f type=file name=file accept=".csv,.xlsx" required></div>
  <div><label for=asof>Pretend today is (optional, for replaying past data)</label><input id=asof type=date name=as_of></div>
  <div><label for=lab>Label for the report</label><input id=lab type=text name=label value="Client data"></div>
  <button type=submit>Make the restock note</button>
</form>"""

JOB = """<h1>Working on {name}</h1><p class=sub>Each step is logged as it happens.</p>
<div class=log id=log></div><div id=done></div>
<script>
const id={id!r};
async function tick(){{
  const r=await fetch('/job/'+id+'/status'); const s=await r.json();
  document.getElementById('log').innerHTML=s.log.map(l=>'<span class=t>'+l[0].toFixed(0).padStart(4,' ')+' s</span>  '+l[1]
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')).join('\\n')+(s.state==='running'?'\\n<span class=spin>…</span>':'');
  if(s.state==='done'){{document.getElementById('done').innerHTML=
    '<h2>Restock note</h2><p class=links><a href="/job/'+id+'/report.html" target=_blank>Open report</a>'+
    '<a href="/job/'+id+'/forecast.csv">forecast.csv</a><a href="/job/'+id+'/issues.csv">issues.csv</a>'+
    '<a href="/job/'+id+'/clean_sales.csv">clean_sales.csv</a></p><iframe src="/job/'+id+'/report.html"></iframe>';return;}}
  if(s.state==='error'){{document.getElementById('done').innerHTML='<p><b>Stopped:</b> '+s.error.replace(/</g,'&lt;')+'</p>';return;}}
  setTimeout(tick,1000);
}}
tick();
</script>"""


def _start_job(filename: str, data: bytes, as_of: str | None, label: str, use_llm: bool) -> str:
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = RUNS / jid
    d.mkdir(parents=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name) or "upload.csv"
    src = d / safe
    src.write_bytes(data)
    job = {"state": "running", "log": [], "t0": time.time(), "name": safe, "error": None, "dir": d}
    with _LOCK:
        JOBS[jid] = job

    def log(m: str) -> None:
        job["log"].append((time.time() - job["t0"], m))

    def work() -> None:
        try:
            run_pipeline(src, d / "out", as_of or None, 20, use_llm, label or "Client data", log)
            job["state"] = "done"
        except PipelineError as e:
            job["state"], job["error"] = "error", str(e)
        except Exception as e:  # show the problem instead of hanging
            traceback.print_exc()
            job["state"], job["error"] = "error", f"{type(e).__name__}: {e}"

    threading.Thread(target=work, daemon=True).start()
    return jid


def make_handler(use_llm: bool):
    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

        def do_GET(self):
            p = self.path.split("?")[0]
            if p == "/":
                return self._send(200, page("tidy-predict", HOME))
            m = re.fullmatch(r"/job/([\w-]+)(?:/(.*))?", p)
            job = JOBS.get(m.group(1)) if m else None
            if not job:
                return self._send(404, page("Not found", "<h1>Not found</h1>"))
            jid, rest = m.group(1), m.group(2)
            if not rest:
                return self._send(200, page("Working", JOB.format(id=jid, name=html.escape(job["name"]))))
            if rest == "status":
                body = {"state": job["state"], "error": job["error"], "log": job["log"]}
                return self._send(200, json.dumps(body).encode(), "application/json")
            if rest in ALLOWED and job["state"] == "done":
                f = job["dir"] / "out" / rest
                ctype = {"html": "text/html; charset=utf-8", "csv": "text/csv", "json": "application/json"}[rest.rsplit(".", 1)[1]]
                return self._send(200, f.read_bytes(), ctype)
            return self._send(404, page("Not found", "<h1>Not found</h1>"))

        def do_POST(self):
            if self.path != "/run":
                return self._send(404, b"")
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            msg = BytesParser(policy=email_policy).parsebytes(
                b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw)
            fields, upload = {}, None
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if part.get_filename():
                    upload = (part.get_filename(), part.get_payload(decode=True))
                else:
                    fields[name] = part.get_content().strip()
            if not upload or not upload[1]:
                return self._send(400, page("No file", "<h1>Please choose a file</h1><a href=/>Back</a>"))
            jid = _start_job(upload[0], upload[1], fields.get("as_of"), fields.get("label", ""), use_llm)
            self.send_response(303)
            self.send_header("Location", f"/job/{jid}")
            self.end_headers()

    return H


def serve(port: int = 8765, use_llm: bool = True) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(use_llm))
    print(f"tidy-predict on http://127.0.0.1:{port}  (Ctrl-C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
