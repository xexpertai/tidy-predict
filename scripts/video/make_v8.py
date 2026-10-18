"""Build demo/final-v8/tidy-predict-demo-v8.mp4.

Layout (1920x1080): a 1564x880 "stage" (the recorded page, or the animated illustration) on a dark background,
and a dedicated 200 px caption band below it, so captions never cover the page. Zooms are smooth eased
crop-and-scale moves of the real recording (nothing re-drawn). Persona Meera is fictional and labelled.

Narration: --voice-dir DIR uses Harsha's own recordings (DIR/<scene id>.wav|m4a|mp3|flac|ogg; any scene without a file falls
back to Kokoro TTS, voice --voice, default am_michael). Audio ends at -14 LUFS, -1.5 dBTP.

Run (video venv, heavy-job cap):
  cd ~/workspace/dev-hacktoberfest/tidy-predict && flock ~/workspace/.heavy.lock systemd-run --user --scope -q \
    -p MemoryMax=3G -p MemorySwapMax=256M ~/workspace/.video-venv/bin/python scripts/video/make_v8.py [--voice-dir DIR] [--voice NAME] [--no-voice-cache]
Needs demo/build-v8/card-end.png (scripts/video/make_cards_v8.py); recording from demo/raw-v8.
"""
import argparse, json, re, subprocess, textwrap
from pathlib import Path

import numpy as np
import soundfile as sf

R = Path(__file__).resolve().parents[2]
RAW = R / "demo" / "raw-v8"
B = R / "demo" / "build-v8"
OUTDIR = R / "demo" / "final-v8"
story = json.loads((R / "scripts" / "video" / "story_v8.json").read_text())
tl = json.loads((RAW / "timeline.json").read_text())
SRC = RAW / tl["video"]
RAW2 = R / "demo" / "raw-none"   # v6 used a second recording; v8 uses one recording only
tl2 = json.loads((RAW2 / "timeline.json").read_text()) if (RAW2 / "timeline.json").exists() else None
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SR, FPS, GAP, LEAD = 24000, 30, 0.30, 0.12
SW, SH, BAND_BG = 1564, 880, "0x1e2321"
PADX = (1920 - SW) // 2
ap = argparse.ArgumentParser()
ap.add_argument("--voice-dir", type=Path)
ap.add_argument("--voice", default="am_michael")
ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--no-voice-cache", action="store_true")
ap.add_argument("--out", default="tidy-predict-demo-v8.mp4")
args = ap.parse_args()
(B / "vo").mkdir(parents=True, exist_ok=True)
(B / "cap").mkdir(exist_ok=True)
OUTDIR.mkdir(parents=True, exist_ok=True)


def ev(name, tline=None):
    for e in (tline or tl)["events"]:
        if e["event"] == name or e["event"].startswith(name):
            return e["t"]
    raise KeyError(name)


def t_of(x, tline=None):
    m = re.fullmatch(r"(.+?)([+-][\d.]+)?", x.strip())
    return ev(m.group(1), tline) + (float(m.group(2)) if m.group(2) else 0.0)


def run(*a):
    r = subprocess.run([str(x) for x in a], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr[-1500:])


def dur_of(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip())


def tidy(audio, max_pause=0.40, thr_db=-45):
    """Trim edges and cap internal pauses."""
    thr = 10 ** (thr_db / 20) * np.abs(audio).max()
    nz = np.flatnonzero(np.abs(audio) > thr)
    audio = audio[max(0, nz[0] - 240): nz[-1] + 480]
    win = int(0.01 * SR)
    loud = np.array([np.abs(audio[i:i + win]).max() > thr for i in range(0, len(audio), win)])
    keep, r = [], 0
    for i, l in enumerate(loud):
        r = 0 if l else r + 1
        if l or r * 0.01 <= max_pause:
            keep.append(audio[i * win:(i + 1) * win])
    return np.concatenate(keep)


def human_clip(sid):
    if not args.voice_dir:
        return None
    for ext in ("wav", "m4a", "mp3", "flac", "ogg", "aac"):
        p = args.voice_dir / f"{sid}.{ext}"
        if p.exists():
            return p
    return None


