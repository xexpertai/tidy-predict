# QA, video v6 (18 Oct 2026)
tidy-predict-demo-v6.mp4: 37.3 s, 1920x1080, 30 fps. Built by scripts/video/make_v6.py from story_v6.json: hook card, real recording (demo/raw-v4e), report re-recording (demo/raw-report-v5), end card. No human figures.
Audio: -13.87 LUFS, true peak -1.55 dBTP, max silence < 0.6 s (silencedetect -50 dB), freezes only on the two static cards.
Voice: Chatterbox clone of the private reference, best seed per line by whisper small.en + ECAPA similarity (0.73-0.85).
Transcript: transcript.txt. Frames: qa/ (every 2 s, 1920 px) and q05/ (every 0.5 s).
