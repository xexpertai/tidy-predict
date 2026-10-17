"""Record the finished report page (with the product-side 'sold above range' colour) as the second source of video v5.
Usage: .venv/bin/python scripts/video/record_report_v5.py demo/build-v5/rep/report.html demo/raw-report-v5
Timeline events: report, table, row: Rabbit night light, cleaned, footer, end. Same page content as the recorded run
(report.html re-rendered from the run's run.json, no model run again)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

rep, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
tl = {"events": []}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(out), record_video_size={"width": 1920, "height": 1080})
    t0 = time.time()   # events are relative to page creation = first video frame
    pg = ctx.new_page()
    pg.goto(rep.as_uri())
    pg.add_style_tag(content="html{zoom:1.45} main{max-width:1000px !important;padding-bottom:620px !important}")
    pg.wait_for_timeout(300)
    mark = lambda n: tl["events"].append({"t": round(time.time() - t0, 2), "event": n})  # noqa: E731
    top = lambda sel, off=0: pg.evaluate(f"document.querySelector({sel!r}).getBoundingClientRect().top + window.scrollY - {off}")  # noqa: E731
    mark("report"); pg.wait_for_timeout(7000); pg.screenshot(path=str(out / "top.png"))
    pg.evaluate("window.scrollTo({top:%d,behavior:'smooth'})" % (top("table") - 30)); pg.wait_for_timeout(900)
    mark("table"); pg.wait_for_timeout(6500)
    y = pg.evaluate("[...document.querySelectorAll('tr')].find(r=>r.textContent.includes('Rabbit night')).getBoundingClientRect().top + window.scrollY")
    pg.evaluate("window.scrollTo({top:%d,behavior:'smooth'})" % (y - 330)); pg.wait_for_timeout(900)
    mark("row: Rabbit night light"); pg.wait_for_timeout(9500); pg.screenshot(path=str(out / "miss.png"))
    h2 = pg.evaluate("[...document.querySelectorAll('h2')].find(h=>h.textContent.includes('cleaned')).getBoundingClientRect().top + window.scrollY")
    pg.evaluate("window.scrollTo({top:%d,behavior:'smooth'})" % (h2 - 40)); pg.wait_for_timeout(900)
    mark("cleaned"); pg.wait_for_timeout(7000); pg.screenshot(path=str(out / "cleaned.png"))
    pg.evaluate("window.scrollTo({top:document.querySelector('footer').getBoundingClientRect().top+window.scrollY-420,behavior:'smooth'})"); pg.wait_for_timeout(700)
    mark("footer"); pg.wait_for_timeout(3500); mark("end")
    vid = pg.video.path(); ctx.close(); b.close()
tl["video"] = Path(vid).name
(out / "timeline.json").write_text(json.dumps(tl, indent=2)); print(json.dumps(tl))
