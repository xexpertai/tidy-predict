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
main{max-width:920px}
.top{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:4px 0 18px}
.top h1{font-size:30px;letter-spacing:-.02em}.top .local{font-size:13px;color:var(--muted);background:#fff;border:1px solid var(--line);
border-radius:999px;padding:4px 12px;white-space:nowrap}.top .local::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;
background:var(--accent);margin-right:7px;vertical-align:1px}
form{display:grid;grid-template-columns:minmax(0,1fr);gap:18px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:22px 24px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
label{font-weight:600;font-size:14px;display:block;margin-bottom:6px}
input[type=text]{font:inherit;font-size:16px;padding:10px 12px;border:1px solid #cfd6d1;border-radius:8px;width:100%;background:#fff;color:var(--fg)}
input[type=text]:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:var(--accent)}
.hint{font-weight:400;color:var(--muted);font-size:13px;margin-top:4px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.drop{position:relative;border:2px dashed #b9c9bf;border-radius:12px;padding:30px 20px;text-align:center;background:var(--soft);transition:background .15s,border-color .15s;cursor:pointer}
.drop.over,.drop:hover{background:#e4efe7;border-color:var(--accent)}
.drop input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
.drop .ic{width:40px;height:40px;margin:0 auto 8px;color:var(--accent)}.drop b{font-size:18px}.drop .or{color:var(--muted);font-size:14px;margin-top:4px}
.drop .or u{color:var(--accent);text-decoration:none;font-weight:600;border-bottom:1px solid currentColor}
.chip{display:inline-flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:15px;margin-top:12px}
.chip .sz{color:var(--muted);font-size:13px}
.drop{min-width:0}.prev{margin-top:14px;text-align:left;max-width:100%;overflow-x:auto}.prev .cap{font-size:13px;color:var(--muted);margin:0 0 6px}
.prev table{font-size:13px;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.prev th{background:#f3ead7;color:#6b4e12;text-align:left;font-size:12px;white-space:nowrap;padding:6px 6px}.prev td{padding:6px 6px}.prev td{text-align:left;white-space:nowrap;max-width:120px;overflow:hidden;text-overflow:ellipsis}
button{font:inherit;font-size:16px;font-weight:600;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:12px 20px;cursor:pointer;justify-self:start}
button:hover{background:#265a42}
.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:22px 0 0}
.step{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:14px;line-height:1.35}
.step b{display:block;font-size:13px;color:var(--muted);font-weight:600;margin-bottom:3px}
.step.on{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}.step.ok b{color:var(--accent)}.step.ok b::before{content:"\\2713  "}
.log{font:14.5px/1.65 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#1e2321;color:#e8efe9;border-radius:10px;padding:16px 18px;min-height:132px;white-space:pre-wrap;margin-top:16px}
.log .t{color:#8fb59c}.log .hi{color:#f3d58a}.spin{display:inline-block;animation:p 1s infinite}@keyframes p{50%{opacity:.3}}
.result{margin-top:22px}.result h2{margin-top:0}
.links{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 12px}.links a{background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 14px;text-decoration:none;color:var(--fg);font-size:15px}
.links a.main{background:var(--accent);color:#fff;border-color:var(--accent)}
iframe{width:100%;height:1500px;border:1px solid var(--line);border-radius:10px;background:#fff}
"""


def page(title: str, body: str) -> bytes:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}{EXTRA_CSS}</style></head><body><main>"
            f"{body}{FOOT}</main></body></html>").encode()


TOP = "<div class=top><h1>tidy-predict</h1><span class=local>Runs on this computer</span></div>"
HOME = TOP + """<p class=sub>Drop in a shop's order export, any column names. Get back a cleaned file, next week's units
per product with a likely range, and a short restock note.</p>
<form method=post action=/run enctype=multipart/form-data>
  <div class=drop id=drop>
    <svg class=ic viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4m0 0l-4 4m4-4l4 4"/><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3"/></svg>
    <b>Drop the order export here</b>
    <div class=or>or <u>choose a file</u> &middot; .csv or .xlsx</div>
    <input id=f type=file name=file accept=".csv,.xlsx" required aria-label="Order export (.csv or .xlsx)">
    <div id=chip></div><div id=prev class=prev></div>
  </div>
  <div class=two>
    <div><label for=asof>Pretend today is</label><input id=asof type=text name=as_of inputmode=numeric placeholder="YYYY-MM-DD" pattern="\d{4}-\d{2}-\d{2}" autocomplete=off><div class=hint>Optional, YYYY-MM-DD: replay past data and compare with what really sold.</div></div>
    <div><label for=lab>Label on the report</label><input id=lab type=text name=label value="Client data"><div class=hint>Say whose data it is, or that it's a demo.</div></div>
  </div>
  <button type=submit>Make the restock note</button>
</form>
<div class=steps>
  <div class=step><b>1 &middot; Columns</b>Header rules first; odd names go to the local Gemma model.</div>
  <div class=step><b>2 &middot; Clean</b>Duplicates, returns, postage lines set aside and listed.</div>
  <div class=step><b>3 &middot; Forecast</b>TabPFN-2 gives each product a range for next week.</div>
  <div class=step><b>4 &middot; Note</b>Gemma writes it; every number is checked against the table.</div>
</div>
<script>
const f=document.getElementById('f'),drop=document.getElementById('drop'),chip=document.getElementById('chip'),prev=document.getElementById('prev');
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
function cells(line){const o=[];let q=false,c='';for(const ch of line){if(ch=='"'){q=!q}else if(ch==','&&!q){o.push(c);c=''}else c+=ch}o.push(c);return o}
function show(){const file=f.files[0];if(!file)return;
  chip.innerHTML='<span class=chip>&#128196; '+esc(file.name)+' <span class=sz>'+(file.size/1048576).toFixed(1)+' MB</span></span>';
  if(!/\\.csv$/i.test(file.name)){prev.innerHTML='';return}
  file.slice(0,4096).text().then(t=>{const L=t.split(/\\r?\\n/).filter(x=>x).slice(0,4);if(L.length<2)return;
    const h=cells(L[0]);prev.innerHTML='<p class=cap>First rows of the file, as sent:</p><table><tr>'+h.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr>'+
    L.slice(1).map(r=>'<tr>'+cells(r).slice(0,h.length).map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</table>'})}
f.addEventListener('change',show);
['dragenter','dragover'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('over')}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{drop.classList.remove('over')}));
</script>"""

JOB = TOP + """<p class=sub>Working on <b>{name}</b>. Each step is logged as it happens.</p>
<div class=steps id=steps>
  <div class=step><b>1 &middot; Columns</b>Header rules, then the local Gemma model for odd names.</div>
  <div class=step><b>2 &middot; Clean</b>Duplicates, returns, postage lines set aside.</div>
  <div class=step><b>3 &middot; Forecast</b>TabPFN-2, one range per product.</div>
  <div class=step><b>4 &middot; Note</b>Gemma writes, the number check reads.</div>
</div>
<div class=log id=log><span class=t>   0 s</span>  Upload received. Reading the file...
<span class=spin>...</span></div><div id=done class=result></div>
<script>
const id={id!r};const steps=document.querySelectorAll('#steps .step');
const stage=l=>/^Read /.test(l)?1:/^Columns found/.test(l)?2:/^Cleaned|^Forecasting/.test(l)?3:/^Forecast done|^Writing/.test(l)?4:/^Note written|^Done/.test(l)?5:0;
function paint(st){{steps.forEach((s,i)=>{{s.className='step'+(i+1<st?' ok':i+1==st?' on':'')}})}}
async function tick(){{
  const r=await fetch('/job/'+id+'/status'); const s=await r.json();
  const lines=[[0,'Upload received. Reading the file...']].concat(s.log);
  document.getElementById('log').innerHTML=lines.map(l=>'<span class=t>'+l[0].toFixed(0).padStart(4,' ')+' s</span>  '+l[1]
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/(\\S+ \\u2192 \\S+)/g,'<span class=hi>$1</span>')).join('\\n')+(s.state==='running'?'\\n<span class=spin>...</span>':'');
  let st=0;for(const l of s.log)st=Math.max(st,stage(l[1]));paint(s.state==='done'?5:st);
  if(s.state==='done'){{document.getElementById('done').innerHTML=
    '<h2>Restock note</h2><p class=links><a class=main href="/job/'+id+'/report.html" target=_blank>Open the report</a>'+
    '<a href="/job/'+id+'/forecast.csv">forecast.csv</a><a href="/job/'+id+'/issues.csv">issues.csv</a>'+
    '<a href="/job/'+id+'/clean_sales.csv">clean_sales.csv</a></p><iframe src="/job/'+id+'/report.html"></iframe>';return;}}
  if(s.state==='error'){{document.getElementById('done').innerHTML='<p><b>Stopped:</b> '+s.error.replace(/</g,'&lt;')+'</p>';return;}}
  setTimeout(tick,700);
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
