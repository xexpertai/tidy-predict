"""Build demo/tidy-predict-demo.mp4 (v4) from the raw Playwright recording in demo/raw-v4.

Everything on screen is the recorded page (one real run); the only non-recorded picture is the end card.
Scenes (scripts/video/story_v4.json) cut the recording by the events in timeline.json, may speed a
wait up (labelled on screen), crop in on a region (plain scaling, nothing re-drawn) and carry a caption.
Narration: Kokoro af_heart, voiced locally; each scene lasts as long as its line (clips are frozen on
their last frame or sped up to fit, never re-ordered). Audio is normalised to -14 LUFS, -1.5 dBTP.

Run with the video venv: ~/workspace/.video-venv/bin/python scripts/video/make_v4.py [--no-voice-cache]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

R = Path(__file__).resolve().parents[2]
RAW = R / "demo" / "raw-v4e"
B = R / "demo" / "build-v4"
OUT = R / "demo" / "final-v4" / "tidy-predict-demo-v4.mp4"
story = json.loads((R / "scripts" / "video" / "story_v4.json").read_text())
tl = json.loads((RAW / "timeline.json").read_text())
SRC = RAW / tl["video"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SR, FPS, GAP, LEAD = 24000, 30, 0.30, 0.12
(B / "vo").mkdir(parents=True, exist_ok=True)


def ev(name: str) -> float:
    for e in tl["events"]:
        if e["event"] == name or e["event"].startswith(name):
            return e["t"]
    raise KeyError(name)


def t_of(x: str) -> float:
    m = re.fullmatch(r"(.+?)([+-][\d.]+)?", x.strip())
    return ev(m.group(1)) + (float(m.group(2)) if m.group(2) else 0.0)


def run(*a):
    subprocess.run([str(x) for x in a], check=True, capture_output=True)


def dur_of(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def cap_pauses(audio, max_pause=0.40, thr_db=-45):
    thr = 10 ** (thr_db / 20) * np.abs(audio).max()
    win = int(0.01 * SR)
    loud = np.array([np.abs(audio[i:i + win]).max() > thr for i in range(0, len(audio), win)])
    keep, run_ = [], 0
    for i, l in enumerate(loud):
        run_ = 0 if l else run_ + 1
        if l or run_ * 0.01 <= max_pause:
            keep.append(audio[i * win:(i + 1) * win])
    return np.concatenate(keep)


def voice(use_cache=True):
    pipe, durs = None, {}
    for sc in story["scenes"]:
        wav, key = B / "vo" / f"{sc['id']}.wav", B / "vo" / f"{sc['id']}.txt"
        said = sc.get("say", sc["text"])
        if use_cache and wav.exists() and key.exists() and key.read_text() == said:
            durs[sc["id"]] = len(sf.read(wav, dtype="float32")[0]) / SR
            continue
        if pipe is None:
            from kokoro import KPipeline
            pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        audio = np.concatenate([np.asarray(a) for _, _, a in pipe(said, voice="af_heart", speed=sc.get("speed", 1.0))])
        thr = 10 ** (-45 / 20) * np.abs(audio).max()
        nz = np.flatnonzero(np.abs(audio) > thr)
        audio = cap_pauses(audio[max(0, nz[0] - 240): nz[-1] + 480])
        sf.write(wav, audio, SR, subtype="PCM_16")
        key.write_text(said)
        durs[sc["id"]] = len(audio) / SR
        print(f"voiced {sc['id']}: {durs[sc['id']]:.2f}s", flush=True)
    return durs


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\\\\\'").replace("%", "\\%")


def caption_filter(sc: dict) -> str:
    f = []
    cap = sc.get("caption")
    if cap:
        f.append(f"drawtext=fontfile={FONT}:text='{esc(cap)}':fontsize=38:fontcolor=white:box=1:boxcolor=0x1e2321@0.86:"
                 f"boxborderw=18:x=64:y=h-th-64")
    lab = sc.get("label")
    if lab:
        f.append(f"drawtext=fontfile={FONT_R}:text='{esc(lab)}':fontsize=30:fontcolor=white:box=1:boxcolor=0x2f6b4f@0.92:"
                 f"boxborderw=14:x=w-tw-64:y=64")
    return ",".join(f)


def build_scene(i: int, sc: dict, want: float) -> Path:
    """Cut, crop, speed and pad one scene to exactly `want` seconds (30 fps, no audio)."""
    out = B / f"scene{i:02d}.mp4"
    if sc["src"] == "card:end":
        run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", FPS, "-t", f"{want:.3f}", "-i", B / "card-end.png",
            "-vf", f"fade=t=in:st=0:d=0.3,format=yuv420p", "-r", FPS, "-c:v", "libx264", "-preset", "medium", "-crf", "17", out)
        return out
    a, b = sc["src"].split("..")
    t0, t1 = t_of(a), t_of(b)
    assert t1 > t0, sc["id"]
    clip = t1 - t0
    vf = []
    if "crop" in sc:  # x,y,w,h in the 1920x1080 frame (16:9), scaled back up: a plain zoom, nothing re-drawn
        x, y, w, h = sc["crop"]
        vf.append(f"crop={w}:{h}:{x}:{y},scale=1920:1080:flags=lanczos")
    speed = sc.get("speed_video")
    if speed is None:
        speed = max(1.0, clip / want) if sc.get("fit", "freeze") == "speed" else 1.0
    if speed != 1.0:
        vf.append(f"setpts=PTS/{speed:.4f}")
    play = clip / speed
    if play < want:
        vf.append(f"tpad=stop_mode=clone:stop_duration={want - play + 0.05:.3f}")
    cf = caption_filter(sc)
    if cf:
        vf.append(cf)
    if sc.get("fade_in"):
        vf.insert(0, "fade=t=in:st=0:d=0.35")
    vf.append("fps=30,format=yuv420p")
    run("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-i", SRC, "-t", f"{clip:.3f}", "-vf", ",".join(vf),
        "-t", f"{want:.3f}", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17", out)
    sc["_speed"] = speed
    return out


def build(use_cache=True):
    durs = voice(use_cache)
    parts, mix, t = [], [], 0.0
    for i, sc in enumerate(story["scenes"]):
        want = max(durs[sc["id"]] + LEAD + GAP, sc.get("min", 0.0))
        p = build_scene(i, sc, want)
        d = dur_of(p)
        mix.append((B / "vo" / f"{sc['id']}.wav", t + LEAD))
        sc["_start"], sc["_dur"] = round(t, 2), round(d, 2)
        print(f"{sc['id']:>10}: {t:6.2f}s  +{d:5.2f}s  speed {sc.get('_speed', 1):.2f}", flush=True)
        t += d
        parts.append(p)
    (B / "concat.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    run("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", B / "concat.txt", "-c", "copy", B / "video.mp4")
    total = dur_of(B / "video.mp4")
    audio = np.zeros(int((total + 1) * SR), dtype="float32")
    for wav, at in mix:
        a, _ = sf.read(wav, dtype="float32")
        s = int(at * SR)
        audio[s:s + len(a)] += a
    audio = audio[: int(total * SR)]
    sf.write(B / "vo.wav", audio, SR, subtype="PCM_16")
    j = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(B / "vo.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr).group(0))
    af = (f"loudnorm=I=-13.3:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true:print_format=summary,aresample=48000")
    run("ffmpeg", "-y", "-loglevel", "error", "-i", B / "video.mp4", "-i", B / "vo.wav", "-af", af, "-c:v", "copy", "-c:a", "aac",
        "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT)
    (B / "scenes.json").write_text(json.dumps(story["scenes"], indent=2))
    print(f"wrote {OUT} ({dur_of(OUT):.1f} s)")


if __name__ == "__main__":
    build(use_cache="--no-voice-cache" not in sys.argv)
