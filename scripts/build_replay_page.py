"""Build docs/index.html (public replay page) from a run directory.
Usage: python scripts/build_replay_page.py runs/<id>/out docs/index.html
Every number comes from run.json (facts, actuals, clean_stats, note) and forecast.csv / clean_sales.csv
(past weekly units for the sparkline, recomputed with tidy_predict.weekly.weekly_units)."""
import html, json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tidy_predict.clean import REASONS
from tidy_predict.weekly import weekly_units

out_dir, dest = Path(sys.argv[1]), Path(sys.argv[2])
run = json.loads((out_dir / "run.json").read_text())
fc = pd.read_csv(out_dir / "forecast.csv", dtype={"product": str})
lines = pd.read_csv(out_dir / "clean_sales.csv", dtype={"product": str}, parse_dates=["date"])
target = pd.Timestamp(run["target_week"])
tab = weekly_units(lines[lines.date < target], until=target - pd.Timedelta(days=1))
code = dict(zip(fc["name"], fc["product"]))
facts, act, note = run["facts"], run["actuals"], run["note"]
items = facts["items"]
WIDE = 8  # "wide range": P90 is at least 8x P10
e = lambda x: html.escape(str(x))

def hist(name):
    h = [int(x) for x in tab[code[name]].iloc[-12:]]
    assert h[-1] == next(i for i in items if i["product"] == name)["last_week_units"]
    return h

