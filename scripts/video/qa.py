"""Video QA. Fails (exit 1) on any issue and writes demo/build/qa/qa.json.
  - 1920x1080, duration <= 90 s
  - integrated loudness -14 +-1 LUFS, true peak <= -1.0 dBTP
  - no silence longer than 0.6 s (silencedetect at -50 dB)
  - writes a full-size frame every 2 s (1920 px wide) for frame-by-frame review, plus 3x3 contact sheets
Usage: python3 scripts/video/qa.py demo/tidy-predict-demo.mp4 demo/build/qa"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

video, qa = Path(sys.argv[1]), Path(sys.argv[2])
shutil.rmtree(qa, ignore_errors=True)
(qa / "frames").mkdir(parents=True)


def probe(args):
    return subprocess.run(["ffprobe", "-v", "error", *args, str(video)], capture_output=True, text=True).stdout.strip()


def ff_null(flag, f):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), flag, f, "-f", "null", "-"],
                          capture_output=True, text=True).stderr


issues = []
dur = float(probe(["-show_entries", "format=duration", "-of", "csv=p=0"]))
wh = probe(["-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0"])
if wh != "1920,1080":
    issues.append(f"resolution {wh}")
if dur > 90:
    issues.append(f"duration {dur:.1f}s > 90 s")
m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", ff_null("-af", "loudnorm=I=-14:TP=-1.5:print_format=json")).group(0))
lufs, tp = float(m["input_i"]), float(m["input_tp"])
if abs(lufs + 14) > 1:
    issues.append(f"loudness {lufs:.1f} LUFS")
if tp > -1.0:
    issues.append(f"true peak {tp:.1f} dBTP")
sil = ff_null("-af", "silencedetect=noise=-50dB:d=0.6")
silences = [(float(a), float(b)) for a, b in re.findall(r"silence_start: ([\d.]+).*?silence_duration: ([\d.]+)", sil, re.S)]
if silences:
    issues.append(f"{len(silences)} silence(s) > 0.6 s: {silences}")
subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", "fps=1/2", str(qa / "frames" / "t%03d.png")], check=True)
frames = sorted((qa / "frames").glob("*.png"))
fw = probe(["-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=p=0"])
subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(qa / "frames" / "t%03d.png"), "-vf",
                "scale=640:-1,tile=3x3", str(qa / "sheet%02d.png")], check=True)
out = {"video": str(video), "duration_s": round(dur, 2), "resolution": wh, "lufs": lufs, "true_peak_dbtp": tp,
       "silences_over_0_6s": silences, "frames_every_2s": len(frames), "frame_width_px": int(fw), "issues": issues,
       "pass": not issues}
(qa / "qa.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
sys.exit(1 if issues else 0)