def voice():
    pipes, durs = {}, {}
    for sc in story["scenes"]:
        sid = sc["id"]
        wav, key = B / "vo" / f"{sid}.wav", B / "vo" / f"{sid}.key"
        said = sc.get("say", sc["text"])
        h = human_clip(sid)
        sig = f"human:{h.stat().st_mtime_ns}:{h}" if h else f"{args.voice}|{args.speed}|{sc.get("speed", 1.0)}|{said}"
        if not args.no_voice_cache and wav.exists() and key.exists() and key.read_text() == sig:
            durs[sid] = len(sf.read(wav, dtype="float32")[0]) / SR
            continue
        if h:
            tmp = B / "vo" / f"{sid}.raw.wav"
            run("ffmpeg", "-y", "-loglevel", "error", "-i", h, "-ac", "1", "-ar", SR, tmp)
            audio = tidy(sf.read(tmp, dtype="float32")[0])
            tmp.unlink()
        else:
            lc = {"a": "a", "b": "b", "h": "h"}[args.voice[0]]
            if lc not in pipes:
                from kokoro import KPipeline
                pipes[lc] = KPipeline(lang_code=lc, repo_id="hexgrad/Kokoro-82M")
            audio = tidy(np.concatenate([np.asarray(a) for _, _, a in pipes[lc](said, voice=args.voice, speed=sc.get("speed", 1.0) * args.speed)]))
        sf.write(wav, audio, SR, subtype="PCM_16")
        key.write_text(sig)
        durs[sid] = len(audio) / SR
        print(f"voiced {sid}: {durs[sid]:.2f}s ({'human' if h else args.voice})", flush=True)
    return durs


def band_filters(sc, i):
    f = []
    x = 90
    for lab in sc.get("labels", []):
        fill = "0x8a5a12" if "ictional" in lab or "Illustration" in lab else "0x2f6b4f"
        f.append(f"drawtext=fontfile={FONT}:text='{lab.replace(':', chr(92) + ':')}':fontsize=26:fontcolor=white:box=1:boxcolor={fill}:boxborderw=9:x={x}:y=896")
        x += int(len(lab) * 17.5) + 18 + 22
    cap = sc.get("caption")
    if cap:
        for k, line in enumerate(textwrap.wrap(cap, 56)):
            t = line.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")
            f.append(f"drawtext=fontfile={FONT}:text='{t}':fontsize=40:fontcolor=white:x=90:y={952 + k * 50}")
    return f


def ease(a, d):
    p = f"clip((t-{a})/{d},0,1)"
    return f"({p}*{p}*(3-2*{p}))"


def build_scene(i, sc, want):
    out = B / f"scene{i:02d}.mp4"
    if sc["src"].startswith("card:"):
        run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", FPS, "-t", f"{want:.3f}", "-i", B / f"card-{sc['src'][5:]}.png",
            "-vf", "fade=t=in:st=0:d=0.3,format=yuv420p", "-r", FPS, "-c:v", "libx264", "-preset", "medium", "-crf", "17", out)
        return out
    vf = []
    if sc["src"].startswith("illus:"):
        inp = ["-i", B / f"illus-{sc['src'][6:]}.mp4"]
        clip, speed = dur_of(inp[1]), 1.0
        vf.append(f"scale={SW}:{SH}")
    elif sc["src"].startswith("still:"):
        # cursor-free screenshot of the same run (demo/raw-v8), cropped to a 1920x1080 window; optional highlight box
        # (drawn by us, so the scene carries a chip saying so). sc["still_y"] = top of the window in the full-page png.
        png = B / f"still-{sc['id']}.png"
        f = [f"crop=1920:1080:0:{sc.get('still_y', 0)}"]
        for x, y, w, h in sc.get("highlight", []):
            f.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0xffb000@0.28:t=fill")
            f.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0xe08a00@1.0:t=4")
        run("ffmpeg", "-y", "-loglevel", "error", "-i", RAW / sc["src"][6:], "-vf", ",".join(f), "-frames:v", "1", png)
        inp = ["-loop", "1", "-framerate", "30", "-t", f"{want + 0.5:.3f}", "-i", png]
        clip, speed = want + 0.5, 1.0
    else:
        rep = False
        a, b = sc["src"][4:].split("..") if rep else sc["src"].split("..")
        t0, t1 = (t_of(a, tl2), t_of(b, tl2)) if rep else (t_of(a), t_of(b))
        assert t1 > t0, sc["id"]
        clip = t1 - t0
        inp = ["-ss", f"{t0:.3f}", "-t", f"{clip:.3f}", "-i", (RAW2 / tl2["video"]) if rep else SRC]
        speed = sc.get("speed_video") or (max(1.0, clip / want) if sc.get("fit", "freeze") == "speed" else 1.0)
        if speed != 1.0:
            vf.append(f"setpts=PTS/{speed:.4f}")
    play = clip / speed
    if play < want:
        vf.append(f"tpad=stop_mode=clone:stop_duration={want - play + 0.05:.3f}")
    if "zoom" in sc:
        zx, zy, zw, zh = sc["zoom"]
        Z = 1920 / zw
        e = ease(sc.get("zoom_at", 0.4), sc.get("zoom_dur", 1.1))
        zf = f"(1+({Z:.5f}-1)*{e})"
        cx = f"(960+({zx + zw / 2}-960)*{e})"
        cy = f"(540+({zy + zh / 2}-540)*{e})"
        vf.append(f"scale=w='{SW}*{zf}':h='{SH}*{zf}':eval=frame:flags=bicubic")
        vf.append(f"crop={SW}:{SH}:x='max(0,min({cx}*{SW}*{zf}/1920-{SW / 2},{SW}*{zf}-{SW}))':y='max(0,min({cy}*{SH}*{zf}/1080-{SH / 2},{SH}*{zf}-{SH}))'")
    elif not sc["src"].startswith("illus:"):
        vf.append(f"scale={SW}:{SH}:flags=lanczos")
    if not sc["src"].startswith("illus:"):
        # slow continuous push-in so a held page never reads as a dead frame
        k = f"(1+0.03*min(t/{want:.3f},1))"
        vf.append(f"scale=w='{SW}*{k}':h='{SH}*{k}':eval=frame:flags=bicubic")
        vf.append(f"crop={SW}:{SH}:x='(iw-{SW})/2':y='(ih-{SH})/2'")
    if sc.get("fade_in"):
        vf.append("fade=t=in:st=0:d=0.35")
    vf.append(f"pad=1920:1080:{PADX}:0:color={BAND_BG}")
    vf += band_filters(sc, i)
    vf.append("fps=30,format=yuv420p")
    run("ffmpeg", "-y", "-loglevel", "error", *inp, "-vf", ",".join(vf), "-t", f"{want:.3f}", "-an", "-c:v", "libx264",
        "-preset", "medium", "-crf", "17", out)
    sc["_speed"] = speed
    return out


