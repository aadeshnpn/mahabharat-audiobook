# Mahabharata Full-Cast Audiobook: Spec & Phased Plan (draft v0.1)

*Draft written Oct 9, 2026 for Aadesh to review. Nothing has been pushed to GitHub. Hard constraints: **open-source only** and **CPU-only inference** (slow is fine). Companion docs: `research-tts.md` (model survey) and `proto/NOTES.md` (what actually ran on the box).*

## 1. Goal
Produce a cinematic, full-cast English audiobook of the KMG translation of the Mahabharata, starting with **Book 1, Adi Parva** (236 sections, about 229k words, roughly 25 h of audio). Every character who speaks more than once gets a unique designed voice. The delivery should feel rooted in ancient India (Indian-English accent and diction) while staying clear and easy to follow.

### Non-goals (for v1)
- Books 2–18 (but the pipeline must generalize to them).
- Translation, abridgement, or modernizing the text. KMG wording is kept verbatim, apart from a reversible normalization layer covering parenthetical glosses and footnotes.
- Real-time or streaming playback.

## 2. Key design decisions (proposed; open to change)
| Decision | Proposal | Why |
|---|---|---|
| Text source | `mahabharata-online.github.io/<book>/<n>.html` → `data/text/bookNN/NNN.txt` | Clean HTML, one file per section, sub-parva header on every page |
| Unit of work | **Section** (1–236). Sub-parvas are chapters in the final M4B | Small enough to re-render; matches the source |
| Voice design | VoxCPM2 voice design (top pick); Qwen3-TTS VoiceDesign, Indic Parler-TTS, or OmniVoice as alternatives or accent anchors | See research-tts.md |
| Rendering | VoxCPM2 *controllable cloning* (ref clip + "(emotion, pace)" instruction); Pocket TTS as the fast fallback | CPU-viable, Apache/MIT |
| Voice identity | A frozen **reference clip** per character (10–20 s) + metadata. Optional per-character LoRA later for the top ~5 voices | Reproducible; cheap to swap engines |
| Narration layers | Sauti (outer frame) → Vaisampayana (inner frame) → characters. Each layer gets its own voice plus subtle acoustic treatment | KMG is literally nested narration |
| "X said," tags | Keep in the narrator's voice, e.g. *"Bhishma said,"* spoken by Vaisampayana, then Bhishma's line in Bhishma's voice. Configurable (`speech_tags: keep|drop`) | Faithful to text; drop mode gives a more radio-drama feel |
| LLM for text analysis | Local or open model for extraction and attribution; manual review gates | Accuracy matters more than speed |
| Determinism | Fixed seeds, versioned voice registry, content hashes per line → cache | Re-render only what changed |

## 2b. Decisions confirmed by Aadesh (Oct 10, 2026)
- The prototype voices, tone and emotion **sound good**. VoxCPM2 design plus controllable cloning stays the main path.
- **"X said," tags stay in the narrator's voice** for now.
- **Sauti and Vaisampayana get separate voices**, one per frame narrator.
- **Personal use for now**: licences are not a constraint yet (re-check before any public release).
- **A hosted LLM is fine** for extraction and attribution (Phases 2, 3 and 5). It needs an API key on the box.
- **Pronunciation is handled with a respelling lexicon, not fine-tuning** (see Phase 1b).

## 3. Pipeline & phases

### Phase 0: Bake-off & tooling (first prototype is done; see proto/NOTES.md)
- Pick the engines by listening tests on 5 characters × 3 emotions: VoxCPM2, Qwen3-TTS, Indic Parler, Pocket TTS.
- Measure CPU RTF on Aadesh's own hardware.
- Exit criteria: engines chosen; accent judged acceptable; a 2-minute end-to-end demo the user approves.

### Phase 1: Ingest & normalize text
- Scrape → `data/raw/book01/*.html` → `data/text/book01/NNN.txt` + `index.json` (**done**: 236 sections).
- Normalization: parenthetical translator glosses such as "Brahmacharya (study and meditation in celibacy)" stay in the script and are omitted from TTS text (`strip_glosses`, global in `configs/duration.yaml`, overridable per episode, segment, or line). A parenthesis that is only a number is spoken. Expand "viz.", fix em-dashes and archaic punctuation.
- Pronunciation lexicon `lexicon/sanskrit.tsv`: name → respelling and/or CMUdict phonemes (VoxCPM2 accepts `{...}` phoneme input). Seed it from a name list, then refine by ear.

