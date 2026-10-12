# mahabharat-audiobook

A full-cast cinematic audiobook of the Mahabharata (KMG English translation), built with open-source TTS on CPU only. Book 1 (Adi Parva) is the first target.
See `PLAN.md` for the spec and phases, `research-tts.md` for the model survey, and `proto/NOTES.md` for prototype results.

> **Run it on your own machine:** [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) (Linux, CPU only: `scripts/setup.sh`, then
> `scripts/smoke_test.sh`). **Make an episode:** [docs/EPISODE_WORKFLOW.md](docs/EPISODE_WORKFLOW.md)
> (`scripts/render_episode.sh episodes/ep01.yaml --qa`). Approved voices: [voices/registry.json](voices/registry.json).

## Episodes

An episode is a YAML spec. `mbh episode build` turns it into a line-level script: speaker, emotion, pace, the original KMG wording, and the TTS text after Krishna→Draupadi resolution and the pronunciation lexicon. The same command writes a Markdown script for review. Audio rendering is optional and is not run in tests.

```bash
PYTHONPATH=src python3 -m mbh.cli episode build episodes/ep00_pilot.yaml
PYTHONPATH=src python3 -m mbh.cli episode estimate episodes/ep00_pilot.yaml
PYTHONPATH=src python3 -m mbh.cli episode breaks episodes/ep00_pilot.yaml
PYTHONPATH=src python3 -m mbh.cli episode export-script episodes/ep00_pilot.yaml
# audio, only when VoxCPM2 is installed (see proto/.venv-vox):
PYTHONPATH=src python3 -m mbh.cli episode render episodes/ep00_pilot.yaml
PYTHONPATH=src python3 -m mbh.cli episode assemble episodes/ep00_pilot.yaml
```

`pip install -e .` also installs the `mbh` console script (`mbh episode …`).

