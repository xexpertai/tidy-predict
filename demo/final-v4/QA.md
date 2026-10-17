# QA, video v4 (17 Oct 2026)
File: tidy-predict-demo-v4.mp4, 53.6 s, 1920x1080, 30 fps, AAC 48 kHz. Source: ONE real run of the web page (demo/raw-v4e, Playwright capture, real TabPFN-2 and local Gemma 4 E2B, 139 s, sped-up parts labelled "Sped up").
## Audio (ffmpeg loudnorm measure on the final file)
- Integrated loudness: -14.38 LUFS (target -14, within 0.4)
- True peak: -1.36 dBTP (limit -1.0) PASS
- Longest silence (< -45 dB): 0.56 s (limit 0.6 s) PASS
## Visual (rule 7; contact sheets at 1920 px wide, 960 px tiles, key moments only)
qa-sheets/sheet1.png (hook, upload, form), sheet2.png (log, forecast, note, report), sheet3.png (table, rabbit miss, cleaned, end card), gif-check.png (the two GIFs). Frames viewed: 1,3,5,9,15,22,27,32,36,40,44,47,52 s. Hook crop re-checked at 1280 px after change.
- Found and accepted: faint ghosting on the table scroll (screen-capture compression); caption box covers one table row for ~2 s in the "report" scene.
- Numbers on screen checked against the run: 17 of 20 actual sales inside P10-P90 (counted from report.html), rabbit night light 4,452 sold vs 2,592 P90, 70,254 rows set aside. No invented numbers. Demo-data label shown in the first scene and on the end card. No third-party trademarks (partner credit "Built with PriorLabs-TabPFN" is the licence-required attribution).
## Media
demo-run.gif 14.1 s 3.06 MB; restock-note.gif 12.5 s 4.10 MB (both under 5 MB, 900 px wide). 5 PNG screenshots 1920x1080 (1-5 *.png).
## Not done
No transcript-vs-audio re-listen by a human; Kokoro reads "Tarikh/Kitne" with phonetic spellings (Taareekh/Kitney).