### Phase 1b: Pronunciation respelling lexicon (chosen approach; no fine-tuning)
- `lexicon/book01.tsv` columns: `term  respelling  ipa(optional)  source  verified  notes`, e.g. `Vaisampayana  vy-shum-PAA-yuh-nuh`. Seed it from the character `respelling` fields in the character map app, plus places (Hastinapura, Naimisha, Kurukshetra), weapons, rituals and other recurring Sanskrit terms.
- **Render-time substitution**: before TTS, replace each term (whole word, case-preserving, including possessives and plurals) with its respelling in the text sent to the engine only. The script JSON keeps the original KMG text and stores the substituted `tts_text` next to it.
- **ASR verification loop**: render the term in a carrier sentence ("And then <term> spoke.") with 2–3 voices, transcribe with faster-whisper, and score it with (a) a phonetic match against the expected respelling (using double-metaphone or a g2p comparison, because ASR will spell Sanskrit names differently) and (b) a listening queue for anything below threshold. Iterate on the respelling, keeping 1–3 variants per term, and mark the term `verified=1` with the variant that wins.
- Fallback: if a respelling doesn't work for one engine, an engine-specific override column can hold CMUdict phonemes (VoxCPM2 accepts `{...}` phoneme input).
- Tooling: `mbh lexicon build | test | report`. The respelling field is editable in the character map web app.

### Phase 2: Character extraction → `characters.json`
- Pass A (rules): harvest `"<Name> said,"` / `"<Name> continued,"` / `"<Name> replied"` patterns. In Book 1 Vaisampayana has 142, Sauti 59, Janamejaya 24, Saunaka 15, and so on.
- Pass B (LLM, per section): list named entities that **speak**, plus aliases (Devavrata = Gangeya = Bhishma = "son of Ganga"; Partha/Dhananjaya = Arjuna; Vasudeva = Krishna).
- Merge into canonical IDs with an alias table. Count speaking lines and sections. **Recurring** means 2 or more speaking lines (configurable). One-off speakers map to generic pooled voices (e.g. `generic_brahmana_old_m`, `generic_messenger`).
- Manual review checkpoint, since alias resolution errors spread to every later phase.

### Phase 3: Backstories & voice briefs
- For each recurring character: an LLM summarizes their Book 1 appearances, with section citations, into `backstory`, `traits`, `emotional_range`, `age_in_book1`, `social_role` (king, sage, Naga, Gandharva, Asura, Apsara, deity...).
- The LLM then writes a **voice brief**: timbre, pitch, age, pace, texture, accent, plus 3 sample lines from the text, including an emotional one.
- Special classes need deliberate design: deities (Indra, Surya, Ganga), Nagas (Takshaka, Vasuki), Garuda, Rakshasas (Hidimba, Vaka), and ethereal "voice from the sky" (*asariri*) lines, which get post-FX.

### Phase 4: Voice design → voice registry
- For each character, generate K=4–8 candidates from the brief (different seeds and prompt phrasings).
- Auto-filter: an ASR check (WER on the sample line), a speaker-embedding check (distance from all already-cast voices > threshold), and a duration sanity check.
- Human pick (Aadesh), then freeze `voices/<id>/ref.wav` (+ transcript) and write the registry entry.
- Optional: an emotion bank per voice (`ref_angry.wav`, `ref_grief.wav`) produced by cloning the frozen reference with emotion instructions. Pocket TTS needs this, since its emotion comes only from the reference.

### Phase 5: Per-section script (dialogue attribution) → `scripts/book01/NNN.json`
- Split each section into segments: `narration` vs `speech`, with the speaker, the addressee, and the nesting layer.
- KMG quoting is irregular (nested `"…'…'` with missing closers), so use rules first, then an LLM attribution pass that must output JSON with source character offsets so text is never altered. Then validate: concatenating the segments must reproduce the source text after normalization.
- Tag each speech segment with `emotion` (from a fixed vocabulary), `intensity` 0–1, `pace`, and an optional free-text `direction` that maps to the TTS instruction.
- Review UI: a simple HTML/CSV view to spot-check attribution. Target fewer than 2% wrong speakers.

### Phase 6: Rendering
- Render per segment, with long segments split at sentence boundaries (VoxCPM2 docs warn about long-text drift). Cache audio by `hash(text, voice_id, voice_version, instruction, engine, params)`.
- Narration and speech use the same engine. Instruction = `"(<emotion>, <pace>)"`.
- QA per clip: ASR WER threshold (re-roll up to N seeds on failure), clipping and loudness checks, duration-vs-text sanity checks.
- Parallelism: one process per N cores, sharded by section, resumable.

