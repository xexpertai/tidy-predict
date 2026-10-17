# QA, video v5 (17 Oct 2026)
File: tidy-predict-demo-v5.mp4, 69.4 s, 1920x1080, 30 fps, H.264 + AAC 48 kHz. Built by scripts/video/make_v5.py from ONE real recording (demo/raw-v4e, real TabPFN-2 + local Gemma 4 E2B run) plus two animated illustration scenes (scripts/video/illustration/story.html, recorded with Playwright) and an end card.

## What changed vs v4
1. Hook: an animated illustrated opening (stock register with tally marks and scribbles, calculator showing "?", empty shelf tagged "Rabbit night light / SOLD OUT", boxes piling on the other shelf). On-screen headline "Counting stock by hand = guessing" is fully shown by 1.7 s, the voice line "Meera counts her gift shop's stock by hand. And she keeps guessing wrong." lands in the first 3.5 s. Hard cut to the real app at 10.5 s. Chips "Illustration" and "Fictional persona" are on screen.
2. Persona Meera (first name only, fictional). First appearance carries: "Fictional shop owner. The problem is real: a shop I know counts stock by hand." Chips "Meera: fictional" in the app scenes. Story: problem, drop file, restock note, the honest miss, next step (second illustration, "Meera (fictional)"). End card: "Persona is fictional; demo data is public (UCI Online Retail II, CC BY 4.0) ... Not a client. No real customer results are shown." plus "by Harsha Shinde". No quotes, no testimonial, no results claimed for Meera.
3. Captions: dedicated 200 px lower band under a 1564x880 stage. Nothing is drawn over the page. Checked at full size on every caption scene (sheets below).
4. Smooth eased zooms (about 1.1 s) on the Gemma header-mapping log, the restock note, and the rabbit night light row (cursor ends on 4452).
5. Voice: natural-speech script (contractions, short sentences, "about forty-four hundred"), Kokoro am_michael, per-scene speed (story scenes 1.00-1.04, technical 1.10), mild compression. `--voice-dir` swaps in Harsha's own recordings (tested with an m4a for one scene). See VOICE-SCRIPT.md.

## Audio (ffmpeg loudnorm measure on the final file)
- Integrated loudness: -14.34 LUFS (target -14, within 0.4; same tolerance as v4)
- True peak: -1.31 dBTP (limit -1.0) PASS
- Loudness range 1.8 LU
- Longest silence: 0.46 s at -45 dB and at -35 dB (limit 0.6 s) PASS

## Visual (rule 7; contact sheets 1920 px wide, 960 px tiles, 4 tiles each)
qa-sheets/sheet1.png (illustration hook 0.8/2.6/5.5/9.8 s), sheet2.png (drop, form, Gemma log with mapping line), sheet3.png (note, restock note zoom, table, miss; first pass), sheet4.png (miss, next-step illustration, cleaned, end card), sheet5.png (Gemma log, restock zoom, miss zoom hold). All caption scenes read at full size: no caption touches page content, no cut-off text. Layout bug found and fixed during QA: first zoom crops were cut at the right edge (crop used the wrong frame width), later-scene frames kept playing after a clip's end (fixed with -t as input option), apostrophes/newlines in drawtext.
Numbers on screen checked against the run: 1,067,371 rows, 4,452 sold vs 2,592 busy-week number (P90), 17 of 20 inside (spoken; same count as v4 QA from report.html), names Tarikh/Kitne/Maal. Narration says "about forty-four hundred" and "about twenty-six hundred" (rounded from 4,452 and 2,592; exact figures are in the caption).
No third-party logos or trademarks. Illustration product names (rabbit night light, popcorn holder, red harmonica, paper chain kit) are items from the public dataset; the illustration shows tally marks only, no invented numbers. Fonts: Caveat (SIL OFL) in scripts/video/assets with its licence.

