"""GIFs and zoomed screenshots for the DEV post, from the same raw recording and screenshots as the video.

Usage: python3 scripts/video/make_media.py <out dir>
GIFs: 900 px wide, 15 fps, palette per clip, each < 8 MB. Screenshots: crops of the Playwright PNGs at 1x (no upscaling).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
RAW = R / "demo" / "raw-v4e"
tl = json.loads((RAW / "timeline.json").read_text())
SRC = RAW / tl["video"]
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def ev(name):
    for e in tl["events"]:
        if e["event"] == name or e["event"].startswith(name):
            return e["t"]
    raise KeyError(name)


def t_of(x):
    m = re.fullmatch(r"(.+?)([+-][\d.]+)?", x.strip())
    return ev(m.group(1)) + (float(m.group(2)) if m.group(2) else 0.0)


def esc(s):
    return s.replace(":", "\\:").replace("'", "\\\\\\'")


def gif(name, segments, width=900, fps=15):
    """segments: list of (start, end, speed, label|None, crop|None). Concatenated, then one palette for the whole GIF."""
    parts = []
    for i, (a, b, speed, label, crop) in enumerate(segments):
        t0, t1 = t_of(a), t_of(b)
        vf = []
        if crop:
            x, y, w, h = crop
            vf.append(f"crop={w}:{h}:{x}:{y}")
        vf.append(f"scale={width}:-2:flags=lanczos")
        if speed != 1:
            vf.append(f"setpts=PTS/{speed}")
        if label:
            vf.append(f"drawtext=fontfile={FONT}:text='{esc(label)}':fontsize=22:fontcolor=white:box=1:boxcolor=0x2f6b4f@0.92:boxborderw=8:x=w-tw-20:y=20")
        vf.append(f"fps={fps},format=yuv420p")
        p = OUT / f"_{name}_{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", SRC, "-vf", ",".join(vf),
                        "-an", "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(p)], check=True)
        parts.append(p)
    lst = OUT / f"_{name}.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    mp4 = OUT / f"_{name}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(mp4)], check=True)
    g = OUT / f"{name}.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-filter_complex",
                    f"[0:v]split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                    str(g)], check=True)
    for p in ([] if __import__("os").environ.get("KEEP") else parts + [lst, mp4]):
        p.unlink()
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(g)], capture_output=True, text=True).stdout)
    print(f"{g.name}: {d:.1f} s, {g.stat().st_size / 1e6:.2f} MB")


def shot(name, src, crop):
    x, y, w, h = crop
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(RAW / src), "-vf", f"crop={w}:{h}:{x}:{y}", str(OUT / f"{name}.png")], check=True)
    print(f"{name}.png: {w}x{h}")


if __name__ == "__main__":
    spec = json.loads((R / "scripts" / "video" / "media_v4.json").read_text())
    for g in spec["gifs"]:
        gif(g["name"], [(s["a"], s["b"], s.get("speed", 1), s.get("label"), s.get("crop")) for s in g["segments"]])
    for s in spec["shots"]:
        shot(s["name"], s["src"], s["crop"])