### Phase 7: Cinematic assembly & mastering
- Gaps: about 250 ms between lines of the same speaker, 400–600 ms at speaker changes, 1.5 s at paragraph and scene breaks.
- Acoustic layering: Sauti's frame slightly "present", Vaisampayana a touch warmer, divine or sky voices with reverb. Optional low ambience beds (forest, court, river) and sparse music stings, using royalty-free or self-generated audio only.
- Loudness: −16 LUFS integrated for spoken word (−18 to −20 for Audible-style targets), true-peak ≤ −1 dBTP.
- Output: per-section FLAC masters → per-sub-parva MP3/Opus → a single `book01.m4b` with chapter markers, metadata, and cover.

### Phase 8: Review loop
- Listening checklist per sub-parva covering wrong speaker, mispronunciation, emotional mismatch, and artifacts. Fixes edit the script JSON or lexicon, and the cache makes re-renders incremental.

## 4. Data formats (JSON Schema-ish)

### `characters.json`
```json
{
  "bhishma": {
    "name": "Bhishma",
    "aliases": ["Devavrata", "Gangeya", "son of Ganga", "son of Santanu"],
    "gender": "male", "age_in_book1": "young adult → elder", "kind": "human",
    "first_section": 98, "speaking_lines": 0, "sections": [98, 99, 100],
    "backstory": "...", "traits": ["dutiful", "resolute", "self-sacrificing"],
    "emotional_range": ["calm authority", "solemn resolve", "tender (to Satyavati)"],
    "voice_brief": "A powerful Indian warrior prince in his prime, commanding low voice...",
    "voice_id": "bhishma_v1",
    "notes": "Ages over the book: consider a second voice version for elder Bhishma"
  }
}
```

### `voices/registry.json`
```json
{
  "bhishma_v1": {
    "character": "bhishma", "engine": "voxcpm2", "engine_version": "openbmb/VoxCPM2@32279ef",
    "design_prompt": "...", "seed": 1234, "ref_wav": "voices/bhishma/ref.wav",
    "ref_text": "Hear, O ye kings! ...", "emotion_bank": {"angry": "voices/bhishma/ref_angry.wav"},
    "spk_embedding": "voices/bhishma/spk.npy", "approved_by": "aadesh", "approved_at": "2026-10-10"
  }
}
```

### `scripts/book01/100.json`
```json
{
  "book": 1, "section": 100, "sub_parva": "Sambhava Parva",
  "source_url": "https://mahabharata-online.github.io/1/100.html",
  "segments": [
    {"id": "100-0187", "type": "narration", "speaker": "vaisampayana", "layer": 2,
     "text": "O king, the son of Ganga, devoted to truth, ... then said,",
     "src_span": [10234, 10398], "emotion": "neutral", "pace": "measured"},
    {"id": "100-0188", "type": "speech", "speaker": "bhishma", "addressee": "dasa", "layer": 3,
     "text": "Chief of fishermen, thou best of men, listen to what I say...",
     "emotion": "solemn_resolve", "intensity": 0.8, "pace": "slow",
     "direction": "a sacred vow before assembled kings"}
  ]
}
```
Emotion vocabulary (v1): `neutral, warm, solemn, solemn_resolve, joyful, angry, contemptuous, grief, fear, pleading, surprised, tender, commanding, mocking, awed`.

### Render manifest `build/book01/100.manifest.json`
Per segment: `audio_path, cache_key, engine, params, seed, rtf, asr_text, wer, status`.

## 5. Proposed repo layout (`aadeshnpn/mahabharat-audiobook`)
```
mahabharat-audiobook/
├── README.md, PLAN.md, docs/research-tts.md
├── pyproject.toml               # uv; extras: [voxcpm], [pocket], [qwen], [llm]
├── configs/
│   ├── book01.yaml              # sections, speech_tags, gaps, loudness, engine choice
│   └── engines/{voxcpm2,pocket,qwen3}.yaml
├── src/mbh/
│   ├── ingest/      scrape.py, extract.py, normalize.py
│   ├── characters/  harvest_rules.py, llm_extract.py, merge_aliases.py, backstory.py
│   ├── voices/      design.py, select.py (ASR + spk-embed filters), registry.py
│   ├── script/      segment.py, attribute.py (LLM), emotion.py, validate.py
│   ├── tts/         base.py (Engine interface), voxcpm2.py, pocket.py, qwen3.py
│   ├── render/      render_section.py, cache.py, qa.py
│   ├── assemble/    mix.py, fx.py, master.py, m4b.py
│   └── cli.py       # `mbh ingest|characters|design|script|render|assemble --book 1 --sections 98-100`
├── lexicon/sanskrit.tsv
├── data/            # gitignored except index.json
│   ├── raw/book01/*.html, text/book01/*.txt
├── characters/book01.json
├── voices/registry.json, voices/<id>/ref.wav      # small clips: commit, or Git LFS
├── scripts/book01/*.json                            # reviewed attribution: commit
├── build/                                           # gitignored renders/cache
└── tests/  (text round-trip, schema validation, engine smoke tests)
```

