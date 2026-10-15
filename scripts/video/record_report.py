"""Record the finished report page on its own (1920x1080), with a timeline, for the video.
Usage: python scripts/video/record_report.py runs/<id>/out/report.html demo/raw-report"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

rep, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
tl = {"events": []}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(out),
                        record_video_size={"width": 1920, "height": 1080})
    pg = ctx.new_page()
    t0 = time.time()
    mark = lambda n: tl["events"].append({"t": round(time.time() - t0, 2), "event": n})  # noqa: E731
    pg.goto(rep.as_uri())
    pg.add_style_tag(content="html{zoom:1.45}")
    mark("report")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(out / "rep-top.png"))   # crisp stills of each held view (the screencast is low-bitrate)
    pg.wait_for_timeout(10500)
    # jump between views and hold each one: continuous scrolling tears in the screencast
    table_y = pg.evaluate("document.querySelectorAll('h2')[0].getBoundingClientRect().top + window.scrollY")
    mark("scroll start")
    pg.evaluate(f"window.scrollTo(0,{table_y - 20})")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(out / "rep-table.png"))
    pg.wait_for_timeout(5500)
    mid_y = pg.evaluate("document.querySelectorAll('tr')[12].getBoundingClientRect().top + window.scrollY")
    pg.evaluate(f"window.scrollTo(0,{mid_y - 40})")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(out / "rep-table2.png"))
    pg.wait_for_timeout(5500)
    mark("report scrolled")
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    mark("footer")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(out / "rep-bottom.png"))
    pg.wait_for_timeout(6500)
    mark("end")
    vid = pg.video.path()
    ctx.close()
    b.close()
tl["video"] = Path(vid).name
(out / "timeline.json").write_text(json.dumps(tl, indent=2))
print(json.dumps(tl))