def build():
    durs = voice()
    parts, mix, t = [], [], 0.0
    for i, sc in enumerate(story["scenes"]):
        want = max(durs[sc["id"]] + LEAD + GAP, sc.get("min", 0.0))
        p = build_scene(i, sc, want)
        d = dur_of(p)
        mix.append((B / "vo" / f"{sc['id']}.wav", t + LEAD))
        sc["_start"], sc["_dur"] = round(t, 2), round(d, 2)
        print(f"{sc['id']:>12}: {t:6.2f}s  +{d:5.2f}s  speed {sc.get('_speed', 1):.2f}", flush=True)
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
    sf.write(B / "vo_raw.wav", audio, SR, subtype="PCM_16")
    # gentle compression + limiter so the voice can reach -14 LUFS under the -1.5 dBTP ceiling
    run("ffmpeg", "-y", "-loglevel", "error", "-i", B / "vo_raw.wav", "-af",
        "acompressor=threshold=-24dB:ratio=4:attack=5:release=90:makeup=4dB,alimiter=limit=0.55:level=disabled", B / "vo.wav")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(B / "vo.wav"), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r).group(0))
    out = OUTDIR / args.out
    target = -13.3
    for _ in range(3):  # linear loudnorm undershoots a little; adjust the target until the file measures -14 +-0.25 LUFS
        af = (f"loudnorm=I={target:.2f}:TP=-1.6:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
              f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000")
        run("ffmpeg", "-y", "-loglevel", "error", "-i", B / "video.mp4", "-i", B / "vo.wav", "-af", af, "-c:v", "copy", "-c:a", "aac",
            "-b:a", "160k", "-shortest", "-movflags", "+faststart", out)
        m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out), "-af", "loudnorm=I=-14:TP=-1:print_format=json", "-vn", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        got = float(re.search(r'"input_i" : "([-\d.]+)"', m).group(1))
        tp = float(re.search(r'"input_tp" : "([-\d.]+)"', m).group(1))
        print(f"loudness {got:.2f} LUFS, true peak {tp:.2f} dBTP (target arg {target:.2f})", flush=True)
        if abs(got + 14) <= 0.15 and tp <= -1.1:
            break
        target += -14 - got
    (B / "scenes.json").write_text(json.dumps(story["scenes"], indent=2))
    print(f"wrote {out} ({dur_of(out):.1f} s)")


if __name__ == "__main__":
    build()
