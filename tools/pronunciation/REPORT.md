# Pronunciation harness: respelling format for VoxCPM2 (2026-10-10)

## Problem
The lexicon's stress-marked guide respellings (`VAY-duhs`, `UP-suh-rahs`, `DAY-vuh-VRAH-tuh`) went straight
into TTS text. VoxCPM2 reads CAPS chunks as letters ("V.A.Y. does", "S.O.T.") or garbles them
("Yupi Saharaz", "Devu Vrayafthu"). In the v1 first minute, Whisper WER was 11.5 %, almost all on names.

## Method (`tools/pronunciation/`)
* `words.tsv`: the 41 lexicon terms used in the pilot, an intended pronunciation (ARPAbet, Sanskrit-ish,
  stress-free) and hand-made plain-word candidates.
* `jobs.py` → `synth.py`: each candidate form in the carrier "Then {word} spoke again, softly.", cloned with the
  episode renderer's own `VoxCPM2Backend` (10 steps, "(warm, measured pace)" prefix, normalised voice refs).
* `score.py`: faster-whisper small.en → words between the anchors → (a) phonemes via CMUdict / g2p_en vs the
  intended ARPAbet over coarse classes (`mbh.episode.pronounce.phoneme_similarity`), (b) a romanised-Sanskrit
  sound key (`roman_key`), take the max; letter spell-outs detected separately. Take passes at sim >= 0.8 (or
  ASR wrote the term itself), not spelled out. Clips where the carrier itself failed are *retakes*, not fails.
* `select.py`: a form is **verified** when it passes on >= 2 distinct voices, >= 2/3 of its conclusive takes pass,
  and no take is spelled out. Ties prefer the KMG spelling. CAPS/hyphen forms are never eligible.

Round 1: 41 terms x 5 formats on Sauti (205 clips, 49 min). Round 2: the top forms plus new variants on
Vaisampayana and Bhishma (120 clips, 21 min); priority to the names in lines 0001-0011.

## Format results (round 1, Sauti, 41 terms)
| format | example | pass | spelled out |
|---|---|---|---|
| caps-hyphen guide (old) | `VAY-duhs` | 12/41 | **6** |
| KMG spelling | `Vedas` | 25/41 | 0 |
| auto: lowercase, joined, capitalised | `Vayduhs` | 23/41 | 0 |
| plain-word candidate 1 | `Vaydas` | 26/41 | 0 |
| plain-word candidate 2 | `Vaidas` | 18/41 | 1 |
~20-30 % of takes in every format were retakes (VoxCPM2 instability on ~2 s carriers), so no single take decides.

## Chosen format
**Ordinary-looking words: no caps, no hyphens; the KMG spelling where it already reads right, a plain phonetic
spelling (stress carried by vowel spelling, e.g. `Naaraayana`, `Moonee`, `Shownuhkuh`) only where it does not.**
VoxCPM2 already pronounces most Sanskrit names well from the romanisation; the guide respelling stays in the
lexicon for humans (`respelling` column) and the engine reads the new `spoken` column. Unverified rows fall back
to the KMG spelling (`lexicon.FALLBACK = "term"`), never the guide.

## Verification (final, 3 voices)
40 / 41 pilot terms verified. KMG spelling kept for 29, including every name in lines 0001-0011 (Vaisampayana,
Ganga, Brahmacharya, Apsaras, Rishis, Devavrata, Bhishma: each 3/3 voices). Respelt (11): Rishi→Rishee,
Narayana→Naaraayana, Nara→Nahruh, Saraswati→Saraswathi, Kulapati→Koolapati, Puranas→Poorahnuhs,
Saunaka→Shownuhkuh, Muni→Moonee, Munis→Moonees, Dwijas→Dweejuhs, Parikshit→Puhrikshit.
**Pending: Sauti** (heard "Saudi" / "Sautee" / "Soty"; English ASR hears the unaspirated t as d and has no prior
for the word). KMG spelling used; needs a listening check. The other 157 lexicon rows (not in the pilot) are unverified and use the fallback.
Per-term detail: `results_2026-10-10.json`.

## Effect on the first minute (lines 0001-0011)
Whisper WER 11.5 % (v1) → 6.1 % (v2); all seven names transcribed verbatim (v1: "Vishum Peyayonu",
"Yupi Surahs", "Devu Vrayafthu", "Brahmisharyu"). A/B clips: `samples/pronunciation_ab/`.

## Reproduce
```
PYTHONPATH=src .venv/bin/python tools/pronunciation/jobs.py r1 sauti > build/pron_r1_jobs.json
PYTHONPATH=src proto/.venv-vox/bin/python tools/pronunciation/synth.py build/pron_r1_jobs.json
PYTHONPATH=src proto/.venv-pocket/bin/python tools/pronunciation/score.py build/pron_r1_jobs.json   # needs g2p_en + cmudict
.venv/bin/python tools/pronunciation/select.py --json build/pron/select.json
```
Do not run synth and score at the same time on the 8-core box (each takes all cores; both slow down ~5x).
