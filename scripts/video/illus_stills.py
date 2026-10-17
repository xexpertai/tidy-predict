"""Render illustration stills at given times (deterministic, ?t=). Usage: illus_stills.py <hook|next> <outdir> t1 t2 ..."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
R = Path(__file__).resolve().parents[2]
mode, out, ts = sys.argv[1], Path(sys.argv[2]), sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1564, "height": 880})
    pg.on("pageerror", lambda e: print("ERR", e))
    for t in ts:
        pg.goto(f"file://{R}/scripts/video/illustration/story.html?s={mode}&t={t}"); pg.wait_for_timeout(250)
        pg.screenshot(path=str(out / f"{mode}-{float(t):05.2f}.png"))
