"""One self-contained HTML page for the shop owner: the note, the stock table, and what was cleaned."""
from __future__ import annotations

import html

import pandas as pd

from .clean import REASONS

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#666;--line:#e3e0d8;--accent:#2f6b4f;--soft:#eef4f0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}
.sub{color:var(--muted);margin:0 0 18px}
.note{background:var(--soft);border-left:4px solid var(--accent);padding:14px 16px;border-radius:6px;font-size:17px}
.by{color:var(--muted);font-size:13px;margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}th{font-weight:600;color:var(--muted);font-size:13px}
td.n{font-variant-numeric:tabular-nums;white-space:nowrap}.bar{display:inline-block;vertical-align:middle;margin-right:8px;height:8px;background:var(--accent);border-radius:4px;opacity:.75}
.tag{display:inline-block;font-size:12px;padding:2px 8px;border-radius:10px;background:#f3ead7;color:#6b4e12}
footer{margin-top:32px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:12px}
.flag{display:inline-block;font-size:12px;font-weight:600;padding:1px 8px;border-radius:10px;margin-left:6px;background:#ffe2a8;color:#7a4300}
tr.above td{background:#fff3da}tr.above td:first-child{box-shadow:inset 4px 0 0 #e08a00}td.n.above b,td.n.above{color:#7a4300;font-weight:700}
tr.below td{background:#eef1f6}tr.below td:first-child{box-shadow:inset 4px 0 0 #6b7fa8}.flag.low{background:#dbe3f2;color:#27406e}
.built{font-weight:600;color:var(--fg)}
.scroll{overflow-x:auto}
.greyed{color:#8a8a84;font-style:italic;background:#f1efe9}
.flag.chk{background:#fde9c4;color:#7a4a00;display:block;margin:3px 0 0 0;width:max-content}
"""


def _e(x) -> str:
    return html.escape(str(x))


CHK = "<span class='flag chk'>wide range: check by hand</span>"


def risk_cell(d) -> str:
    c = d.get("sell_out_chance_pct")
    return "<td class=n>n/a</td>" if c is None else f"<td class=n><b>{c}%</b></td>"


def render(facts: dict, note_text: str, note_author: str, clean_stats: dict, data_label: str,
           actuals: dict[str, float] | None = None, run_info: dict | None = None) -> str:
    items = facts["items"]
    top = max([d["stock_for_busy_week"] for d in items] + [1])
    rows = []
    for d in items:
        w = int(110 * d["stock_for_busy_week"] / top)
        act, cls = "", ""
        if actuals is not None:
            a = actuals.get(d["product"])
            if a is not None and a > d["stock_for_busy_week"]:
                cls, act = " class=above", f"<td class='n above'>{int(a):,}<span class=flag>sold above range</span></td>"
            elif a is not None and a < d["low_units"]:
                cls, act = " class=below", f"<td class=n>{int(a):,}<span class='flag low'>sold below range</span></td>"
            else:
                act = f"<td class=n>{'' if a is None else int(a)}</td>"
        rows.append(
            f"<tr{cls}><td>{_e(d['product'])}{CHK if d.get('check_by_hand') else ''}</td><td class=n>{d['last_week_units']}</td>"
            f"<td class=n>{d['avg_last_4_weeks']}</td><td class=n><b>{d['expected_units']}</b></td>"
            f"<td class='n{' greyed' if d.get('check_by_hand') else ''}'>{d['low_units']}&ndash;{d['stock_for_busy_week']}</td>" +
            (f"<td class='n greyed'>check by hand</td>" if d.get('check_by_hand') else
             f"<td class=n><span class=bar style='width:{w}px'></span> <b>{d['stock_for_busy_week']}</b></td>") + f"{risk_cell(d)}{act}</tr>")
    act_head = "<th>Actually sold</th>" if actuals is not None else ""
    cleaned = [(REASONS[k], v) for k, v in clean_stats.items() if k in REASONS and v]
    clean_rows = "".join(f"<tr><td>{_e(r)}</td><td class=n>{v:,}</td></tr>" for r, v in cleaned)
    ri = run_info or {}
    run_line = " · ".join(f"{_e(k)}: {_e(v)}" for k, v in ri.items())
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Restock note</title><style>{CSS}</style></head>
<body><main>
<h1>Restock note: week starting {_e(facts['week_starting'])}</h1>
<p class=sub><span class=tag>{_e(data_label)}</span></p>
<div class=note>{_e(note_text)}</div>
<div class=by>Written by {_e(note_author)}. Every number in it was checked against the table below.</div>
<h2>Next week, per product</h2>
<div class=scroll><table><tr><th>Product</th><th>Last week</th><th>4-week avg</th><th>Expected</th>
<th>Likely range (P10&ndash;P90)</th><th>Stock for a busy week (P90)</th><th>Sell-out chance*</th>{act_head}</tr>
{''.join(rows)}</table></div>
<p class=sub>* Chance that demand is above the busiest of the last 4 weeks (the stand-in for stock). Read it as a ranking signal, not a precise probability.</p>
<h2>What was cleaned</h2>
<p class=sub>{clean_stats.get('rows_in', 0):,} rows in, {clean_stats.get('rows_out', 0):,} rows counted as sales.
Nothing was deleted without a reason: every set-aside row is listed in <code>issues.csv</code> with its row number.</p>
<div class=scroll><table><tr><th>Reason</th><th>Rows</th></tr>{clean_rows}</table></div>
<footer><div class=built>Built with PriorLabs-TabPFN</div>
Forecasts: TabPFN-2 (Prior Labs License, Apache 2.0 + attribution), run on this computer.
Note: Gemma (open weights, Apache 2.0) via llama.cpp, run on this computer. No data left the machine.
<div>{run_line}</div></footer>
</main></body></html>"""
