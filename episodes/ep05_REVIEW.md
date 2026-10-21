# Episode 5 draft: review notes (text only, no audio)

Script for review: `episodes/ep05_script.md`. Cue sheet: `episodes/ep05.cues.txt`. Spec: `episodes/ep05.yaml`.
Overrides: `episodes/overrides/ep05.json`. Shard plan: `episodes/ep05.shards.txt` (5 shards, ~3–4 min each).

## Span and end point
- **Book 1 §2 ¶9–12, unabridged KMG, in order. Estimated 18:37 of narration** (1117 s at 138.1 wpm, pauses included;
  52 lines; target 15–20 min). With the v6 sting title (45 s) and ending (18 s), each with its 2.5 s crossfade, plus
  the music tail, the file will be about **19:40**.
- **Starts** right after Ep 4: "The high-souled Vyasa composed these hundred parvas… as follows:" (¶9, the bridge into
  the summary of the eighteen parvas).
- **Ends at §2 ¶12**, the close of the Aranyaka (third) parva: "These are all included in the third Parva called
  Aranyaka, consisting of two hundred and sixty-nine sections. The number of slokas is eleven thousand, six hundred
  and sixty-four." This ranked first in `mbh episode breaks` (complete sentence, paragraph boundary, in narration,
  between parvas). ¶13 opens the Virata parva, which starts Ep 6.
- **Alternatives:** ending after the Sabha parva (¶11) gives only about 9:25. Going through ¶13 (Virata, about 1:30
  more) gives about 20:10 of narration, about 21:15 with the title and ending, which is over the 20-minute target.

## Outline
| Time | ¶ | What happens |
|---|---|---|
| 0:00 | ¶9 | Vyasa's hundred parvas gathered into eighteen; Sauti recites them "as follows" |
| 0:16 | ¶10 | **Adi parva:** its sub-parvas; Utanka, Bhrigu, Garuda and the Nagas, the churning of the ocean |
| 1:14 | ¶10 | Sambhava: the births of kings, Vyasa, Bharata son of Sakuntala; Ganga and the Vasus |
| 1:57 | ¶10 | Bhishma's vow; Chitrangada and Vichitravirya; Dhritarashtra, Pandu and the Pandavas; the house of lac |
| 3:21 | ¶10 | Ghatotkacha, Ekachakra and Vaka; Draupadi's Swayamvara and the five husbands |
| 5:44 | ¶10 | Arjuna's exile, Ulupi, Subhadra, Abhimanyu; Khandava, the Gandiva, Maya (227 chapters, 8,884 slokas) |
| 7:38 | ¶11 | **Sabha parva:** the hall, the Rajasuya, Jarasandha and Sisupala; the dice game, Draupadi, the exile (78 sections) |
| 9:25 | ¶12 | **Aranyaka parva:** the Pandavas go to the forest; Kirmira; Krishna's visit; Dwaita and Kamyaka; Arjuna's quest for weapons |
| 11:51 | ¶12 | Nala and Damayanti; Lomasa; the pilgrimages; Agastya, Rishyasringa, Parasurama, Sukanya and Chyavana |
| 13:47 | ¶12 | Mandhata, Jantu, the hawk and the pigeon, Ashtavakra; Gandhamadana, Hanuman, Kailasa, the Nivatakavachas |
| 16:23 | ¶12 | Markandeya's tales; Draupadi and Satyabhama; Duryodhana's capture; Jayadratha; Rama; Savitri; Karna's ear-rings |
| 18:23 | ¶12 | the close: 269 sections, 11,664 slokas |

