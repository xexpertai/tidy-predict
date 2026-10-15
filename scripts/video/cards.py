"""Render the video's title / numbers / end cards as 1920x1080 PNGs (HTML -> Playwright screenshot).
Every number on the numbers card is read from eval/results/*.json, never typed in.
Usage: python scripts/video/cards.py demo/build"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
R = Path("eval/results")
bt = json.loads((R / "backtest_summary.json").read_text())
iv = json.loads((R / "interval_baseline.json").read_text())
ta = json.loads((R / "tie_analysis.json").read_text())
rg = ta["2_3_ranges_and_stocking"]
pt = ta["4_point_forecast"]
S = bt["summary"]
wider = round((iv["naive_ratio_p10_p90"]["relative_width"] / iv["tabpfn_p10_p90"]["relative_width"] - 1) * 100)

CSS = """*{box-sizing:border-box}body{margin:0;width:1920px;height:1080px;background:#fbfaf7;color:#1d1d1b;
font-family:'Noto Sans',sans-serif;display:flex;flex-direction:column;justify-content:center;padding:0 170px}
h1{font-size:92px;margin:0 0 18px;letter-spacing:-1px}h2{font-size:54px;margin:0 0 34px}
p{font-size:40px;line-height:1.4;margin:0 0 18px;color:#444}.k{color:#2f6b4f;font-weight:700}
.tag{display:inline-block;font-size:28px;padding:6px 18px;border-radius:24px;background:#f3ead7;color:#6b4e12;margin-top:26px}
table{border-collapse:collapse;font-size:38px;margin:4px 0 26px}td{padding:10px 26px 10px 0;border-bottom:2px solid #e3e0d8}
td.n{text-align:right;font-variant-numeric:tabular-nums}tr.me td{font-weight:700;color:#2f6b4f}
.small{font-size:28px;color:#666}
table.neutral{font-size:34px;width:100%}table.neutral td{padding:8px 26px 8px 0}h2{margin-bottom:22px}"""


def card(name, body):
    return name, f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}</style></head><body>{body}</body></html>"


def numbers_card():
    """Neutral colours; the better value in each column is bold. Every value comes from tie_analysis.json."""
    t, k = rg["tabpfn_2"], rg["mean_4w_x_k_tuned_on_validation"]
    cols = [  # (label, tabpfn value, rule value, lower_is_better, format)
        ("Inside P10–P90 range<br><span class=small>target 80%</span>", t["coverage_p10_p90"] * 100,
         k["coverage_p10_p90"] * 100, None, "{:.1f}%"),
        ("Range width ÷ sales", t["relative_width"], k["relative_width"], True, "{:.2f}×"),
        ("Leftover units<br><span class=small>stocking to P90</span>", t["stock_to_top"]["leftover_units"] / 1000,
         k["stock_to_top"]["leftover_units"] / 1000, True, "{:.0f}k"),
        ("Units short<br><span class=small>stocking to P90</span>", t["stock_to_top"]["short_units"] / 1000,
         k["stock_to_top"]["short_units"] / 1000, True, "{:.1f}k"),
        ("Middle number<br><span class=small>WAPE</span>", pt["tabpfn_p50_wape"], pt["mean_4w_x_k_val_wape"], True, "{:.3f}"),
        ("Busy-week number<br><span class=small>P90 pinball loss</span>", t["pinball_p90"], k["pinball_p90"], True, "{:.0f}"),
    ]

    def cell(v, other, low, fmt):
        if low is None:  # coverage: closest to 80 wins
            best = abs(v - 80) < abs(other - 80)
        else:
            best = v < other if low else v > other
        txt = fmt.format(v)
        return f"<td class=n>{'<b>' + txt + '</b>' if best else txt}</td>"

    rows = "".join(f"<tr><td>{lab}</td>{cell(a, b, low, f)}{cell(b, a, low, f)}</tr>" for lab, a, b, low, f in cols)
    return ("<h2>12 test weeks × 20 products, run once</h2>"
            "<table class=neutral><tr><td></td><td class=n><b>TabPFN-2</b><br><span class=small>no per-shop factors</span></td>"
            "<td class=n><b>4-week mean × k</b><br><span class=small>k fitted on Jul–Aug</span></td></tr>"
            + rows + "</table><p class=small>Bold = better in that row.</p>")


def row(label, key, me=False):
    return f"<tr class={'me' if me else ''}><td>{label}</td><td class=n>{S[key]['wape']:.3f}</td></tr>"


cards = [
    card("title", "<h1>tidy-predict</h1><p>A weekly restock note you can sell to small online shops.</p>"
         "<p>Messy order export in. Forecast and a plain note out.<br><span class=k>All on one laptop. "
         "No data leaves it.</span></p>"),
    card("numbers", numbers_card()),
    card("end", "<h1>tidy-predict</h1><p>Forecasts: TabPFN-2 &nbsp;·&nbsp; Note: Gemma 4 E2B via llama.cpp<br>"
         "Both open, both on this laptop. MIT-licensed code.</p><p class=k>Built with PriorLabs-TabPFN</p>"
         "<p class=small>Demo data: UCI Online Retail II (real, anonymised orders of a UK online gift shop), CC BY 4.0. "
         "Not a client.<br>github.com/xexpertai/tidy-predict</p>"),
]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    for name, h in cards:
        pg.set_content(h)
        pg.screenshot(path=str(out / f"card-{name}.png"))
        print("card", name)
    b.close()
