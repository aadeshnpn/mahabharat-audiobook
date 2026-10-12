# Episode 1 render QA (v1, 2026-10-11)

Files: `samples/ep01_full_v1_music.mp3` (music preset A + episode cues) and `samples/ep01_full_v1.mp3` (dry).
Timestamps below are positions in these MP3s (identical in both; the music mix adds a 4 s tail at the end).

| | dry | music (A) |
|---|---|---|
| Duration | 17:18 (1037.9 s) | 17:22 (1041.9 s) |
| Integrated loudness (MP3, EBU R128) | -16.0 LUFS | -16.0 LUFS |
| True peak (MP3) | -1.6 dBTP | -1.6 dBTP |
| Overall WER (Whisper small.en vs KMG text) | 6.5 % | 6.5 % (music does not hurt intelligibility) |
| Speech-to-music, min / avg | | 14.1 / 18.5 dB (floor 14; 8 lines trimmed) |

Estimate was 17:22 (138 wpm model).

**Render:** 83 lines. 23 were reused from the cache (lines shared with the pilot, plus the 3 audition lines). 60 rendered
on CPU in ~41 min wall-clock, 17:03–17:44 MDT, including 4 OOM-killed passes that resumed automatically, plus 2 retakes
(~2 min). Assembly with music took ~4 min after vectorizing the loudness code.

**Line QA** (`tools/qa_episode.py`, after retakes): WER per speaker: Sauti 4.8 % (1779 words), Naimisha Rishis 7.6 %
(144), Vyasa 4.6 % (260), Brahma 2.0 % (100), Ganesa 11.1 % (18 words; "pen do" was heard as "pendu"). Overall 4.9 %.
Most remaining errors are Sanskrit-name spellings the recognizer does not know (Daksa/Daksha, Pisakas/Pisachas),
"viz." and archaic forms. Speaker loudness spread was 3.76 dB raw and 0.0 dB after per-line normalization.

**Retakes** (`take: 1` in `episodes/overrides/ep01.json`):
* 0047 "Some read the Bharata beginning with...": in the first take Astika, Uparichara and Brahmanas were not heard
  (WER 0.42). The retake has WER 0.00 and every name heard.
* 0013 "Thence, anxious to see you...": the first take drifted toward Vyasa's timbre (own 0.73, Vyasa 0.11 closer).
  The retake matches Sauti (own 0.80, margin +0.13).

**Pending names:** both are spoken in the KMG spelling and pass in context.
* Prachetas: line 0029, at **~6:33** (line 6:25–6:34). Heard as "Prasetas", similarity 0.88.
* Pitris: line 0030, at **~6:48**, the last word (line 6:34–6:49). Heard as "Patris", similarity 0.83.

## Worth a listen

| Time | Line | Why |
|---|---|---|
| 0:00–0:04 | 0001 Sauti "Om" | Sustained chant (heard "Aum"); same render as the approved pilot opening |
| 2:27–2:32 | 0013 Sauti | Retake (timbre) |
| 2:32–3:05 | 0014 Sauti | One pause > 1.2 s inside the line |
| 5:41–7:55 | 0026–0036 | Loudest music of the episode: cosmic-egg celestial swell (5:41–7:19), Yugas grave drone (7:19–7:55). Speech is ~15 dB over the music, close to the 14 dB floor. Check it isn't too present |
| 6:25–6:49 | 0029–0030 | Prachetas, Pitris |
| 9:46–9:57 | 0047 Sauti | Retake (names) |
| 11:27–12:57 | 0056 Vyasa | 90 s catalogue line (longest single render); flagged as possible repetition, WER 0.04 |
| 12:57–13:03 | 0057 Vyasa | "no writer of this work...": flagged as a possible soft ending |
| 13:06–13:20 | 0059–0060 Brahma | The speaker meter puts these marginally nearer Santanu than Brahma's ref (margins -0.03/-0.015, within noise); 0062 at 13:26 is clearly Brahma (0.83) |
| 14:09–14:31 | 0069 Vyasa, 0071 Ganesa | The Ganesa scene |
| 16:14–17:08 | 0082 Sauti | 54 s line flagged as possible repetition (WER 0.045); the closing tree image and the ending music |

Flags not listed are ASR name spellings or 2-word speech tags ("Sauti said": 1.4 s, WER noisy). Reports:
`build/qa_ep01_final.json`, `build/qa_music_ep01.json`, `build/ep01_full_v1*.report.json` (local, not committed).
