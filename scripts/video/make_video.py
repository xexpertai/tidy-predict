"""Build demo/tidy-predict-demo.mp4 from the raw recording, the cards and a Kokoro voiceover.

- Scenes come from demo/raw/timeline.json (real event times in the real recording).
- Each scene lasts as long as its narration (+ a short breath). Recording segments that are longer get sped up,
  and the speed-up is labelled on screen with the real duration. Shorter ones hold their last frame.
- The narration (scripts/video/story.json) is voiced locally with Kokoro (voice af_heart), then the mix is
  normalised to -14 LUFS with a true peak at or below -1.5 dBTP.

Run with the video venv (it has kokoro): ~/workspace/.video-venv/bin/python scripts/video/make_video.py
"""
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
RAW, B, OUT = ROOT / "demo/raw", ROOT / "demo/build", ROOT / "demo/tidy-predict-demo.mp4"
FONT = "/usr/share/fonts/truetype/noto/NotoSans-SemiBold.ttf"
SR = 24000
GAP = 0.35  # breath between scenes (s); must stay well under the 0.6 s silence limit
story = json.loads((Path(__file__).with_name("story.json")).read_text())
# two real recordings: "app" = upload + live log (scripts/record_demo.py),
# "rep" = the same run's report page (scripts/video/record_report.py)
TL = {k: json.loads((ROOT / d / "timeline.json").read_text()) for k, d in (("app", "demo/raw"), ("rep", "demo/raw-report"))}
SRC = {k: ROOT / d / TL[k]["video"] for k, d in (("app", "demo/raw"), ("rep", "demo/raw-report"))}


def ev(rec: str, prefix: str) -> float:
    for e in TL[rec]["events"]:
        if e["event"].startswith(prefix):
            return e["t"]
    raise KeyError(prefix)


def run(*a):
    subprocess.run(a, check=True)


def voice():
    pipe = None
    (B / "vo").mkdir(parents=True, exist_ok=True)
    durs = {}
    for sc in story["scenes"]:
        wav = B / "vo" / f"{sc['id']}.wav"
        key = B / "vo" / f"{sc['id']}.txt"
        said = sc.get("say", sc["text"])
        if wav.exists() and key.exists() and key.read_text() == said:   # cached: same words, same voice
            a, _ = sf.read(wav, dtype="float32")
            a = cap_pauses(a)
            sf.write(wav, a, SR, subtype="PCM_16")
            durs[sc["id"]] = len(a) / SR
            continue
        if pipe is None:
            from kokoro import KPipeline
            pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        audio = np.concatenate([np.asarray(a) for _, _, a in pipe(sc.get("say", sc["text"]), voice="af_heart", speed=1.0)])
        # trim leading/trailing near-silence so scene gaps are exactly GAP
        thr = 10 ** (-45 / 20) * np.abs(audio).max()
        nz = np.flatnonzero(np.abs(audio) > thr)
        audio = cap_pauses(audio[max(0, nz[0] - 240): nz[-1] + 480])
        sf.write(wav, audio, SR, subtype="PCM_16")
        key.write_text(said)
        durs[sc["id"]] = len(audio) / SR
        print(f"voiced {sc['id']}: {durs[sc['id']]:.2f}s")
    return durs


def cap_pauses(audio, max_pause=0.40, thr_db=-45):
    """Shorten any pause inside a voice clip to max_pause seconds (Kokoro sometimes pauses ~0.6 s at a full stop)."""
    thr = 10 ** (thr_db / 20) * np.abs(audio).max()
    win = int(0.01 * SR)
    loud = np.array([np.abs(audio[i:i + win]).max() > thr for i in range(0, len(audio), win)])
    keep, run = [], 0
    for i, l in enumerate(loud):
        run = 0 if l else run + 1
        if l or run * 0.01 <= max_pause:
            keep.append(audio[i * win:(i + 1) * win])
    return np.concatenate(keep)


def seg_window(sc):
    s = sc["src"]
    if s.startswith(("card:", "still:")):
        return None
    rec, rng = s.split(":", 1)
    a, b = rng.split("..")

    def t(x):
        m = re.fullmatch(r"(.+?)([+-][\d.]+)?", x)
        return ev(rec, m.group(1)) + (float(m.group(2)) if m.group(2) else 0.0)
    return rec, t(a), t(b)


def build():
    durs = voice()
    parts = []
    for i, sc in enumerate(story["scenes"]):
        d = durs[sc["id"]] + GAP
        out = B / f"scene{i:02d}.mp4"
        win = seg_window(sc)
        label = sc.get("label", "")
        if win is None:
            kind, name = sc["src"].split(":", 1)
            card = B / f"card-{name}.png" if kind == "card" else ROOT / "demo/raw-report" / f"{name}.png"
            vf = "format=yuv420p"
            if sc.get("box"):  # highlight one region of a still, e.g. the row the narration is about
                x, y, w, h = sc["box"]
                vf = f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0xd9822b@0.95:t=5:enable='gte(t,{sc.get('box_from', 0)})'," + vf
            run("ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-t", f"{d:.3f}", "-i", str(card),
                "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(out))
        else:
            rec, a, b = win
            seg = b - a
            hold = float(sc.get("hold_end", 0))      # keep the final frame on screen this long
            speed = max(1.0, seg / (d - hold))
            vf = f"trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{speed:.4f},tpad=stop_mode=clone:stop_duration={d:.3f}"
            if speed > 1.05 and "{speed}" in label:
                label = label.replace("{speed}", f"{speed:.0f}").replace("{real}", f"{seg:.0f}")
            if label:
                lf = B / f"label{i:02d}.txt"
                lf.write_text(label)
                vf += (f",drawtext=fontfile={FONT}:textfile={lf}:x=(w-tw)/2:y=h-110:fontsize=34:fontcolor=white:"
                       "box=1:boxcolor=0x2f6b4f@0.92:boxborderw=14"
                       f":enable='lt(t,{d - hold:.3f})'")  # only while the footage is sped up, not over the held end
            vf += f",trim=duration={d:.3f},fps=30,format=yuv420p"
            run("ffmpeg", "-loglevel", "error", "-y", "-i", str(SRC[rec]), "-vf", vf, "-an", "-c:v", "libx264",
                "-preset", "medium", "-crf", "18", str(out))
        parts.append((out, sc["id"], d))
        print(f"scene {sc['id']}: {d:.2f}s" + (f" (speed x{max(1.0, (win[2] - win[1]) / (d - float(sc.get('hold_end', 0)))):.1f})" if win else ""))

    lst = B / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p, _, _ in parts))
    run("ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(B / "video.mp4"))
    # narration track: each line at its scene start
    total = sum(d for _, _, d in parts)
    track = np.zeros(int(total * SR) + SR, dtype=np.float32)
    t = 0.0
    for _, sid, d in parts:
        a, _ = sf.read(B / "vo" / f"{sid}.wav", dtype="float32")
        i = int(t * SR)
        track[i:i + len(a)] += a
        t += d
    sf.write(B / "vo.wav", track[: int(total * SR)], SR, subtype="PCM_16")
    # two-pass loudness normalisation to -14 LUFS, TP -1.5
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(B / "vo.wav"), "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    j = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", m).group(0))
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    run("ffmpeg", "-loglevel", "error", "-y", "-i", str(B / "video.mp4"), "-i", str(B / "vo.wav"),
        "-af", af + ",aresample=48000", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart", str(OUT))
    print(f"wrote {OUT} ({total:.1f}s)")


if __name__ == "__main__":
    build()
