# Episode 3 draft: review notes (text only, no audio)

Script for review: `episodes/ep03_script.md`. Cue sheet: `episodes/ep03.cues.txt`. Spec: `episodes/ep03.yaml`.
Overrides: `episodes/overrides/ep03.json`. Names: see the pronunciation section of `episodes/ep02_REVIEW.md` (one
harness run covered both episodes).

## Span and end point (your choice: option A1)
- **Book 1 §1 ¶30–40, unabridged KMG, in order. Estimated 25:47** (1548 s; 114 lines). Long by design: ¶31–35 is a
  single ~20 min speech with no clean break inside it.
- **Starts:** "And Dhritarashtra hearing the ill news of the success of the Pandavas… addressed to Sanjaya the
  following speech:" (it follows Ep 2's "…the terrific war that ensued").
- **Ends at ¶40**, Sauti closing the scene: "The son of Gavalgana having in this manner administered comfort to the
  royal Dhritarashtra… then restored his mind to peace. Taking these facts for his subject, Dwaipayana composed a holy
  Upanishad…" That ends the dialogue. ¶41 turns to the merits of reading the Bharata.

## Outline
| Time | ¶ | Speaker | What happens |
|---|---|---|---|
| 0:00 | 30 | Sauti | the ill news; Dhritarashtra turns to Sanjaya |
| 0:15 | 31 | Dhritarashtra | defensive: never wanted war, made no distinction between his sons and Pandu's; old and blind, he gave way to Duryodhana; the unfair game was concerted with the king of Gandhara |
| 1:51 | 32 | Dhritarashtra | "When I heard…, then, O Sanjaya, I had no hope of success": the bow and Draupadi, Subhadra, Khandava, the escape from the lac house, Jarasandha, the conquests, the dice, Draupadi's garment (4:19), the exile |
| 5:15 | 33 | Dhritarashtra | the forest years, Arjuna's weapons, Virata, Krishna's embassy (8:47), then the war: Bhishma on his bed of arrows (11:17), Abhimanyu (12:50), Ghatotkacha, Drona (15:27), Duhsasana's blood (16:15), Karna, Salya, Duryodhana at the lake (17:25), the sleeping Panchalas (18:19), Brahmashira (18:51) |
| 19:29 | 34–35 | Dhritarashtra | "Alas! Gandhari…"; only ten survive; "all around me is utter darkness" |
| 20:12 | 36–38 | Sauti / Dhritarashtra | he faints; revived, wishes to die; Sanjaya begins |
| 20:56 | 39 | Sanjaya | the great kings of old (a ~1:20 list of names from 21:28), all dead; "Time createth all things…" (24:34); do not throw away thy reason |
| 25:23 | 40 | Sauti | comfort given; Dwaipayana's Upanishad |

**How it will play:** the lament is 65 stanzas averaging 16 s, each ending "then, O Sanjaya, I had no hope of
success". The script grades the direction: defensive and bitter in ¶31, bitter wonder in ¶32, hope draining through
¶33 ("vary the weight, never sing-song"), broken at ¶34–35. The music stays sparse, swelling only at the turning
points. The Dhritarashtra voice was designed specifically to carry this length.

## Attribution fixes (overrides, moved from the Ep 2 draft)
- **Dhritarashtra ¶31–35, ¶37** (84 lines): KMG nests his speech in single quotes inside Sauti's quotation, so the
  builder had it as Sauti narration. Assigned with paragraph-wide overrides (`apply_all` + `set_type: speech`).
- **Sanjaya ¶39** (22 lines), likewise; Sanjaya was added to the registry (text-grounded: §1 ¶30–40; §2 ¶14, ¶15,
  ¶25; serves Dhritarashtra).
- Sauti keeps ¶30, ¶36, ¶38, ¶40 (incl. the "Sauti said," tags).
- **OCR repairs, TTS only (KMG text untouched, flagged `ocr_fix`):** "Kama" → *Karna* ×3 (¶30, ¶33); "then, O
  Sanjaya. I had no hope…" (the Ghatotkacha stanza) and "When I heard that Nakula. the son of Madri…" each merged and
  read as one sentence. Left as KMG: "shomaka", "Dhristadyumna", "Suvala", "alter" (for "after") in ¶31. Tell me
  if you want those repaired for TTS too.
- Draupadi/Krishnaa: where "Krishna" means Draupadi it is spoken *Draupadi* (automatic). The Krishna of the embassy
  and of "Krishna and Arjuna were Nara and Narayana" stays Krishna.

## Voices
| Speaker | Lines | Time | Voice |
|---|---|---|---|
| Dhritarashtra | 84 | 19:43 | ✓ designed 2026-10-11 (`voices/dhritarashtra/ref.wav`, candidate B_0) |
| Sanjaya | 22 | 4:19 | ✓ designed 2026-10-11 (`voices/sanjaya/ref.wav`, candidate C_1) |
| Sauti | 8 | 1:45 | ✓ |

Audition (2 real Ep 3 lines each, via the episode renderer): `samples/voices_ep03_audition.mp3`.

## Music (preset A, per-episode cues in `ep03.yaml`)
| Moment | Time | Cue |
|---|---|---|
| the ill news | 0:00 | grave_drone 0.40 |
| the lament | 0:15–19:29 | sparse grave_drone 0.30 (blooms in pauses), swelling to 0.50 at 8 turning points: garment 4:19, bed of arrows 11:17, Abhimanyu 12:50, Drona 15:27, Duhsasana's blood 16:15, the lake 17:25, the sleeping Panchalas 18:19, Brahmashira 18:51 |
| "Alas!", faints, wishes to die | 19:29–20:55 | grave_drone 0.55 / 0.40 |
| Sanjaya consoles | 20:56 | tender_resolve 0.40 |
| "Time createth all things…" | 24:34 | sacred_solemn 0.50 |
| Sauti closes the scene | 25:23 | reverent_anticipation (ending hook) |

## Names: pronunciation harness
**Episode 3: 53 of 189 names verified.** The remaining 136 are mostly single mentions in the lament's war
stanzas and in Sanjaya's list of ancient kings (¶39: Suhotra, Rantideva, Kakshivanta, Valhika, Damana, Saryati, Ajita,
Amvarisha, Marutta, Ikshaku, Gaya, Sasavindu, Bhagiratha, Kritavirya, Viswasrawa, Yuvanaswu, Kakutstha, Vikrami,
Raghu, Vijava, Virihorta…). They fall back to the KMG spelling. Tested but not yet verified (one voice, or ASR
disagreement): Indra, Madhu, Panchalas, Akshauhinis, Bharadwaja, Abhimanyu, Sastras, Indraprastha, Dwaraka, Khandava, Dhristadyumna, Upanishad, Gandiva, Yuyudhana, Asuras, Santanu, Rama, Saivya.
Suggested before rendering Ep 3: one harness round on these with the new Dhritarashtra and Sanjaya voices (they speak them).
