# VOICE-SCRIPT v5: Harsha ki apni awaaz (record karke bhejo)

Video 69 s ka hai. Neeche har scene ki exact line hai (jo ab TTS bol raha hai). Har line ke saamne scene ki length hai: apni line is se thodi chhoti rakho (line ke baad ~0.4 s ruko), nahi to video us scene ko thoda lamba kar dega.
Persona **Meera fictional hai**, voice mein bhi aisa hi bolo jaise kahani suna rahe ho: warm, thoda dheere. Tech wale scenes thode tez aur saaf.
Numbers: bolne ke liye 'about forty-four hundred' aur 'about twenty-six hundred' hi rakha hai (screen par exact 4,452 / 2,592 dikhta hai).

## Recording tips (Hinglish)
- Phone mein Voice Recorder kholo. Quiet kamra, fan/AC band, phone mooh se ek haath door, thoda side mein (pop sound kam hoga).
- **Ek line = ek take = ek file.** Galti ho to line dobara bolo, pehle wali file delete karo. Line ke pehle 1 sec chup, baad mein 1 sec chup.
- Aise bolo jaise dost ko bata rahe ho, reading mat karo. Apna natural accent rakho (Indian English bilkul theek hai, wahi sach hai).
- Tarikh, Kitne, Maal: jaise tum bolte ho waise hi bolo.
- File names bilkul yahi: `s01_hook.m4a`, `s02_drop.m4a` ... (m4a, wav, mp3 sab chalega). Sab ek folder mein daalo, folder ka path mujhe do.
- Kuch lines na bhejo to un scenes mein TTS hi rahega (mix chalega, par ek hi awaaz better lagti hai).

## Lines

| # | File name | Scene length | Line (bolo ye) | Tone |
|---|---|---|---|---|
| 1 | `s01_hook` | 10.5 s | Meera counts her gift shop's stock by hand. And she keeps guessing wrong. Some weeks, the fast seller's gone. Other weeks? Boxes nobody wants, piling up. | story, warm, 'keeps guessing wrong' pe halka rukna |
| 2 | `s02_drop` | 4.1 s | So one day, she drops her order export into tidy-predict. | story |
| 3 | `s03_form` | 4.3 s | She picks a past week to replay. Labels the data. And hits go. | light, tez |
| 4 | `s04_gemma` | 7.7 s | Her headers are odd, so Gemma, right on the laptop, reads them. Tarikh is the date. Kitne, the quantity. Maal, the product. | clear; Tarikh/Kitne/Maal saaf |
| 5 | `s05_forecast` | 6.5 s | Over a million rows get cleaned. Then TabPFN-2 forecasts her twenty regular sellers. | clear |
| 6 | `s06_note` | 3.9 s | Gemma writes the note. And plain code checks every number in it. | clear |
| 7 | `s07_report` | 3.9 s | And here's her restock note. What to have ready for a busy week. | story, warm |
| 8 | `s08_table` | 6.5 s | Next to each item, there's a likely range, and what really sold. Seventeen of twenty landed inside. | clear |
| 9 | `s09_miss` | 8.5 s | Now, the honest miss. Rabbit night lights sold about forty-four hundred. Way above the busy-week number, about twenty-six hundred. | serious, honest; 'the honest miss' ke baad pause |
| 10 | `s10_next` | 5.7 s | Meera stocks to the busy-week number, keeps a few spares, and still checks the shelf herself. | story, warm, calm |
| 11 | `s11_clean` | 4.0 s | Everything set aside is listed. Open models, run locally. | clear |
| 12 | `s12_end` | 3.7 s | Built with PriorLabs TabPFN. By Harsha Shinde. | friendly, aakhri line |

## Baad mein swap kaise karna hai (mere liye)
```
cd ~/workspace/dev-hacktoberfest/tidy-predict && flock ~/workspace/.heavy.lock systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=256M \
  ~/workspace/.video-venv/bin/python scripts/video/make_v5.py --voice-dir /path/to/harsha-recordings --out tidy-predict-demo-v5-harsha.mp4
```
Script har clip ko trim karti hai, lambi pauses 0.4 s tak kaat deti hai, scene ki length clip ke hisaab se adjust hoti hai, aur -14 LUFS / true peak check khud karti hai. Jo scene ka file nahi mila wahan Kokoro (am_michael) bolega.