## 6. Milestones
1. **M0**: Bake-off done, engines chosen, demo approved (prototype in `proto/`).
2. **M1**: Ingest + lexicon v0 + `characters.json` for Book 1 reviewed.
3. **M2**: Voice briefs + designed voices for the top ~30 speakers + generic pool approved.
4. **M3**: Scripts for sub-parvas Paushya–Astika (sections 3–58) attributed and spot-checked; first sub-parva rendered and mastered.
5. **M4**: All 236 sections scripted and rendered; full listening pass.
6. **M5**: `book01.m4b` released (internally); retrospective; generalize to Book 2.

## 7. Open questions for Aadesh
See the end of `proto/NOTES.md`.

## 8. Episode pipeline (text-only pilot, Oct 10)

The unit of listening is an **episode**, not a whole section. A normal episode is 15–20 minutes and must end on a complete turn. The pilot targets about 5 minutes.

`episodes/<id>.yaml` lists `target_duration_s`, `speech_tags`, the lexicon and timing files, and ordered segments:

- `kind: section` — a section number and an inclusive `paragraphs: [start, end]`, with the frame `narrator`. `excerpt: true` marks a selection taken out of reading order (the pilot cold open).
- `kind: bridge` — narrator text that is not in KMG. `non_kmg: true` is required, and the flag is copied onto every line.

`mbh episode build` writes `episodes/<id>.script.json` and `episodes/<id>_script.md`. Each line has `speaker`, `voice_id`, `type` (`narration` or `speech`), `emotion`, `pace`, original `text`, `tts_text` (after `krishna.speakable` and the lexicon), and `section` / `paragraph`. Attribution is rule-based from the existing "X said," tags, with a callable hook for a later LLM pass. `episodes/overrides/<id>.json` reapplies human speaker, emotion, pace, and direction edits after every rebuild.

`lexicon/book01.tsv` is the Phase 1b file (`term`, `respelling`, `ipa`, `source`, `verified`, `notes`). Substitution is whole-word, longest match first, and touches TTS text only. `verified` is still 0. Parenthetical glosses are stripped from that same TTS text (`strip_glosses: true` on the pilot). The quoted KMG line is unchanged. `mbh episode breaks` proposes legal end points near the target (complete sentence, not mid-dialogue, preferably a question or a paragraph boundary). Duration uses `configs/duration.yaml` (160.9 wpm from the §100 prototype). `mbh episode render` and `assemble` are the Phase 6–7 interface: VoxCPM2 on CPU, cache key per line, gaps and loudness from the same timing file. No audio is rendered in CI.

CLI: `mbh episode build|estimate|breaks|render|assemble|export-script`.

## 9. Status
- **Oct 10 (episode pipeline):** text-only pilot at `episodes/ep00_pilot.yaml`. Cold open is Book 1 §100 ¶10–11 (Bhishma's vow, Vaisampayana), then a two-sentence non-KMG bridge in Sauti's voice, then §1 ¶1–5. Estimated **5 min 38 s** (337.8 s, 34 lines) at 160.9 wpm, with parenthetical glosses omitted from the spoken line. It ends at §1 ¶5, when the Rishi finishes asking for the Bharata; the nearest shorter legal break is §1 ¶4 at about 4:38. Lexicon v0 is `lexicon/book01.tsv`. Render and assemble are implemented and unrun. See the README "Episodes" section.
- **Oct 10:** character map web app merged (FastAPI + SQLite + Cytoscape.js). Seed is the text-grounded `characters/book01.json` (164 characters). The 8 prototype voices are attached. See README.

### Oct 9
- Phase 0: first CPU bake-off done. VoxCPM2 design + controllable cloning rendered a full-cast 100 s excerpt of 1:100 end to end (RTF 3.0 on the box; WER ~5%; 13/13 speaker identity). Samples are in `samples/`.
- Phase 1: Book 1 downloaded (`data/raw/book01/*.html`) and extracted (`data/text/book01/NNN.txt` + `index.json`, 236 sections, 228,772 words post-cleanup). Extractor: `extract_book.py`.
