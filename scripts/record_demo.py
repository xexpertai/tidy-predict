"""Record the demo: a real run of the local web page (real TabPFN-2, real local Gemma), 1920x1080.

Needs: the model server (scripts/start-model.sh) and `tidy-predict serve` running, and Playwright
(`uv pip install -e ".[demo]"`). Nothing is faked: the page talks to the real app. The recording is
raw; demo/raw/timeline.json says when each thing happened so the editor can cut the waits and label
the cuts.

Usage: python scripts/record_demo.py data/raw/online_retail_II.csv 2011-11-27 demo/raw
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

src, as_of, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
url = sys.argv[4] if len(sys.argv) > 4 else "http://127.0.0.1:8765"
label = ("Demo data: UCI Online Retail II (real, anonymised orders of a UK online gift shop, CC BY 4.0), "
         "replayed as of 27 Nov 2011")
out.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
ZOOM = "html{zoom:1.45}"  # the page is designed for laptops; make it readable in a 1080p video
tl: dict = {"events": []}


def mark(name: str) -> None:
    tl["events"].append({"t": round(time.time() - t0, 2), "event": name})
    print(f"{tl['events'][-1]['t']:7.2f}s {name}", flush=True)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                        record_video_dir=str(out), record_video_size={"width": W, "height": H})
    pg = ctx.new_page()
    t0 = time.time()
    pg.goto(url)
    pg.add_style_tag(content=ZOOM)
    mark("home")
    pg.wait_for_timeout(2500)
    pg.set_input_files("#f", str(src))
    mark("file chosen")
    pg.wait_for_timeout(1200)
    pg.fill("#asof", as_of)
    pg.fill("#lab", label)
    mark("form filled")
    pg.wait_for_timeout(1500)
    pg.click("button")
    mark("submitted")
    pg.wait_for_url("**/job/**")
    pg.add_style_tag(content=ZOOM)
    seen = 0
    while True:
        st = pg.evaluate("fetch(location.pathname+'/status').then(r=>r.json())")
        for t, m in st["log"][seen:]:
            mark(f"log: {m}")
        seen = len(st["log"])
        if st["state"] != "running":
            mark(f"state: {st['state']}")
            break
        pg.wait_for_timeout(500)
    if st["state"] != "done":
        sys.exit(f"run failed: {st.get('error')}")
    pg.wait_for_selector("iframe")
    pg.wait_for_timeout(2500)
    jid = pg.url.rstrip("/").rsplit("/", 1)[1]
    tl["job"] = jid
    # open the report itself, larger, and scroll through it slowly
    pg.goto(f"{url}/job/{jid}/report.html")
    pg.add_style_tag(content=ZOOM)
    mark("report")
    pg.wait_for_timeout(9000)
    for y in range(0, 1400, 8):
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(30)
    mark("report scrolled")
    pg.wait_for_timeout(6000)
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    mark("footer")
    pg.wait_for_timeout(5000)
    pg.screenshot(path=str(out / "report-bottom.png"))
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(out / "report-top.png"), full_page=True)
    mark("end")
    vid = pg.video.path()
    ctx.close()
    b.close()
tl["video"] = Path(vid).name
(out / "timeline.json").write_text(json.dumps(tl, indent=2))
print("video:", vid)
