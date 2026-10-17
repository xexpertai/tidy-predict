"""End card for video v5 -> demo/build-v5/card-end.png (1920x1080). Run: .venv/bin/python scripts/video/make_card_v5.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

R = Path(__file__).resolve().parents[2]
CSS = """*{box-sizing:border-box}body{margin:0;width:1920px;height:1080px;background:#fbfaf7;color:#1d1d1b;font-family:'Noto Sans',sans-serif;
display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 200px}
h1{font-size:104px;margin:0 0 14px;letter-spacing:-1px}p{font-size:42px;margin:0 0 18px;color:#444}
.u{font-size:50px;font-weight:700;color:#2f6b4f;background:#eaf3ee;padding:14px 36px;border-radius:14px;margin:18px 0 34px}
.s{font-size:29px;color:#555;line-height:1.5;margin:0 0 6px}.b{font-size:50px;font-weight:700;margin-top:26px}"""
body = """<h1>tidy-predict</h1><p>Messy order export in. Checked restock note out. One laptop, two open models.</p>
<div class=u>github.com/xexpertai/tidy-predict</div>
<div class=s><b>Built with PriorLabs-TabPFN</b> · Forecasts: TabPFN-2 · Note: Gemma 4 E2B via llama.cpp</div>
<div class=s>Persona is fictional; demo data is public (UCI Online Retail II, CC BY 4.0), headers renamed to show the mapping.</div>
<div class=s>Not a client. No real customer results are shown.</div><div class=s><b>Narration: AI voice generated from my own voice sample</b></div><div class=b>by Harsha Shinde</div>"""
out = R / "demo" / "build-v5"; out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.set_content(f"<!doctype html><html><head><meta charset=utf-8><style>{CSS}</style></head><body>{body}</body></html>")
    pg.screenshot(path=str(out / "card-end.png")); b.close()
print("wrote", out / "card-end.png")