- **Spec** (`episodes/<id>.yaml`). Segments are `section` (a section plus an inclusive paragraph range; `excerpt: true` marks a selection) or `bridge` (added narrator text, `non_kmg: true`). `speech_tags` is `keep` or `drop`.
- **Script** (`episodes/<id>.script.json`) and **review Markdown** (`episodes/<id>_script.md`). Each line has speaker id, voice id, emotion, pace, original text, TTS text, and section/paragraph refs. Bridges and abridgements are flagged.
- **Overrides** (`episodes/overrides/<id>.json`). A match on section, paragraph, and a text snippet (speaker, emotion, pace, direction, fx, `strip_glosses`, or a full `tts_text`) is reapplied on every rebuild.
- **Glosses.** Parenthetical translator glosses stay in the KMG line and are removed from TTS text. The global switch is `strip_glosses` in `configs/duration.yaml` (default on). An episode, a segment, or a line override can turn it off. A parenthesis that is only a number, such as "(three)", is spoken.
- **Lexicon** (`lexicon/book01.tsv`: `term`, `respelling`, `ipa`, `source`, `verified`, `notes`, `spoken`). Whole-word substitution, longest match first, including possessives and a trailing plural *s*. Applied only to TTS text. `respelling` is the human guide (stress in caps); the engine reads `spoken`, a harness-verified plain form (VoxCPM2 spells caps chunks out as letters). Rows without one fall back to the KMG spelling, never the guide. Refresh the character-registry rows with `PYTHONPATH=src python3 -m mbh.episode.lexicon` (hand-written rows and harness results are kept).
- **Pronunciation harness** (`tools/pronunciation/`, see `REPORT.md`). Each candidate form in a carrier sentence on 2-3 cloned voices, Whisper ASR, phoneme + romanised-key similarity, letter spell-out detection; `select.py` writes verified forms. 40 of the pilot's 41 lexicon terms are verified (Sauti pending a listening check).
- **Loudness** (`src/mbh/episode/loudness.py`, ITU-R BS.1770 / libebur128 K-weighting and gating, no dependencies). `assemble` brings every line to `loudness.integrated_lufs` (lines under 1.5 s use calibrated 100 ms gating), then masters the episode to the same target with a peak limiter at `true_peak_db` − 0.5 dB and re-measures until within 0.1 LU. The report lists per-line and per-speaker loudness before/after. `python -m mbh.voices.normalize_refs` levels the voice reference clips (−20 LUFS; VoxCPM2's clone level follows the reference), keeping `ref_replaced_*_prenorm.wav` backups.
- **Duration** (`configs/duration.yaml`). 138.1 words per minute, fitted on the full ep00 pilot render (34 lines, 734 words; predicts 337.9 s vs 337.9 s rendered). The earlier 160.9 came from the §100 prototype, rendered without the instruction prefix. Gaps: 0.25 s for the same speaker, 0.50 s on a speaker change, 1.50 s at a paragraph or segment boundary.
- **Render cache** (`build/cache/voxcpm2/<hash>.wav`, gitignored). The key is the TTS text, the instruction, the voice file, and the engine settings, so a rebuild re-synthesizes only changed lines.

The pilot (`episodes/ep00_pilot.yaml`) is text only. It cold-opens on Bhishma's vow (Book 1 §100 ¶10–11, unabridged inside that span), then a two-sentence non-KMG bridge in Sauti's voice, then §1 ¶1–5 from the invocation. Rendered length is **5 min 38 s** (337.9 s, 34 lines; `samples/ep00_pilot_full_v1.mp3`, −16 LUFS). QA: `python tools/qa_episode.py episodes/ep00_pilot.script.json episodes/ep00_pilot.render.json` (per-line Whisper WER, names, speaker identity, cut-offs, silences). Parenthetical glosses are not spoken. It ends when the Rishi of Naimisha finishes asking for the Bharata. Sauti's reply begins at §1 ¶6.

### Music (line-driven, under the dialogue)

Music cues are chosen **per line** from the script's own tags, so any new episode gets a score automatically: `configs/music.yaml` maps emotion → cue/intensity (e.g. `solemn_resolve` → grave low Sa–Pa drone, `joyful` → a brief santoor-like lift, `awed` → celestial swell, `tender` → soft Sa–Ga pad resolving to Sa), and ordered scene rules match text, speaker, segment, paragraph, fx or neighbouring emotions (Om → temple bell over tanpura; the gods' voice → full celestial swell; Sauti at Naimisha → forest ashram with birds only in pauses; the Rishis' request → reverent anticipation that rises into a 4 s tail as the ending hook). Speech tags ("Sauti said,") inherit the next line's cue. Per-line override: add `"music": "<cue>" | "none" | {"cue": ..., "intensity": ...}` to an overrides row. All cues are synthesised on CPU around one tonic (Sa = D3); no model or samples needed (`pip install .[music]` for numpy/scipy).

Dialogue protection is built in: beds duck 8 dB under every line (120 ms look-ahead), the music bus has a wide −8 dB dip at 1.6 kHz, stings and birds sit in pauses, and a hard per-line floor (`min_speech_to_music_db: 18`) turns the music down locally if any line would come closer.

    mbh episode cues episodes/ep00_pilot.yaml            # cue sheet: line -> cue, intensity, why (rule/emotion/override)
    mbh episode assemble episodes/ep00_pilot.yaml --music [--music-stem stem.wav]
    python tools/qa_music.py SCRIPT.json REPORT.json MIX.wav DRY.mp3 [STEM.wav]   # A/B: WER and voice ID dry vs mixed

Level presets live in `configs/music.yaml` (`preset: A` is the default; choose per episode with `music_preset:` or per run with `--music-preset`):

| preset | bed | duck | speech-to-music floor | pause bloom | accent at key cues |
|---|---|---|---|---|---|
| quiet (v1) | −26 LUFS | 8 dB | 18 dB | 0 | 0 |
| **A** (default) | −21 LUFS | 6 dB | 14 dB | +3 dB | +2.5 dB |
| B | −17 LUFS | 5 dB | 12 dB | +4 dB | +3.5 dB |

Pause bloom lifts the music in paragraph/segment pauses (≥ 0.9 s); `accent` (per cue) raises the vow drone, celestial swell, invocation and ending. The speech-band dip stays on in every preset. Pilot mixes: `samples/ep00_pilot_full_v2_music_A.mp3` and `_B.mp3` (−15.9 LUFS); cue sheet `episodes/ep00_pilot.cues.txt`. Music is off unless `--music` or `music: true` in the episode YAML.

Render cache keys use a content hash of each voice reference (not its mtime), so checkouts do not trigger re-renders.

```bash
PYTHONPATH=src python3 -m pytest -q tests/test_episode.py tests/test_lexicon.py tests/test_render_assemble.py tests/test_loudness.py tests/test_pronounce.py
```

## Character Map web app
A local web app for mapping every recurring Book 1 character. It has:
- an interactive **relationship graph** (Cytoscape.js) with parent, foster-parent, spouse, sibling, teacher, ally, enemy, rival, guardian, curse, slew, incarnation-of, service and narration edges, each with a § reference; nodes are coloured by kind (human, sage, deity, celestial, naga, asura, rakshasa, bird, animal, chorus);
- **profiles** for each character: aliases, a TTS respelling, gender, kind + kind detail, era/age, role, backstory with § citations, personality, emotional range, voice brief, sections appeared in, speech turns per section, a shared `voice_group` (if any), flags (`single_section_speaker`, `chorus`, `non_speaking`) and a **provenance** badge (`text-extracted`, `hand`, or `text-extracted+hand-edited` once saved from the UI);
- **voice**: play the reference clip, edit the design prompt and sample line, attach or replace a clip (old clips are kept as `ref_replaced_*`), list candidates and pick one as the reference, and **generate a candidate from the brief** with VoxCPM2 on CPU as a background job;
- full **CRUD** for characters and relationships, plus JSON **import/export** and a REST API (Swagger docs at `/docs`).

### Run
```bash
cd /workspace/mahabharat
uv venv --python 3.12 .venv && VIRTUAL_ENV=.venv uv pip install fastapi "uvicorn[standard]" python-multipart pydantic
# 1) (re)build characters/book01.json from the text-grounded profiles (validates every § citation; ~4 s)
PYTHONPATH=src .venv/bin/python -m mbh.characters.build_extracted --write
# 2a) first time only: seed an empty DB and attach the prototype voices
PYTHONPATH=src .venv/bin/python -m mbh.webapp.seed
# 2b) afterwards: re-seed while keeping voices, prompts and UI edits (stop the server first)
PYTHONPATH=src .venv/bin/python -m mbh.webapp.reseed
# 3) serve
PYTHONPATH=src .venv/bin/uvicorn mbh.webapp.app:app --app-dir src --host 0.0.0.0 --port 8765
```
Open http://localhost:8765 (the REST API docs are at http://localhost:8765/docs).

"Generate candidate" needs the VoxCPM2 environment. It defaults to `proto/.venv-vox/bin/python`; point `MBH_VOX_PYTHON` elsewhere to override. A job takes about 1–2 minutes on an 8-core CPU, including ~20 s of model load, and uses ~7 GB of RAM. Jobs run one at a time.

Environment variables: `MBH_DB` (SQLite path, default `data/mbh.sqlite3`), `MBH_VOX_PYTHON`.

### REST API (summary)
| Method | Path | |
|---|---|---|
| GET | `/api/characters?q=&kind=` | list or search |
| POST | `/api/characters` | create (id is slugified from the name unless given) |
| GET / PUT / PATCH / DELETE | `/api/characters/{id}` | read (includes relationships) / replace / partial update / delete (relationships cascade; `?delete_voice_files=true` also removes the files) |
| GET / POST | `/api/relationships` (`?character=`) | list / create `{source,target,type,label,notes}` |
| PUT / DELETE | `/api/relationships/{rid}` | update / delete |
| GET | `/api/graph` | Cytoscape elements |
| POST / DELETE | `/api/characters/{id}/voice` | upload (multipart `file`) or replace the reference clip / detach it |
| GET | `/api/characters/{id}/voice/candidates` | candidate clips |
| POST | `/api/characters/{id}/voice/select` | `{file}`: make a candidate the reference |
| POST | `/api/characters/{id}/voice/generate` | `{prompt?, text?, steps?}`: queue a VoxCPM2 design job (202) |
| GET | `/api/jobs?character=`, `/api/jobs/{jid}` | job status |
| POST | `/api/import?mode=merge\|replace` | import a JSON body `{characters:[...], relationships:[...]}` |
| POST | `/api/import/seed?mode=merge\|replace` | re-import `characters/book01.json` |
| GET | `/api/export[?save=true]` | export JSON (download, or save to `characters/book01.export.<ts>.json`) |
| GET | `/api/meta` | relationship types and colours, kinds, voice-generation availability |

Note: a `merge` import updates the fields that are present in the file. Fields the file doesn't mention, such as voice clips and prompts, are left alone. Fields it does mention overwrite edits made in the UI. Use `mbh.webapp.reseed` instead of `/api/import/seed` when the DB holds work you want to keep.

### Re-seeding safely (`mbh.webapp.reseed`)
1. Exports the DB to `characters/backups/db_export.before_reseed.<ts>.json`.
2. Replaces characters and relationships with `characters/book01.json`.
3. Restores voice fields (`voice_clip`, `voice_prompt`, `sample_line`, `voice_engine`, `voice_notes`) for every id that still exists.
4. Detects UI edits by comparing the DB with the file it was last seeded from (`characters/backups/last_seed.json`, rewritten on every re-seed). Edited fields win and provenance becomes `text-extracted+hand-edited`.
5. Re-adds characters and relationships that were created in the UI.
An explicit baseline can be passed as the first argument; it must be the exact file the DB was seeded from, otherwise ordinary data changes look like UI edits.

### Tests
```bash
VIRTUAL_ENV=.venv uv pip install pytest httpx playwright
.venv/bin/python -m pytest -q tests          # API: CRUD, cascade, voice upload/replace, import/export, extracted fields, reseed preservation (temp DB)
.venv/bin/python tests/e2e_ui.py              # headless UI CRUD + graph checks against a running server; writes screens/*.png
```

## Where the character data comes from
`characters/book01.json` is a **text-grounded extraction** of Book 1. The profiles were written from a reading of the KMG text (`data/text/book01/`), with § citations. See `characters/EXTRACTION_REPORT.md` for counts, method and open decisions.
- `src/mbh/characters/extracted/part1..5.py` hold the profiles and `rels.py` the relationships. Each relationship has a type and a § reference.
- `src/mbh/characters/build_extracted.py` computes, from the text:
  - mentions and the sections each character appears in, with alias disambiguation (e.g. bare "Krishna" → Vasudeva, Draupadi or Vyasa per occurrence via `mbh.text.krishna`; the two Hidimvas and the two Jaratkarus split by pronouns);
  - speech turns: "X said," tags plus quote-anchored attribution;
  - flags.
  It then checks that every cited section actually mentions the character (or a listed epithet) and fails loudly on any mismatch. It also writes the resolved and unresolved generic speaker tags (`characters/book01_unmapped_speakers.json`).
- `work/factcheck.py` runs keyword checks on specific factual claims in the backstories.
- `src/mbh/text/krishna.py` resolves every bare "Krishna" to Vasudeva, Draupadi or Vyasa. `speakable()` returns the TTS text, saying "Draupadi" where the text means her (decision 2026-10-10).
- **Display names follow the decisions of 2026-10-10:** Balarama and Chitraratha are shown, with the KMG forms Valadeva and Angaraparna kept as aliases. Rishi groups (Satasringa, the Valakhilyas) share the Naimisha Rishis voice via the `voice_group` field.
- The old provisional starter set (`starter_book01.py` + `harvest.py`) is kept for reference only. **Running `harvest` overwrites book01.json with the starter set.** Backups are in `characters/backups/`.

## Layout
```
src/mbh/characters/   extracted/ profiles + build_extracted.py (counts, citation checks); legacy starter + harvest
src/mbh/episode/      spec, attribution, lexicon apply, duration, breaks, render, assemble
src/mbh/cli.py        `mbh episode build|estimate|breaks|render|assemble|export-script`
src/mbh/webapp/       FastAPI app, SQLite store, seed + reseed, static UI (vendored Cytoscape.js)
src/mbh/voices/       design_one.py (VoxCPM2 CPU voice design, used by the web app jobs)
episodes/             episode YAML, overrides, generated script JSON and review Markdown
lexicon/              book01.tsv (respellings applied only to TTS text)
configs/              duration.yaml (words per minute, gaps, loudness, engine defaults)
characters/           book01.json (seed), EXTRACTION_REPORT.md, speaker resolution list, backups/
voices/<id>/          ref.wav (reference clip), candidates/, ref_replaced_* history
data/                 raw HTML + clean text (data/text/book01), SQLite DB
proto/                CPU TTS prototype (scripts, venvs, logs, NOTES.md)
samples/              listening samples; screens/ UI screenshots
extract_book.py       scrape output → clean section text
```
