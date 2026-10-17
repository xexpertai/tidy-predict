"""Record the demo: a real run of the local web page (real TabPFN-2, real local Gemma), 1920x1080.

Needs: the model server (scripts/start-model.sh) and `tidy-predict serve` running, and Playwright
(`uv pip install -e ".[demo]"`). Nothing is faked: the page talks to the real app, the cursor you see is
the recorder's own pointer (drawn on the page, since headless Chromium has none), and the file goes in
through the page's own file chooser. The recording is raw; <out>/timeline.json says when each thing
happened so the editor can cut the waits and label the cuts.

Usage: python scripts/record_demo.py data/raw/dukaan_orders.csv 2011-11-27 demo/raw [url]
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

src, as_of, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
url = sys.argv[4] if len(sys.argv) > 4 else "http://127.0.0.1:8765"
label = "Demo data: UCI Online Retail II, a UK gift shop (public, CC BY 4.0), replayed as of 27 Nov 2011"
out.mkdir(parents=True, exist_ok=True)
W, H, Z = 1920, 1080, 1.5
# The page is designed for laptops; zoom it for a 1080p video, and draw a pointer + click rings.
INIT = """
(() => {
  const z = %s;
  const css = `html{zoom:${z}}
  #tp-cur{position:fixed;left:0;top:0;width:26px;height:26px;pointer-events:none;z-index:2147483647;
    transform:translate(-3px,-2px);filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))}
  .tp-ring{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border:3px solid #2f6b4f;border-radius:50%%;
    pointer-events:none;z-index:2147483646;animation:tp-r .45s ease-out forwards}
  @keyframes tp-r{from{transform:scale(.25);opacity:.9}to{transform:scale(1.1);opacity:0}}`;
  const add = () => {
    if (document.getElementById('tp-cur')) return;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const c = document.createElement('div'); c.id = 'tp-cur';
    c.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M5 3l14 9-6.2 1.2L16 20l-2.6 1.2-3.2-6.8L5 19z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    c.style.left = ((window.__tpx || -100) / z) + 'px'; c.style.top = ((window.__tpy || -100) / z) + 'px';
    document.body.appendChild(c);
  };
  document.addEventListener('mousemove', e => { window.__tpx = e.clientX; window.__tpy = e.clientY;
    const c = document.getElementById('tp-cur'); if (c) { c.style.left = (e.clientX / z) + 'px'; c.style.top = (e.clientY / z) + 'px'; } }, true);
  document.addEventListener('mousedown', e => { const r = document.createElement('div'); r.className = 'tp-ring';
    r.style.left = (e.clientX / z) + 'px'; r.style.top = (e.clientY / z) + 'px'; document.body.appendChild(r); setTimeout(() => r.remove(), 500); }, true);
  if (document.readyState !== 'loading') add(); else document.addEventListener('DOMContentLoaded', add);
})();
""" % Z
tl: dict = {"events": []}


def mark(name: str) -> None:
    tl["events"].append({"t": round(time.time() - t0, 2), "event": name})
    print(f"{tl['events'][-1]['t']:7.2f}s {name}", flush=True)


def glide(pg, x, y, steps=28):
    """Move the pointer like a hand would: eased, not teleported. x, y in viewport px (what bounding_box gives)."""
    cx, cy = pg.evaluate("[window.__tpx||0, window.__tpy||0]")
    for i in range(1, steps + 1):
        k = i / steps
        k = k * k * (3 - 2 * k)  # smoothstep
        pg.mouse.move(cx + (x - cx) * k, cy + (y - cy) * k)
        pg.wait_for_timeout(14)


def centre(pg, sel, dx=0, dy=0):
    b = pg.locator(sel).first.bounding_box()
    return b["x"] + b["width"] / 2 + dx, b["y"] + b["height"] / 2 + dy


def click(pg, sel, dx=0, dy=0):
    pg.locator(sel).first.scroll_into_view_if_needed()
    pg.wait_for_timeout(500)
    x, y = centre(pg, sel, dx, dy)
    glide(pg, x, y)
    pg.wait_for_timeout(250)
    pg.mouse.down()
    pg.wait_for_timeout(90)
    pg.mouse.up()


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, locale="en-GB",
                        record_video_dir=str(out), record_video_size={"width": W, "height": H})
    ctx.add_init_script(INIT)
    pg = ctx.new_page()
    t0 = time.time()
    pg.goto(url)
    pg.mouse.move(1500, 700)
    mark("home")
    pg.wait_for_timeout(1800)
    # pick the file through the page's own chooser
    with pg.expect_file_chooser() as fc:
        click(pg, "#drop u")
    fc.value.set_files(str(src))
    mark("file chosen")
    pg.wait_for_selector("#prev table")
    glide(pg, *centre(pg, "#prev table", dy=-10))
    mark("preview shown")
    pg.wait_for_timeout(3200)
    pg.screenshot(path=str(out / "home-preview.png"))
    click(pg, "#asof")
    pg.keyboard.type(as_of, delay=70)
    mark("date typed")
    pg.wait_for_timeout(600)
    click(pg, "#lab")
    pg.keyboard.press("Control+A")
    pg.keyboard.type(label, delay=22)
    mark("label typed")
    pg.wait_for_timeout(700)
    click(pg, "button")
    mark("submitted")
    pg.wait_for_url("**/job/**", timeout=240000)
    pg.wait_for_selector("#log")
    glide(pg, 1180, 640, steps=20)
    seen = 0
    while True:
        st = pg.evaluate("fetch(location.pathname+'/status').then(r=>r.json())")
        for t, m in st["log"][seen:]:
            mark(f"log: {m}")
        seen = len(st["log"])
        if st["state"] != "running":
            mark(f"state: {st['state']}")
            break
        pg.wait_for_timeout(400)
    if st["state"] != "done":
        sys.exit(f"run failed: {st.get('error')}")
    pg.wait_for_timeout(1200)
    pg.screenshot(path=str(out / "job-log.png"))
    pg.wait_for_selector("iframe")
    pg.wait_for_timeout(1500)
    glide(pg, *centre(pg, ".links a.main"))
    pg.wait_for_timeout(600)
    for y in range(0, 520, 10):
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(16)
    mark("result scrolled")
    pg.wait_for_timeout(2500)
    jid = pg.url.rstrip("/").rsplit("/", 1)[1]
    tl["job"] = jid
    # the report itself, larger
    pg.goto(f"{url}/job/{jid}/report.html")
    pg.mouse.move(1700, 900)
    mark("report")
    pg.wait_for_timeout(1000)
    glide(pg, *centre(pg, ".note", dx=-120, dy=24))
    pg.wait_for_timeout(5000)
    pg.screenshot(path=str(out / "report-top.png"))
    rows = pg.locator("table").first.locator("tr")
    for y in range(0, 300, 8):
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(22)
    mark("table")
    pg.wait_for_timeout(1500)
    # point at the rows the note names, then the rabbit night light
    for name in ("Red harmonica", "Rabbit night light"):
        row = pg.locator("tr", has_text=name).first
        bb = row.bounding_box()
        glide(pg, bb["x"] + 60, bb["y"] + bb["height"] / 2)
        mark(f"row: {name}")
        pg.wait_for_timeout(2200)
        cells = row.locator("td")
        glide(pg, *(lambda c: (c["x"] + c["width"] - 30, c["y"] + c["height"] / 2))(cells.nth(cells.count() - 1).bounding_box()))
        pg.wait_for_timeout(1800)
    pg.screenshot(path=str(out / "report-table.png"))
    top = pg.evaluate("window.scrollY")
    for y in range(int(top), int(top) + 760, 10):
        pg.evaluate(f"window.scrollTo(0,{y})")
        pg.wait_for_timeout(16)
    mark("cleaned")
    pg.wait_for_timeout(2500)
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    mark("footer")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=str(out / "report-bottom.png"))
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(400)
    pg.screenshot(path=str(out / "report-full.png"), full_page=True)
    mark("end")
    vid = pg.video.path()
    ctx.close()
    b.close()
tl["video"] = Path(vid).name
(out / "timeline.json").write_text(json.dumps(tl, indent=2))
print("video:", vid)
