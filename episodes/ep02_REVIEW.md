# Episode 2 draft: review notes (text only, no audio)

Script for review: `episodes/ep02_script.md` (line by line, with the TTS text where it differs). Cue sheet:
`episodes/ep02.cues.txt`. Spec: `episodes/ep02.yaml`. Overrides: `episodes/overrides/ep02.json`.

## Span and end point (your choice: option A1)
- **Book 1 §1 ¶18–29, unabridged KMG, in order. Estimated 8:57** (537 s at 138.1 wpm, pauses included; 44 lines).
  The model is trustworthy: Ep 1 was estimated at 17:22 and rendered at 17:18.
- **Starts** right after Ep 1: "Sauti continued, 'I will now speak of the undying flowery and fruitful productions of
  this tree…'"
- **Ends at ¶29**, the close of Sauti's story in brief: "…he made the Kshatriyas kill each other in the terrific war
  that ensued." That's a narration boundary. ¶30 turns to Dhritarashtra's lament, which is **Episode 3**
  (`episodes/ep03_REVIEW.md`).
- Why short: the next clean break after ¶29 is ¶40 (34:45 from ¶18), because ¶31–35 is a single ~20 min speech.
  The alternatives (one 35-min episode; marked abridgements B/B′ at ~20–21 min; a non-KMG summary C at 17:36) are
  recorded in git history (commit 71f9a8c), along with the §2 list-passage options:

| After Ep 3 (§1 ¶41–46 + §2, ~65 min) | Plan |
|---|---|
| Unabridged | ~4 episodes: §1 ¶41–§2 ¶9 (~16:55, ends after the hundred-parva list); §2 ¶10–13 (~19:40); ¶14–20 (~16:20); ¶21–33 (~12:20) |
| Marked abridgement | omit the 29 verse/section-count sentences and the ¶8 name list (−9:15): ~56 min, ~3 episodes |
| Flagged non-KMG summary | replace §2 ¶8–30 with a ~3 min Sauti overview: one ~17–18 min episode |

## Outline (timestamps estimated)
| Time | ¶ | What happens |
|---|---|---|
| 0:00 | 18–19 | Vyasa, at Bhishma's and his mother's word, fathers Dhritarashtra, Pandu and Vidura, then returns to his retreat; only after they have died does he publish the Bharata |
| 1:14 | 20–21 | what Vyasa represented; the 24,000-verse Bharata, the 150-verse epitome, the 6,000,000-verse version (Narada to the Devas, Devala to the Pitris, Suka to the Gandharvas…); "I, Sauti, have also repeated one hundred thousand verses" |
| 3:02 | 22 | Yudhishthira is a vast tree; Arjuna its trunk… Krishna, Brahma and the Brahmanas its roots |
| 3:20 | 23 | Pandu kills a stag coupling with its mate in the forest (his misfortune); the divine fathers; the Munis bring the boys to Hastinapura: "These our pupils… are Pandavas" |
| 5:06 | 24 | the citizens' cry of welcome; the unseen spirits; a rain of flowers |
| 5:50 | 25–27 | the Pandavas study and are honoured; Arjuna wins Draupadi at the swayamvara; their conquests |
| 7:00 | 28 | the Rajasuya; Duryodhana sees the wealth and Maya's hall, is mocked, and burns with envy |
| 8:11 | 29 | he grows pale; Dhritarashtra permits the dice; Vasudeva, wroth, lets it run its course, and the war follows |

## Attribution fixes (spot-checked, with overrides)
- **Builder bug fixed (text loss):** an interrupted quote inside a paragraph that opened mid-quotation dropped the
  rest of the paragraph. In ¶23 everything after "'These our pupils" was missing. A sweep of all of Book 1 found **16
  paragraphs** hit (incl. §2 ¶8 at 36 % coverage, §148 ¶2 at 9 %). Now fixed. Every build runs a letter-level
  coverage check (`TEXT LOST?`; 0 across Book 1). Ep 0/Ep 1 scripts are unchanged.
