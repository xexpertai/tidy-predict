"""Draw docs/media/range-vs-sold.svg (+ .png) from a run directory: four products, forecast range vs what sold.
Usage: python scripts/make_range_chart.py <run out dir> docs/media/range-vs-sold
Every number comes from run.json (facts, actuals). Each row has its own scale; the numbers are printed."""
import html, json, sys
from pathlib import Path

out_dir, dest = Path(sys.argv[1]), Path(sys.argv[2])
run = json.loads((out_dir / "run.json").read_text())
items = {i["product"]: i for i in run["facts"]["items"]}
act = run["actuals"]
ROWS = ["Rabbit night light", "Small popcorn holder", "Red harmonica in box", "Set of 60 pantry design cake cases"]
W, H, X0, X1 = 1000, 1390, 40, 960
INK, MUTED, BAND, ABOVE, IN = "#1d1d1b", "#5c5a54", "#cfe3d8", "#b85c00", "#2f6b4f"
e = html.escape
parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" role="img" font-family="system-ui,Segoe UI,Roboto,sans-serif" '
         f'aria-label="For four products, the forecast range for the week of 28 Nov 2011, the 4-week average, and what really sold">',
         f'<rect width="{W}" height="{H}" fill="#fbfaf7"/>',
         f'<text x="{X0}" y="46" font-size="30" font-weight="700" fill="{INK}">Forecast range vs what really sold, week of 28 Nov 2011</text>',
         f'<text x="{X0}" y="80" font-size="22" fill="{MUTED}">Demo data. Each row has its own scale.</text>']
y = 150
for name in ROWS:
    d, a = items[name], act[name]
    top = max(d["stock_for_busy_week"], a, d["avg_last_4_weeks"]) * 1.06
    px = lambda v: X0 + (X1 - X0) * v / top
    above = a > d["stock_for_busy_week"]
    col = ABOVE if above else IN
    tag = "sold ABOVE the range" if above else "sold inside the range"
    parts.append(f'<text x="{X0}" y="{y}" font-size="26" font-weight="700" fill="{INK}">{e(name)}</text>')
    parts.append(f'<text x="{X1}" y="{y}" font-size="24" font-weight="700" text-anchor="end" fill="{col}">{tag}: {int(a):,}</text>')
    by = y + 40
    parts.append(f'<rect x="{X0}" y="{by + 12}" width="{X1 - X0}" height="2" fill="#d9d6cc"/>')
    parts.append(f'<rect x="{px(d["low_units"]):.1f}" y="{by}" width="{px(d["stock_for_busy_week"]) - px(d["low_units"]):.1f}" height="26" rx="4" fill="{BAND}"/>')
    parts.append(f'<rect x="{px(d["expected_units"]) - 2:.1f}" y="{by - 6}" width="4" height="38" fill="{INK}"/>')
    ax = px(d["avg_last_4_weeks"])
    parts.append(f'<path d="M{ax:.1f} {by + 31} l-8 12 h16 z" fill="{MUTED}"/>')
    parts.append(f'<circle cx="{px(a):.1f}" cy="{by + 13}" r="14" fill="{col}" stroke="#fff" stroke-width="3"/>')
    parts.append(f'<text x="{X0}" y="{by + 80}" font-size="24" fill="{MUTED}">range {d["low_units"]:,} to {d["stock_for_busy_week"]:,}, expected {d["expected_units"]:,}</text>')
    parts.append(f'<text x="{X0}" y="{by + 110}" font-size="24" fill="{MUTED}">4-week average {d["avg_last_4_weeks"]:,}; busiest of last 4 weeks {d["busiest_of_last_4_weeks"]:,}</text>')
    parts.append(f'<text x="{X0}" y="{by + 140}" font-size="24" fill="{MUTED}">chance of selling out at the busiest-week stock: {d["sell_out_chance_pct"]}%</text>')
    if d.get("check_by_hand"):
        parts.append(f'<text x="{X0}" y="{by + 170}" font-size="24" font-weight="700" fill="{ABOVE}">Flagged in the note: wide range, check by hand</text>')
    y += 275
ly = y - 10
parts.append(f'<rect x="{X0}" y="{ly}" width="30" height="16" rx="3" fill="{BAND}"/><text x="{X0 + 42}" y="{ly + 16}" font-size="24" fill="{MUTED}">likely range (P10 to P90)</text>')
parts.append(f'<rect x="{X0 + 400}" y="{ly - 4}" width="4" height="24" fill="{INK}"/><text x="{X0 + 416}" y="{ly + 16}" font-size="24" fill="{MUTED}">expected</text>')
parts.append(f'<path d="M{X0 + 600} {ly} l-8 14 h16 z" fill="{MUTED}"/><text x="{X0 + 620}" y="{ly + 16}" font-size="24" fill="{MUTED}">4-week average</text>')
parts.append(f'<circle cx="{X0 + 20}" cy="{ly + 52}" r="10" fill="{ABOVE}"/><text x="{X0 + 42}" y="{ly + 60}" font-size="24" fill="{MUTED}">what really sold (orange: above the range, green: inside)</text>')
parts.append("</svg>")
svg = "\n".join(parts)
dest.parent.mkdir(parents=True, exist_ok=True)
Path(str(dest) + ".svg").write_text(svg)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
    pg.set_content(f"<body style='margin:0'>{svg}</body>"); pg.screenshot(path=str(dest) + ".png"); b.close()
print("wrote", dest)