def spark(h, name):
    w, ht, pad = 110, 30, 3
    m = max(h) or 1
    pts = [(pad + i * (w - 2 * pad) / (len(h) - 1), ht - pad - (ht - 2 * pad) * v / m) for i, v in enumerate(h)]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lab = f"Weekly units sold, last {len(h)} weeks: lowest {min(h):,}, highest {max(h):,}, latest {h[-1]:,}"
    return (f'<svg class=spark viewBox="0 0 {w} {ht}" width={w} height={ht} role=img aria-label="{lab}">'
            f'<polyline points="{d}" fill=none stroke="currentColor" stroke-width=1.6 stroke-linejoin=round stroke-linecap=round />'
            f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r=2.6 fill="currentColor" /></svg>')

def rangebar(d, a):
    top = max(d["stock_for_busy_week"], a) * 1.04
    p = lambda v: 100 * v / top
    st = status(d, a)
    return (f'<span class="rbar" aria-hidden=true><i class=band style="left:{p(d["low_units"]):.1f}%;width:{p(d["stock_for_busy_week"]) - p(d["low_units"]):.1f}%"></i>'
            f'<i class=exp style="left:{p(d["expected_units"]):.1f}%"></i>'
            f'<i class="dot {st}" style="left:{p(a):.1f}%"></i></span>')

def status(d, a):
    return "above" if a > d["stock_for_busy_week"] else "below" if a < d["low_units"] else "inside"

FLAG = {"above": '<span class="flag above"><span aria-hidden=true>&#9650;</span> Sold above range</span>',
        "below": '<span class="flag below"><span aria-hidden=true>&#9660;</span> Sold below range</span>',
        "inside": '<span class="flag inside"><span aria-hidden=true>&#10003;</span> Inside range</span>'}
SWING = "Wide range: check by hand. Do not order from this row alone."

st = {i["product"]: status(i, act[i["product"]]) for i in items}
n = len(items)
n_in, n_ab, n_be = (sum(v == k for v in st.values()) for k in ("inside", "above", "below"))
assert n == facts["products_forecast"] == len(act) and n_in + n_ab + n_be == n

rows, cards = [], []
for d in items:
    nm, a = d["product"], act[d["product"]]
    s, h = st[nm], hist(nm)
    wide = bool(d.get("check_by_hand"))
    sw = f'<div class=swing>{SWING}</div>' if wide else ""
    rng = f'{d["low_units"]:,}&ndash;{d["stock_for_busy_week"]:,}'
    KG = " greyed" if wide else ""
    KV = "check by hand" if wide else format(d["stock_for_busy_week"], ",")
    rows.append(
        f'<tr class="{s}"><th scope=row class=prod>{e(nm)}{sw}</th>'
        f'<td class=spk>{spark(h, nm)}</td><td class=n>{d["expected_units"]:,}</td>'
        f'<td class=n>{rng}{rangebar(d, a)}</td>'
        + (f'<td class="n keep greyed">check by hand</td>' if d.get("check_by_hand") else f'<td class="n keep">{d["stock_for_busy_week"]:,}</td>') +
        f'<td class="n risk"><b>{d["sell_out_chance_pct"]}%</b></td>'
        f'<td class="n sold {s}"><b>{int(a):,}</b>{FLAG[s]}</td></tr>')
    cards.append(
        f'<li class="card {s}"><h3>{e(nm)}</h3>{sw}<div class=cspk><span>Past {len(h)} weeks</span>{spark(h, nm)}</div>'
        f'<dl><div><dt>Expected</dt><dd>{d["expected_units"]:,}</dd></div>'
        f'<div><dt>Likely range</dt><dd>{rng}</dd></div>'
        f'<div class="keepc{KG}"><dt>Keep for a busy week</dt><dd>{KV}</dd></div>'
        f'<div class=riskc><dt>Chance of selling out*</dt><dd>{d["sell_out_chance_pct"]}%</dd></div>'
        f'<div class="soldc {s}"><dt>Actually sold</dt><dd>{int(a):,}</dd></div></dl>'
        f'{rangebar(d, a)}<div class=cflag>{FLAG[s]}</div></li>')

cs = run["clean_stats"]
cleaned = "".join(f"<tr><th scope=row>{e(REASONS[k])}</th><td class=n>{v:,}</td></tr>" for k, v in cs.items() if k in REASONS and v)
wk = pd.Timestamp(run["target_week"]).strftime("%-d %b %Y")
first = tab.index[-12].strftime("%-d %b"); last = tab.index[-1].strftime("%-d %b %Y")

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5c5a54;--line:#e3e0d8;--accent:#2f6b4f;--soft:#eef4f0;--card:#fff;
--above:#8a4a00;--above-bg:#fff0d6;--above-bd:#d97a00;--below:#1f3d75;--below-bg:#e6edfa;--below-bd:#3a63b8;--in:#2f6b4f}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.banner{background:#7a4e0e;color:#fff;padding:12px 18px;font-weight:600;font-size:15px;text-align:center}
main{max-width:1040px;margin:0 auto;padding:28px 18px 56px}
h1{font-size:clamp(24px,4.4vw,34px);line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:20px;margin:36px 0 10px}h3{margin:0;font-size:17px}
.sub{color:var(--muted);margin:0 0 20px;font-size:15px}
.tag{display:inline-block;font-size:13px;padding:3px 10px;border-radius:12px;background:#f3ead7;color:#5e4410}
.note{background:var(--soft);border-left:5px solid var(--accent);padding:18px 20px;border-radius:8px;font-size:18px;line-height:1.55}
.note .lbl{display:block;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin-bottom:6px}
.by{color:var(--muted);font-size:13.5px;margin:8px 2px 0}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0 0;padding:0;list-style:none}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;border-top:4px solid var(--line)}
.stat b{display:block;font-size:34px;line-height:1.1;font-variant-numeric:tabular-nums}
.stat span{font-size:14px;line-height:1.3;color:var(--muted)}
.stat.in{border-top-color:var(--in)}.stat.ab{border-top-color:var(--above-bd)}.stat.be{border-top-color:var(--below-bd)}
.stat.ab b{color:var(--above)}.stat.be b{color:var(--below)}
.how{margin:22px 0 0;font-size:15px;color:#33322e}
.how details{margin-top:6px}.how summary{cursor:pointer;color:var(--accent);font-weight:600;display:inline-block}
.how .tip{margin-top:8px;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:8px;font-size:14px}
.how .tip p{margin:0 0 6px}.how .tip p:last-child{margin:0}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--muted);margin:10px 0 0}
.legend i{display:inline-block;vertical-align:middle;margin-right:5px}
.lg-band{width:22px;height:8px;background:rgba(47,107,79,.35);border-radius:2px}.lg-exp{width:2px;height:12px;background:var(--fg)}
.lg-dot{width:10px;height:10px;border-radius:50%;background:var(--fg)}
table{width:100%;border-collapse:collapse;font-size:15px;margin-top:12px}
caption{text-align:left;color:var(--muted);font-size:13px;padding-bottom:4px}
thead th{font-size:12.5px;font-weight:700;color:var(--muted);text-align:right;padding:8px 10px;border-bottom:2px solid var(--line);vertical-align:bottom}
thead th:first-child{text-align:left}
tbody th,tbody td{padding:10px;border-bottom:1px solid var(--line);vertical-align:middle}
tbody th{text-align:left;font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.spk{color:#4a6a5a;text-align:right;width:120px}.spark{display:block;margin-left:auto}
.greyed{color:#8a8a84!important;font-style:italic;font-weight:400}.greyed dd,.greyed b{color:#8a8a84!important;font-weight:400}
.swing{font-weight:400;font-size:12.5px;color:var(--muted);margin-top:2px}
td.keep{font-weight:700;background:#f6f3ea;border-left:1px solid var(--line)}
td.sold{background:#f6f3ea;border-right:1px solid var(--line);min-width:150px}td.sold b{display:block;font-size:16px}
tr.above td.sold,.soldc.above{background:var(--above-bg);box-shadow:inset 4px 0 0 var(--above-bd)}
tr.below td.sold,.soldc.below{background:var(--below-bg);box-shadow:inset 4px 0 0 var(--below-bd)}
.flag{display:inline-block;font-size:12px;font-weight:700;padding:2px 8px;border-radius:10px;white-space:nowrap}
.flag.above{background:#ffd89a;color:var(--above)}.flag.below{background:#c9d8f5;color:var(--below)}
.flag.inside{background:transparent;color:var(--in);padding-left:0;font-weight:600}
.rbar{position:relative;display:block;height:10px;margin:6px 0 0 auto;width:150px;background:#ece9e0;border-radius:3px}
.rbar i{position:absolute;top:0;height:100%}.rbar .band{background:rgba(47,107,79,.38);border-radius:2px}
.rbar .exp{width:2px;background:var(--fg);top:-2px;height:14px}
.rbar .dot{width:12px;height:12px;border-radius:50%;top:-1px;margin-left:-6px;background:var(--fg);border:2px solid #fff}
.rbar .dot.above{background:var(--above-bd)}.rbar .dot.below{background:var(--below-bd)}
.cards{display:none;list-style:none;margin:12px 0 0;padding:0;gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;border-left:5px solid var(--line)}
.card.above{border-left-color:var(--above-bd)}.card.below{border-left-color:var(--below-bd)}
.card .swing{margin:4px 0 0}.cspk{display:flex;justify-content:space-between;align-items:center;margin:8px 0;color:#4a6a5a;font-size:13px}
.cspk span{color:var(--muted)}.cspk .spark{margin:0}
.card dl{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0 0}.card dl div{padding:8px 10px;background:#f6f3ea;border-radius:8px}
.card dt{font-size:12px;color:var(--muted)}.card dd{margin:0;font-size:19px;font-weight:700;font-variant-numeric:tabular-nums}
.card dl .keepc{grid-row:2;grid-column:1}.card dl .riskc{grid-row:2;grid-column:2}.card dl .soldc{grid-row:3;grid-column:1 / 3}
td.risk{background:#f6f3ea}
.card .rbar{width:100%;margin:14px 0 4px}.cflag{margin-top:8px}
.clean{max-width:640px}.clean tbody th{font-weight:400}
footer{margin-top:44px;color:var(--muted);font-size:13.5px;border-top:1px solid var(--line);padding-top:14px}
footer p{margin:4px 0}.built{font-weight:700;color:var(--fg);font-size:15px}footer a{color:var(--accent)}
a:focus-visible,summary:focus-visible{outline:3px solid #1f5fbf;outline-offset:2px}
@media(max-width:860px){.stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:640px){main{padding:20px 14px 40px}.note{font-size:16.5px;padding:14px}
.stat b{font-size:28px}.stat{padding:12px}.table-wrap{display:none}.cards{display:grid}.legend{font-size:12.5px}}
@media print{body{background:#fff;font-size:12px}.banner{background:#fff;color:#000;border:1px solid #000}
.how details>.tip{display:block}.how summary{display:none}.card,.stat,tr{break-inside:avoid}
.table-wrap{display:block!important}.cards{display:none!important}.stat,.note,td.keep,td.sold{-webkit-print-color-adjust:exact;print-color-adjust:exact}
a{color:#000}}
"""

page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Restock note, week of {wk} (replay) | tidy-predict</title>
<meta name=description content="Replay of a public dataset: a plain-language restock note and a per-product forecast for 20 products, next to what really sold.">
<style>{CSS}</style></head>
<body><div class=banner role=note>Replay of a public dataset (UCI Online Retail II, CC BY 4.0) as of 27 Nov 2011. Not a client. No models run on this page.</div>
<main>
<h1>Restock note: week starting {wk}</h1>
<p class=sub><span class=tag>Demo data: UCI Online Retail II (real, anonymised orders of a UK online gift shop, CC BY 4.0), replayed as of 27 Nov 2011</span></p>
<p class=sub>The story around it: a <b>fictional</b> owner of a small online gift shop guesses next week's stock by eye. This public UK gift-shop export stands in for her orders; nobody has used the tool on a real shop. <a href="media/tidy-predict-demo-v8.mp4">Watch the 45-second demo video</a> (AI voice from my own voice sample, labelled in the video).</p>
<section aria-label="Restock note"><div class=note><span class=lbl>Restock note</span>{e(note["text"])}</div>
<p class=by>Written by {e(note["author"])}. Every number in it was checked against the table below.</p></section>
<ul class=stats aria-label="Summary of the replay">
<li class=stat><b>{n}</b><span>products forecast</span></li>
<li class="stat in"><b>{n_in}</b><span>sold inside the likely range</span></li>
<li class="stat ab"><b>{n_ab}</b><span><span aria-hidden=true>&#9650;</span> sold above the range</span></li>
<li class="stat be"><b>{n_be}</b><span><span aria-hidden=true>&#9660;</span> sold below the range</span></li></ul>
<div class=how><p style="margin:0"><b>How to read this:</b> the forecast gives a <em>likely range</em>. Most weeks should land inside it. &ldquo;Keep for a busy week&rdquo; is the top of that range, so you rarely run out.</p>
<details><summary>What do the technical names mean?</summary><div class=tip>
<p><b>Likely range</b> = P10 to P90. P10: sales fall below this in about 1 week out of 10. P90: sales go above this in about 1 week out of 10. So about 8 weeks out of 10 land in between.</p>
<p><b>Expected</b> = the middle forecast (P50, the median). <b>Keep for a busy week</b> = P90.</p>
<p><b>Actually sold</b> is what the shop really sold that week, from the same public file. The forecast never saw it.</p>
<p>The small line shows weekly units sold, {first} to {last} (12 full weeks before the forecast); each line is scaled to its own product, so compare shapes, not heights. &ldquo;Wide range: check by hand&rdquo; is shown when P90 is more than 10 times P10, or when last week was under a quarter of the 4-week average.</p></div></details>
<div class=legend aria-hidden=true><span><i class=lg-band></i>likely range</span><span><i class=lg-exp></i>expected</span><span><i class=lg-dot></i>actually sold</span></div></div>
<h2>Next week, per product</h2>
<div class=table-wrap><table><caption>Forecast for the week starting {wk}, in units, with what really sold. Sorted by &ldquo;Keep for a busy week&rdquo;.</caption>
<thead><tr><th scope=col>Product</th><th scope=col>Past 12 weeks</th><th scope=col>Expected</th><th scope=col>Likely range</th><th scope=col>Keep for a busy week</th><th scope=col>Chance of selling out*</th><th scope=col>Actually sold</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class=sub>* Chance that the week's demand is above what the shop would have if it stocked the busiest of its last 4 weeks, read from TabPFN's forecast distribution. The data has no real stock levels, so that level is the stand-in. It is a ranking signal (higher means more likely to sell out), not a precise probability. Never shown below 5% or above 95%.</p>
<ol class=cards aria-label="Forecast per product">{"".join(cards)}</ol>
<h2>What was cleaned</h2>
<p class=sub>{cs["rows_in"]:,} rows in, {cs["rows_out"]:,} rows counted as sales.
Nothing was deleted without a reason: every set-aside row is listed in <code>issues.csv</code> with its row number.</p>
<table class=clean><thead><tr><th scope=col>Reason</th><th scope=col>Rows</th></tr></thead><tbody>{cleaned}</tbody></table>
<footer><p class=built>Built with PriorLabs-TabPFN</p>
<p>Forecasts: TabPFN-2 (Prior Labs License, Apache 2.0 + attribution), run on this computer. The note was written by Gemma (open weights, Apache 2.0) via llama.cpp, also on this computer. No data left the machine.</p>
<p>Code and method: <a href="https://github.com/xexpertai/tidy-predict">github.com/xexpertai/tidy-predict</a>. Data: UCI Online Retail II, CC BY 4.0.</p>
<p>AI assistance: this project was built with an AI coding agent (Claude Code), directed and reviewed by the author. This page is a replay of one saved run; no model runs in your browser.</p>
<p>Run: forecast time {run["forecast_seconds"]:.0f} s, total time {run["total_seconds"]:.0f} s.</p></footer>
</main></body></html>"""
dest.write_text(page)
print("wrote", dest, len(page), "bytes;", n_in, n_ab, n_be)