- **¶23 the Munis** → *Rishis of Satasringa* (Naimisha Rishis group voice): "'These our pupils'," / "said they,"
  (Sauti) / "'are as your sons, your brothers, and your friends; they are Pandavas.'" / "Saying this, the Munis
  disappeared." (Sauti).
- **¶24 the citizens' cry** ("They are on all accounts welcome!…", 3 lines): no crowd voice exists, so Sauti reads it
  (joyful; an explicit, flagged choice). Say if you want a crowd voice instead.
- **Draupadi/Krishnaa:** "the virgin Krishna at the swayamvara" (¶27) is spoken as *Draupadi*.
- Everything else is Sauti narration (no other speech in ¶18–29).

## Voices
Sauti (42 lines) and the Rishis of Satasringa (2 lines, Naimisha voice): both exist. **No new voice is needed for
Ep 2.**

## Music (preset A, per-episode cues in `ep02.yaml`, sheet in `ep02.cues.txt`)
| Moment | Time | Cue |
|---|---|---|
| Sauti resumes at Naimisha (¶18) | 0:00 | forest_ashram 0.40 |
| the story in brief | 0:41– | narration_warm 0.35 |
| Pandu's misfortune (the stag) / the divine fathers | 3:20 / 3:47 | grave_drone 0.35 / sacred_solemn 0.45 |
| the Munis present the boys, then vanish | 4:27 | tender_resolve → celestial_swell |
| the citizens' welcome / unseen spirits, rain of flowers | 5:06 / 5:16 | bright_lift 0.60 / celestial_swell 0.70 |
| Draupadi won, conquests (¶27), the Rajasuya opening | 6:21–7:19 | royal_resolve 0.45 |
| the Rajasuya and Duryodhana's envy (¶28) | 7:00– | grave_drone 0.45 |
| the dice and the war (¶29, ending) | 8:11–8:57 | grave_drone 0.55, building to the end |

## Names: pronunciation harness
Harness (`tools/pronunciation/`): carrier "Then {word} spoke again, softly.", Whisper → phoneme/romanisation
similarity; a form is verified when it passes on ≥ 2 distinct voices. This run covered **62 priority Ep 2/Ep 3 terms** (every
recurring or major name) × KMG spelling + one plain-word candidate on **Sauti and Bhishma** (248 clips, 42 min), plus a
round 2 on Vaisampayana/Bhishma for the Ep 2 names that only had retakes (20 clips). **43/62 verified** and written to
`lexicon/book01.tsv` (`spoken` column; detail in `tools/pronunciation/results_2026-10-11_ep02.json`). The KMG spelling
won for most. Respelt where it read better: Arjuna → *Arjoona*, Bhima → *Bheema*, Brahmacharis → *Brahmachaarees*, Draupadi → *Drowpadee*, Duhsasana → *Dushaasana*, Gavalgana → *Guvulgana*, Kripa → *Kripaa*, Magadha → *Mugudha*, Munis → *Moonees*, Nara → *Nahruh*, Narada → *Naaruda*, Narayana → *Naaraayana*, Rishi → *Rishee*, Sakra → *Shakra*, Sakuni → *Shakuni*.

**Episode 2: 39 of 57 names verified.** Not verified, read as the KMG spelling (the fallback):
Asura, Aswins, Brahmanas, Chaidya, Devala, Devas, Dharma, Kshatriyas, Maya, Pitris, Ranku, Sadasyas, Saradwan, Sauti, Suka, Vayu, Vichitra, Yakshas. Of these, *Kshatriyas* was tested (Whisper hears the singular "Kshatriya", a plural quirk, not a
garble); Sauti is the long-standing pending item from the pilot (heard "Saudi"); Brahmanas, Devas, Dharma, Pitris,
Aswins, Yakshas and Suka are already in Ep 0/Ep 1 renders; the rest occur once each (Asura, Chaidya, Devala, Maya,
Ranku, Sadasyas, Saradwan, Vichitra…). No Ep 2 name failed outright. Worth an ear at the render: Drowpadee, Arjoona,
Kshatriyas.

The Ep 0/Ep 1 scripts' spoken text is unchanged by these lexicon additions (no re-render).