## Voice engine comparison (honest)
- Tried Chatterbox (MIT, with exaggeration control): installed in ~/workspace/.tts-venv (separate venv, stock default voice only, nothing cloned). It was killed by the 3 GB memory cap while loading the model (fp32, "oom-kill" in the journal), and the shared heavy-lock queue was blocked for over an hour by other jobs, so no Chatterbox audio exists. Not used. StyleTTS2 was not attempted (needs more RAM/CPU time and an espeak setup; no realistic way to finish in the hour).
- Kokoro compared on the same 2 lines (hook, miss): af_heart, am_michael, am_adam, bm_george. I cannot listen; the choice is by measurement: all transcribe correctly with faster-whisper small.en (clarity), am_adam is fastest (2.7 words/s) but runs the second line together with no pause (max gap 0.00 s), af_heart and bm_george are clean but slow/flat, am_michael keeps clear sentence pauses (0.7-0.8 s) with the widest dynamic variation (LRA 1.7-4.3). Chosen: am_michael at 1.0-1.1 speed. This is still a synthetic voice; a human listen was NOT done. Harsha's own voice is the real fix.

## Not done
- No human listen to the final audio. GIFs and screenshots from v4 are unchanged (UI shots did not change), not re-made.

## Fix round (manager QA, 17 Oct)
- Miss scene: the table used to scroll on and the cursor sat on 4452. Now the scene holds a cursor-free screenshot from the same run (raw-v4e/report-full.png), with the rabbit night light row boxed and tinted for the whole caption, plus a chip "Row highlighted" (the highlight is added by us; the numbers are the real page). Smooth zoom kept. See qa-sheets/sheet6.png.
- Caption-vs-rows check of every other scene: report, table, Gemma log and note scenes already matched. The "cleaned" scene showed table rows under the caption "Every set-aside row is listed"; it now starts on the "What was cleaned" section (qa-sheets/sheet7.png), and the wrong "Sped up" chip was removed (it plays at 1.0x).
- Re-measured: -14.34 LUFS, -1.31 dBTP, longest silence 0.44 s.

## Harsha-voice build, final (17 Oct, after judge R5)
File: demo/final-v5/tidy-predict-demo-v5-harsha.mp4, 69.2 s, 1920x1080, 30 fps. Voice: Chatterbox (MIT) zero-shot clone of Harsha's own reference (he confirmed it matches). Kokoro numbers above describe the older TTS build.
- Loudness -13.88 LUFS, true peak -1.43 dBTP, LRA 1.9 LU. Longest silence 0.46 s (-35, -45, -50 dB). freezedetect (0.7 s): 0 hits.
- Speaker similarity to reference (ECAPA cosine): 0.71-0.85 per line, mean about 0.79.
- Regenerated for R5 flags: s03 ("to re-play"), s04 (Maahl), s05 ("Tab, P, F, N, two"), s09 ("Now. The honest miss."), s12 ("Prior Labs Tab P F N"); best of 3-5 seeds picked by unprompted whisper small.en.
- Unprompted whisper on the final file now hears: "re-play", "Mahal", "Tab, P, F, N, two", "Now the honest miss", "prior labs, Tab, P, F, N". Still imperfect: "tidy predict" is heard as "tidy predicament", "Tarikh/Kitne" as "Tarek/kidney", "Harsha Shinde" is mumbled at the very end (end card shows it).
- Changes: "AI voice (my own, cloned)" chip on scene 1; step-card zoom at 25 s no longer clips card 4; Meera's writing hand has a pencil, smaller hand; sheets v5h-sheet1/2 re-made (hook/log/zoom, report/miss/next/end).

## Name fix round (17 Oct)
s12 regenerated as "Prior Labs Tab, P, F, N. ... By Har-sha Shin-deh." (best of 10 seed/spelling runs; heard "by Harsha Shinde"), s02 as "Tidy Predict" (heard "tidy predict"). Final file: -13.87 LUFS, -1.55 dBTP, LRA 2.2, max silence 0.46 s, 0 freezes, 69.2 s. Sheet of changed scenes: qa-sheets/v5h-sheet3-changed.png. Hindi words (Tarikh/Kitne/Maal) are heard as "Tarek/kidney/Mahal": natural-sounding, not re-rolled further.
