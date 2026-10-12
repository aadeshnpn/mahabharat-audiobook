# Episode 2 draft: review notes (text only, no audio)

Script for review: `episodes/ep02_script.md` (line by line, with the TTS text where it differs). Cue sheet:
`episodes/ep02.cues.txt`. Spec: `episodes/ep02.yaml`. Overrides: `episodes/overrides/ep02.json`. Option specs:
`episodes/ep02_options/` (proposals, not approved).

## The problem, honestly
Episode 2 starts at **§1 ¶18**, right after Episode 1 ("I will now speak of the undying flowery and fruitful
productions of this tree…": Vyasa fathers Dhritarashtra, Pandu and Vidura). **Unabridged, there is no 15–20 min
ending that isn't mid-dialogue:**

| Span | What | Time (est.) |
|---|---|---|
| ¶18–29 | Sauti's story in brief, from the three princes to the dice and the war | 0:00–8:57 |
| ¶30 | "Dhritarashtra… addressed to Sanjaya the following speech:" | 8:58 |
| **¶31–35** | **Dhritarashtra's lament, one unbroken speech** (¶33 alone is 1,949 words) | **9:13–29:09 (~20 min)** |
| ¶36–38 | he faints; wishes to die; Sanjaya begins | 29:11–29:54 |
| ¶39 | Sanjaya's consolation: the great kings of old, and Time | 29:55–34:24 |
| ¶40 | Sauti closes the scene: "…Dwaipayana composed a holy Upanishad" | 34:25–34:45 |

The breaks tool's top candidates near 17:30 all fall inside ¶33 (a "When I heard…" stanza in the middle of
Dhritarashtra's speech), so I rejected them under the never-mid-dialogue rule. The clean breaks are **¶29 (8:57)** and
**¶40 (34:45)**. The duration model is trustworthy: Ep 1 was estimated at 17:22 and rendered at 17:18.

**As drafted, `ep02.yaml` is the full unabridged §1 ¶18–40 (34:45, 158 lines)**, segmented so any option below is a
one-line change. Nothing is abridged.

## Options for Episode 2 (pick one)

| | Option | Ep 2 ends | Duration | Abridged? |
|---|---|---|---|---|
| **A1** | Unabridged, short: ¶18–29 only; Ep 3 = the whole lament + consolation (¶30–40, ~25:50) | ¶29, "the terrific war that ensued" | **8:57** | no |
| **A2** | Unabridged, long (drafted): ¶18–40 as one double-length episode | ¶40, "Dwaipayana composed a holy Upanishad" | **34:45** | no |
| **B** | Marked abridgement, KMG words only: omit ¶33 (55 stanzas from the forest exile to the end of the war), keep ¶32's 13 stanzas (Draupadi's swayamvara to dice and exile) and everything else (`ep02_options/ep02_B_drop_p33.yaml`) | ¶40 | **20:33** | yes, flagged `abridged` |
| **B′** | Marked abridgement, KMG words only, keeping an arc of ~12–15 stanzas across the whole story and war (bow, Draupadi won, dice, garment, exile, Krishna's embassy, Karna quits, Bhishma on his bed of arrows, Abhimanyu, Drona, Duhsasana's blood, Karna slain, Duryodhana at the lake and the club duel, the sleeping Panchalas, Brahmashira). Needs a small `drop` override in the builder (not built yet). | ¶40 | **~20:40–21:30** (~19:20–20:10 if the ¶39 list of king names is also trimmed) | yes, flagged |
| **C** | Flagged non-KMG narrator summary: Sauti summarises ¶32–33 in ~43 s, ending "then, O Sanjaya, I had no hope of success" (`ep02_options/ep02_C_summary_bridge.yaml`) | ¶40 | **17:36** | yes, a `non_kmg` bridge replaces ~18 min |

**How it would play.** ¶18–29 is a brisk, eventful summary: it works. The lament is the dramatic heart of §1: a blind
father reliving his ruin, refrain after refrain. With a strong Dhritarashtra voice, varied direction (the script
grades it: defensive in ¶31, bitter wonder in ¶32, hope draining through ¶33, broken at ¶34–35) and music that
swells only at the turning points, 20 minutes of it is powerful but heavy. Sixty-five stanzas averaging 16 s, each
ending "then, O Sanjaya, I had no hope of success", is a litany, and listeners who don't know the story yet will hear
a long list of events they haven't met. Sanjaya's reply (¶39) also opens with ~1:20 of king names.

**My suggestion:** if unabridged is firm, **A2** (one long, unabridged episode with clean ends; an "extended episode"
is better than an 8-minute one or a mid-speech cliffhanger). If you'll allow a marked abridgement here, **B′** keeps
the arc of the lament in KMG's own words at ~20 min. **C** fits the target best, but it puts non-KMG words in place of
the most dramatic passage.

## Beyond Episode 2: the list-like run (§1 ¶41–46 and §2)
After ¶40 come **§1 ¶41–46** (merits of hearing the Bharata, 4:00) and **§2 Parva-sangraha** (61:13). §2 breaks
down as follows:

| §2 span | What | Time |
|---|---|---|
| ¶1–7 | Samantapanchaka (Rama's lakes of blood), what an Akshauhini is, the battle's 18 days, "listen to the outlines" | 7:08 |
| ¶8–9 | **the list of a hundred parva names** | 5:49 |
| ¶10–30 | **contents of each of the 18 parvas**, incl. 29 verse/section-count sentences (3:26) | 44:48 |
| ¶31–33 | the merits again, "shake off all inaction" | 3:28 |

Options for the run after Ep 2 (estimates; nothing changed):
1. **Unabridged:** ~65 min ≈ 4 episodes: Ep 3 §1 ¶41–§2 ¶9 (~16:55, ends after the hundred-parva list, "…of which the
   above is only an abridgement"); Ep 4 §2 ¶10–13 (~19:40, Adi to Virata); Ep 5 ¶14–20 (~16:20, Udyoga to Stri); Ep 6
   ¶21–33 (~12:20, Santi to the end of §2).
2. **Marked abridgement:** omit the 29 count sentences and the ¶8 name list (−9:15): ~56 min, still ~3 episodes.
3. **Flagged non-KMG summary:** keep §1 ¶41–46, §2 ¶1–7 and ¶31–33 in full, and replace ¶8–30 with a ~3 min Sauti
   overview of the eighteen parvas: **one ~17–18 min Episode 3**, after which the story proper (§3, Paushya) begins.

## Attribution fixes (spot-checked, with overrides)
- **Builder bug fixed (text loss):** an interrupted quote inside a paragraph that opens mid-quotation dropped the rest
  of the paragraph. In ¶23 everything after "'These our pupils" was missing ("said they, 'are as your sons… they
  are Pandavas.' Saying this, the Munis disappeared."). A sweep of all of Book 1 found **16 paragraphs** hit (incl. §2 ¶8
  at 36 % coverage, §148 ¶2 at 9 %). Fixed in `attribute.py`. Every build now runs a letter-level **coverage check**
  (`TEXT LOST?` warning; 0 across Book 1 after the fix). The Ep 0/Ep 1 scripts are unchanged (no re-render).
- **Dhritarashtra ¶31–35, ¶37** (84 lines): KMG nests his speech in single quotes inside Sauti's quotation, so the
  builder had it as Sauti narration. Assigned via paragraph-wide overrides (new `set_type` key, since `type` in an
  override row is only a match filter).
- **Sanjaya ¶39** (22 lines): likewise. **Sanjaya added to the registry** (he was missing: mentioned only in summary
  sections §1–2). The entry is text-grounded (§1 ¶30–40; §2 ¶14, ¶15, ¶25), with the relationship `serves`
  Dhritarashtra. The registry now has 166 characters and 340 relationships, and the web app is reseeded.
- **¶23 the Munis** → *Rishis of Satasringa* (shares the Naimisha Rishis voice); "said they," and "Saying this, the
  Munis disappeared." stay with Sauti.
- **¶24 the citizens' cry** ("They are on all accounts welcome!…"): no crowd voice exists, so Sauti reads it (an
  explicit, flagged choice, joyful).
- **Draupadi/Krishnaa:** "the virgin Krishna at the swayamvara" (¶27) is spoken as *Draupadi* (automatic rule).
- **OCR repairs, TTS only (KMG text untouched, flagged `ocr_fix`):** "Kama" → *Karna* ×3 (¶30, ¶33); "then, O
  Sanjaya. I had no hope…" and "When I heard that Nakula. the son of Madri…" merged and read as one sentence each.
  Other spellings ("shomaka", "Dhristadyumna", "Suvala", "alter" for "after" in ¶31) are left as KMG; tell me if you
  want them repaired for TTS too.

## Voices
| Speaker | Lines | Time | Voice |
|---|---|---|---|
| Sauti | 50 | 9:31 | ✓ |
| **Dhritarashtra** | **84** | **19:43** | **needs a voice** (aged blind king: grief, self-justification, despair; must carry 20 minutes) |
| **Sanjaya** | **22** | **4:19** | **needs a voice** (wise minister and charioteer-bard, calm, consoling; distinct from Sauti, also a Suta) |
| Rishis of Satasringa | 2 | 0:07 | ✓ (Naimisha Rishis group voice) |
| *(optional)* Hastinapura citizens | 3 | 0:05 | crowd voice, or keep Sauti as now |

None designed yet. Under options B/B′/C Dhritarashtra still needs a voice (¶31, ¶34–35, ¶37).

## Music (preset A, per-episode cues in `ep02.yaml`)
| Moment | Time | Cue |
|---|---|---|
| Sauti resumes at Naimisha (¶18) | 0:00 | forest_ashram 0.40 |
| the story in brief | 0:41– | narration_warm 0.35 |
| Pandu's misfortune (the stag) / the divine fathers | 3:20 / 3:47 | grave_drone 0.35 / sacred_solemn 0.45 |
| the Munis present the boys, then vanish | 4:27 | tender_resolve → celestial_swell |
| the citizens' welcome / unseen spirits, rain of flowers | 5:06 / 5:16 | bright_lift 0.60 / celestial_swell 0.70 |
| Draupadi won, conquests, the Rajasuya | 6:21–7:19 | royal_resolve 0.45 |
| Duryodhana's envy, the dice, the war | 7:19–8:57 | grave_drone 0.45 |
| Dhritarashtra's lament | 9:13–28:27 | sparse grave_drone 0.30 (blooms in pauses), swelling to 0.50 at 8 turning points: Draupadi's garment 13:17, Bhishma's bed of arrows 20:15, Abhimanyu 21:48, Drona 24:26, Duhsasana's blood 25:14, Duryodhana at the lake 26:24, the sleeping Panchalas 27:17, Brahmashira 27:49 |
| "Alas!", the king faints, wishes to die | 28:27–29:54 | grave_drone 0.55 / 0.40 |
| Sanjaya consoles | 29:55 | tender_resolve 0.40 |
| "Time createth all things…" | 33:32 | sacred_solemn 0.50 |
| Sauti closes the scene | 34:25 | reverent_anticipation (ending hook) |

## Names: pronunciation harness
PRON_PLACEHOLDER