**Listenability risk:** like Ep 4's ¶8, this is a table of contents. It is fuller than ¶8 (each entry is a short plot
summary) but it is still a list read by one voice for 18 minutes. It is unabridged, as the house style requires.
Emotions are evened out to warm/solemn and measured pace, with a direction note ("reading the table of contents of a
great epic; even, unhurried, each item distinct"). The music gives the list some shape: grave drone under the house
of lac, the dice game and the battles; tender under the weddings; sacred under the sages' stories; forest ashram for
the forest parva.

## Speakers and voices
- **Sauti only.** There is no quoted speech in ¶9–12, so there are no character lines, no crowd lines and no Rishis
  lines. Narrator tags: none occur in this span.
- **No new voices needed.** The Sauti voice is already approved (`voices/sauti/ref.wav`).

## Long lines split (structure only; KMG text unchanged)
¶10–12 are made of very long sentences joined by semicolons. The builder splits only at sentence ends, which left
nine lines from 50 to 145 seconds long, including one of 2,077 characters. To keep VoxCPM2 takes stable and retakes
cheap, those lines are `split` at "; " or ": " into parts of about 300–480 characters. The parts re-join exactly to
the KMG text (the builder checks this). The longest line is now about 45 s (Ep 1 rendered an 84 s line cleanly).

## OCR / print repairs (spoken text only via `tts_replace`, flagged `ocr_fix`; KMG text untouched)
These typos are in the source text (also in the Gutenberg edition):
- ¶10 "Adivansavatara, **Samva**" → **Sambhava** (the sub-parva named again a few lines later as "The Sambhava parva").
- ¶10 "the curse of **Animondavya**" → **Animandavya** (KMG's own spelling where his story is told later in the Adi parva).
- ¶10 "the defeat of Salya, **Kama**" → **Karna** (the same rn→m misprint fixed in Ep 4).
- ¶11 "divided into **seventh-eight** sections" → **seventy-eight**.
- ¶12 "their brother Arjuna **staving** in the heavens" → **staying**.
- ¶12 "the Nivatakavachas dwelling in **Hiranyaparva**" → **Hiranyapura** (their city; "parva" is confusing in a list of parvas).
- ¶12 "the Rishi **Tarkhya**" → **Tarkshya** (KMG's spelling elsewhere).
- ¶12 "the shrine **Putasta**" → **Pulastya** (Narada's account of the tirthas is taught by Pulastya). *Least certain of
  the fixes; say if you'd rather keep "Putasta".*
- ¶12 "called Aranyaka (relating to the forest) This parva…": the missing full stop is added after the gloss is removed,
  so the TTS doesn't run the two sentences together.

Spoken-form tidying (not typos): Su-kanya → Sukanya, Khandava-prastha → Khandavaprastha, extra-ordinary →
extraordinary, Snake-sacrifice → snake sacrifice (hyphens make VoxCPM2 spell or stall).

Kept as KMG (spelling variants, not misprints): Sauva (Saubha), Vabhruvahana, Vrihidraunika, Adivansavatara, and the
odd phrase "the ill-shaving of Jayadratha's crown".

## "Krishna" = Draupadi
The resolver turns the two Draupadi uses into "Draupadi" for TTS: "the extra-ordinary births of Krishna and
Dhrishtadyumna" and "connubial companionship with Krishna". The others stay Krishna (Vasudeva): Balarama and Krishna
at the Swayamvara, Vidura's sight of Krishna, Subhadra's brother, the pleasure-trip to the Jamuna, the wrath of
Krishna allayed by Dhananjaya, and Krishna cheering Draupadi.

## Glosses not spoken
(the Asura-architect), (snakes), (serpent), (?), (relating to the forest), (of the Pandavas), (in search of the
sweet-scented flower), (he was in search of), (to acts of vengeance), (Kuvera), (Jantu), (from which they had been
excluded by the other gods), (as a boon from the grateful Aswinis), (missile weapon), (the god of justice),
(Yudhishthira).

## Pronunciation risks
About 80 names have no lexicon entry, among them Adivansavatara, Animandavya, Arshtishena, Ashtavakra, Brihadaswa,
Dhundhumara, Gandhamadana, Haihayas, Kalakeyas, Kartavirya, Lopamudra, Markandeya, Nivatakavachas, Pratismriti,
Rishyasringa, Saryati, Satyabhama, Uchchaihsrava, Vabhruvahana, Vaisravana, Vrihidraunika, Yajnaseni and Yavakrita.
About 38 more are in the lexicon but unverified. Before rendering I propose the same harness pass as Ep 4 (Sauti's voice, KMG
spelling first, plain-word respellings only for failures, no caps/hyphens), and then a 2-minute sample.

## Render plan (after your approval)
Harness pass → short sample → `setsid nohup tools/render_sharded.sh episodes/ep05.yaml 4` (5 shards, one model
process at a time) → assemble with music preset A, -16 LUFS, `intro: title_song` / `outro: ending_song` (v6 sting) →
QA (`qa_episode.py`, `qa_music.py`) → `cache_sync.py backup` + export chunks for the render-cache release.
The cache has been restored and pulled. All 52 lines are new, so all of them will render.
