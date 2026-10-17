"""Record the animated illustration pages (scripts/video/illustration/story.html) with Playwright.
Usage: .venv/bin/python scripts/video/record_illustration.py <hook|next> <seconds> <out.mp4>
Page is 1564x880 (the stage of the v5 layout). Nothing here is a screenshot of a real product or a real person."""
import subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright

R = Path(__file__).resolve().parents[2]
scene, secs, out = sys.argv[1], float(sys.argv[2]), Path(sys.argv[3])
tmp = Path(tempfile.mkdtemp(prefix="illus-"))
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={"width": 1564, "height": 880}, record_video_dir=str(tmp), record_video_size={"width": 1564, "height": 880})
    t_ctx = time.time()
    pg = c.new_page()
    pg.goto(f"file://{R}/scripts/video/illustration/story.html?s={scene}")
    pg.evaluate("document.fonts.ready")
    t_load = time.time()
    pg.wait_for_timeout(int(secs * 1000))
    c.close(); b.close()
vid = next(tmp.glob("*.webm"))
lead = max(0.0, t_load - t_ctx - 0.05)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{lead:.2f}", "-i", vid, "-t", f"{secs:.2f}", "-vf", "fps=30,format=yuv420p",
                "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(out)], check=True)
print("wrote", out, "lead trimmed", round(lead, 2))
