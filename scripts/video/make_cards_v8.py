"""Cards for video v8 -> demo/build-v8/card-end.png (1920x1080). No people are drawn.
Run: cd ~/workspace/dev-hacktoberfest/tidy-predict && .venv/bin/python scripts/video/make_cards_v8.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

R = Path(__file__).resolve().parents[2]
CSS = """*{box-sizing:border-box}body{margin:0;width:1920px;height:1080px;background:#fbfaf7;color:#1d1d1b;font-family:'Noto Sans',sans-serif;
display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 160px;position:relative}
h1{font-size:96px;margin:0 0 14px;letter-spacing:-1px;line-height:1.1}h2{font-size:84px;margin:0 0 26px;line-height:1.15}
p{font-size:44px;margin:0 0 18px;color:#444}
.u{font-size:50px;font-weight:700;color:#2f6b4f;background:#eaf3ee;padding:14px 36px;border-radius:14px;margin:18px 0 34px}
.s{font-size:29px;color:#555;line-height:1.5;margin:0 0 6px}.b{font-size:50px;font-weight:700;margin-top:26px}
.chips{position:absolute;left:90px;bottom:60px;display:flex;gap:18px}.chip{font-size:28px;font-weight:700;color:#fff;background:#8a5a12;padding:10px 22px;border-radius:8px}
.chip.g{background:#2f6b4f}
.row{display:flex;gap:90px;margin-top:40px;align-items:flex-end}
.shelf{width:520px;height:250px;border-bottom:10px solid #6b5a43;display:flex;align-items:flex-end;justify-content:center;gap:16px;position:relative}
.box{background:#d9b779;border:4px solid #8d6a2e;width:120px;height:90px;border-radius:6px}
.tag{position:absolute;top:-40px;font-size:30px;font-weight:700;color:#fff;padding:8px 18px;border-radius:8px}
.cap{font-size:32px;color:#555;margin-top:16px}"""
end = """<h1>tidy-predict</h1><p>Messy order export in. Checked restock note out. One laptop, two open models.</p>
<div class=u>github.com/xexpertai/tidy-predict</div>
<div class=s><b>Built with PriorLabs-TabPFN</b> · Forecasts: TabPFN-2 · Note: Gemma 4 E2B via llama.cpp</div>
<div class=s>Fictional shop. Demo data: a public UK gift-shop export (UCI Online Retail II, CC BY 4.0), replayed as of 27 Nov 2011.</div>
<div class=s>Not a client. Nobody has used this yet.</div>
<div class=s><b>Narration: AI voice generated from my own voice sample</b></div><div class=b>by Harsha Shinde</div>"""
out = R / "demo" / "build-v8"; out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    for name, body in (("end", end),):
        pg.set_content(f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}</style></head><body>{body}</body></html>")
        pg.screenshot(path=str(out / f"card-{name}.png"))
    b.close()
print("wrote cards in", out)
