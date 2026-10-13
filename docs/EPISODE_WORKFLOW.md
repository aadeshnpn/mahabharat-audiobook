# Making an episode, end to end

Setup first: [LOCAL_SETUP.md](LOCAL_SETUP.md). Shorthand used below:

```bash
export PYTHONPATH=src MBH_VOX_PYTHON=proto/.venv-vox/bin/python
APP=.venv/bin/python; VOX=proto/.venv-vox/bin/python; QA=proto/.venv-pocket/bin/python
```

The whole render half is one command: `scripts/render_episode.sh episodes/epNN.yaml --name epNN_full_v1 --qa`.
The steps below explain each stage and the review loop around it.

The same stages are in Episode Studio, on the character-map server: [STUDIO.md](STUDIO.md).

```bash
PYTHONPATH=src .venv/bin/python -m mbh.webapp    # http://127.0.0.1:8765/studio  (binds to localhost, no login)
```

| Step below | Studio |
|---|---|
| 1. Pick the span | New episode: section, paragraph range, target, music preset. Estimate and Suggest endings call the same duration model and break suggester. |
| 2. Build and review | Creating the episode builds the script. The line table is the Markdown review, one row per line. |
| 3. Overrides | Save on a row writes `episodes/overrides/<id>.json` and rebuilds. Split and merge are on the row. |
| 4. Lexicon | Lexicon page: edit `spoken`, queue a pronunciation test, play it, mark verified. |
| 5. Voices | Voices page, or the map's Voice tab: design candidates from the brief, audition, pick the reference. WER and clone tests stay on the command line. |
| 6–8. Render, assemble, QA | Script page buttons. One job at a time. The player seeks by line; QA flags show on the timeline. |

An agent uses the same routes with curl. The full create → build → review → render → assemble → QA sequence is in [STUDIO.md](STUDIO.md#agent-usage). OpenAPI is at `/docs`.

## House style (decisions already made, apply to every episode)

* **Text:** unabridged KMG (Kisari Mohan Ganguli), in order. Text is never paraphrased. Added narrator text is only
  allowed as a `bridge` segment marked `non_kmg: true`. List-like passages are kept unless the user decides otherwise
  (Ep 1 kept §1 ¶9, the generations of the gods).
* **Glosses stripped:** translator parentheses ("(the sacred tradition)") stay in the script text but are not spoken
  (`strip_glosses: true`). A parenthesis that is only a number is spoken.
* **Said-tags kept:** "Sauti said," and similar tags are read by the narrator (`speech_tags: keep`); the quote after
  them is voiced by the speaker.
* **Narrative layers:** Sauti narrates the outer frame (layer 1), Vaisampayana the inner recital (layer 2), and
  everyone else is a character (layer 3). Each has its own approved voice.
* **Names:** display Valadeva as **Balarama** and Angaraparna as **Chitraratha** (KMG forms kept as aliases). When
  "Krishna" means Draupadi, the speaker and display name are **Draupadi**, and the TTS text says "Draupadi"/"Krishnaa",
  never "Krishna".
* **Voice groups:** group speakers share one voice via `voice_group`, e.g. the Satasringa Rishis and Valakhilyas speak
  with the **Naimisha Rishis** voice (a single aged sage, no chorus effect). The Devas have their own chorus voice.
* **Voices:** every voice is a VoxCPM2 design from a text-grounded brief, chosen by ASR intelligibility + distinctness
  + clone tests, approved by Aadesh by ear, leveled to **-20 LUFS** at `voices/<id>/ref.wav`, and recorded in
  `voices/registry.json`.
* **Loudness:** every line is normalized to **-16 LUFS** before joining, then the episode is mastered to **-16 LUFS
  integrated, -1 dBTP true-peak**. MP3s are re-measured after encoding (`tools/encode_mp3.py`).
* **Music:** on by default, **preset A** (bed -21 LUFS, 6 dB duck, pause bloom). B is louder and `quiet` is the
  original subtle mix. Speech must stay at least 14 dB above the music (A) inside dialogue, with a speech-band EQ carve.
* **Pronunciation:** names use the KMG spelling unless the harness proves a plain-word respelling reads better.
  All-caps or hyphenated respellings are never sent to TTS (VoxCPM2 spells them out).
* **Duration:** target 15–20 min per episode (estimate model 138 wpm incl. pauses), ending at a natural break
  (a narration boundary or a scene change, not mid-dialogue).

## 1. Pick the span and write the episode YAML

```bash
$APP -m mbh.cli episode breaks --section 1 --start-paragraph 18 --target-seconds 1050   # candidate end points
```

Create `episodes/ep02.yaml` (copy `episodes/ep01.yaml`):

```yaml
id: ep02
title: "Episode 2: ..."
book: 1
target_duration_s: 1050
speech_tags: keep
narrator_default: sauti
timing: configs/duration.yaml
lexicon: lexicon/book01.tsv
overrides: episodes/overrides/ep02.json
strip_glosses: true
music: true                 # or a path to another cue YAML; music_preset: B to override the default
music_rules:                # optional, episode-specific; prepended to configs/music.yaml rules
  - {name: example, match: {section: 1, paragraph: 20}, cue: grave_drone, intensity: 0.5}
segments:
  - {id: s1, kind: section, section: 1, paragraphs: [18, 25], narrator: sauti, label: "..."}
summary: >
  ...
end_reason: >
  why this is a natural break
```

Text comes from `data/text/book01/NNN.txt` (one file per KMG section, paragraph per line block).

## 2. Build and review the script

```bash
$APP -m mbh.cli episode build episodes/ep02.yaml      # -> episodes/ep02.script.json + episodes/ep02_script.md
$APP -m mbh.cli episode estimate episodes/ep02.yaml   # duration by segment
$APP -m mbh.cli episode cues episodes/ep02.yaml       # per-line music cue sheet (no audio) -> save as episodes/ep02.cues.txt
```

Read `episodes/ep02_script.md`. Each line shows speaker, emotion, pace, direction and TTS text. The builder's warnings list
unresolved speakers and names missing from the lexicon. Write review notes like `episodes/ep01_REVIEW.md`.

## 3. Fix lines with overrides (`episodes/overrides/<id>.json`)

Each row matches `section` + `paragraph` + a `contains` snippet and is reapplied on every rebuild:

```json
{"overrides": [
  {"section": 1, "paragraph": 12, "contains": "Let Ganesa be thought of", "emotion": "commanding"},
  {"section": 1, "paragraph": 11, "contains": "no writer of this work", "emotion": "pleading",
   "direction": "a poet with a finished masterpiece and no one to write it down"},
  {"section": 1, "paragraph": 3, "contains": "Puranas", "tts_text": "exact words to speak"},
  {"section": 1, "paragraph": 14, "contains": "Ganesa", "music": "bright_lift"},
  {"section": 1, "paragraph": 5, "contains": "Whence comest thou", "take": 2},
  {"section": 1, "paragraph": 13, "contains": "Vyasa addressed him thus", "merge_next": true},
  {"section": 1, "paragraph": 14, "contains": "provided my pen", "split": [
     {"text": "I will become the writer of thy work, provided my pen do not for a moment cease writing.",
      "speaker": "ganesa", "type": "speech", "emotion": "warm"},
     {"text": "And Vyasa said unto that divinity,", "type": "narration"}]}
]}
```

Fields: `speaker`, `emotion` (see `configs/duration.yaml` emotions), `pace`, `intensity`, `direction` (free text added
to the TTS instruction), `fx`, `strip_glosses`, `tts_text` (spoken words only; the KMG `text` is untouched),
`addressee`, `type`, `flags_add`, `music` (`"<cue>"`, `"none"`, or `{"cue": ..., "intensity": ...}`), and `take`
(retake: N>0 seeds the TTS with N and gives the line its own cache entry, so a bad render can be redone
reproducibly). Structural: `merge_next` joins a line with the next one; `split` replaces a line with parts that must
re-join to the original text (the builder checks this). Use them for nested quotes and speech inside narration.

Matching: a row matches on `section`, `paragraph`, `segment_id`, `type` and `contains`/`match`. A row with no
`contains` matches the whole paragraph, and a row that matches several lines needs `"apply_all": true` (e.g. give a
whole nested-quote speech to its speaker). In a field row `type` is a **filter**. Use `set_type`
(`narration`/`speech`) to change a line's type. Setting `speaker` (even to the narrator) marks the line
`speaker_confirmed` and clears the "speaker unresolved" warning.

**Text coverage check:** every build compares each KMG paragraph of a `section` segment, letter by letter, with the
script lines. A `§S ¶P: TEXT LOST?` warning means the attributer dropped words (an unabridged episode must never ship
with one). Fixed in Ep2 work: an interrupted quote inside a paragraph that opened mid-quotation (`'These our pupils',
said they, '...'`) used to drop the rest of the paragraph (16 paragraphs in Book 1).

**Audition a new voice on real lines:** `PYTHONPATH=src proto/.venv-vox/bin/python tools/audition.py episodes/ep03.yaml
samples/voices_ep03_audition.mp3 ep03-0007,ep03-0084 ep03-0105,ep03-0111` (each comma group is one speaker block;
lines go through the episode renderer and cache, so the full render reuses them).

## 4. Names: lexicon + pronunciation harness

`lexicon/book01.tsv` columns: `term, respelling (human guide), ipa, source, verified, notes, spoken`. Only `spoken`
reaches TTS. New names from the build warnings get a row with `verified=0`. Then test them:

```bash
cd tools/pronunciation
../../.venv/bin/python jobs.py ep02a sauti,vaisampayana,bhishma --only Prachetas,Pitris --formats orig,p1 \
    --extra "Prachetas=Prachaytas;Pitris=Pitrees" > ../../build/pron_ep02a_jobs.json
cd ../..
$VOX tools/pronunciation/synth.py build/pron_ep02a_jobs.json        # each name in a carrier sentence, per voice (resumable)
$QA  tools/pronunciation/score.py build/pron_ep02a_jobs.json        # ASR -> phoneme similarity, spell-out detection
$QA  tools/pronunciation/select.py --min-voices 2                   # verified = passes on >= 2 voices
```

Put the winning form in `spoken`, set `verified=1` with a note, and add the plain-word forms you want to try to
`tools/pronunciation/words.tsv`. Prefer the KMG spelling when it passes. Still pending after Ep 1: **Prachetas,
Pitris** (each passes on only one voice).

## 5. New characters and voices

1. **Registry entry**, text-grounded with § refs: add a `C(...)` row in `src/mbh/characters/extracted/part*.py`
   (flag `single_section_speaker` if it speaks in only one section) and relationships in `rels.py`, then
   ```bash
   $APP -m mbh.characters.build_extracted --write      # -> characters/book01.json, checks every citation
   $APP -m mbh.webapp.reseed                           # backs up the DB, keeps voices and UI edits
   ```
2. **Briefs:** `proto/voices_<batch>.json`, 3–5 briefs per character with 2 takes each. Build them from the registry's
   `voice_brief` and the text; end every prompt with "clear Indian English accent". Design on a line the character
   does *not* speak in the episode (or a neutral sentence), so the clone tests are held out:
   ```json
   [{"id": "vyasa-E_dark_ascetic", "n": 2, "prompt": "The great seer Vyasa, an old dark-skinned ascetic, low grave voice ..., clear Indian English accent", "line": "..."}]
   ```
3. **Design → QA → clone test → QA → install:**
   ```bash
   $VOX tools/voice_design/design.py proto/voices_ep02.json        # voices/<id>/candidates/*.wav (resumable)
   $QA  tools/voice_design/qa.py design proto/voices_ep02.json     # WER, F0, wpm, similarity to every approved voice
   $VOX tools/voice_design/clone.py episodes/ep02.yaml ep02-0040,ep02-0051 voices/<id>/candidates/<best>.wav [...]
   $QA  tools/voice_design/qa.py clone <id>                        # WER + identity on real lines
   $APP tools/voice_design/install.py <id> voices/<id>/candidates/<pick>.wav --notes "Selected ...; approved by Aadesh <date>"
   ```
   Pick rules: WER ~0 (names aside); max cosine to any approved voice ≤ ~0.78 (the approved voices' own pairwise
   max); in clone tests own-candidate similarity ~0.85+ and above every other voice. Then a human listens.
   `install.py` levels to -20 LUFS, attaches the voice in the DB and rewrites `voices/registry.json`. Alternatively,
   pick in the web app's Voice panel and run `$APP tools/export_voice_registry.py`.
4. Commit `voices/<id>/ref.wav`, `voices/registry.json`, the brief JSON and the registry changes. Candidates stay local.

## 6. Render (resumable)

```bash
$VOX -m mbh.cli episode render --dry-run episodes/ep02.yaml     # cached / would_render / missing_voice per line
tools/render_resumable.sh episodes/ep02.yaml                     # loops until every line is cached; safe to re-run
```

Lines are cached by content (`build/cache/voxcpm2/`), so lines shared with an earlier episode are reused. A missing
voice shows as `missing_voice`: design or assign the voice (or a `voice_group`) first.

## 7. Assemble, music, master, MP3

```bash
$VOX -m mbh.cli episode assemble episodes/ep02.yaml --no-music --out build/ep02_full_v1.wav > build/ep02_full_v1.report.json
$VOX -m mbh.cli episode assemble episodes/ep02.yaml --music --music-preset A \
     --out build/ep02_full_v1_music.wav --music-stem build/ep02_full_v1_music_stem.wav > build/ep02_full_v1_music.report.json
$VOX tools/encode_mp3.py build/ep02_full_v1.wav samples/ep02_full_v1.mp3
$VOX tools/encode_mp3.py build/ep02_full_v1_music.wav samples/ep02_full_v1_music.mp3
```

Presets live in `configs/music.yaml` (`preset: A` is the default; `presets: {quiet, A, B}`). Cues follow each line's
emotion and scene rules. Speech tags inherit the next line's cue, and the music bus is trimmed wherever speech-to-music
falls under the preset's floor.

## 8. QA

```bash
$QA tools/qa_episode.py episodes/ep02.script.json episodes/ep02.render.json --out build/qa_ep02.json
$QA tools/qa_music.py episodes/ep02.script.json build/ep02_full_v1_music.report.json \
    build/ep02_full_v1_music.wav build/ep02_full_v1.wav build/ep02_full_v1_music_stem.wav --out build/qa_music_ep02.json
```

`qa_episode.py` checks, per line: Whisper WER vs the KMG text, lexicon names heard, speaker identity vs every voice
ref, cut-off endings, long internal silences, repetitions/insertions, duration vs expected, and clipping.
`qa_music.py` compares WER and speaker identity with and without music and reports min/avg speech-to-music ratio.
For a bad line, add `{"...": ..., "take": 1}` in the overrides, rebuild, re-render (only that line re-renders),
re-assemble, and QA `--only <line_id>`. Note the timestamps of anything worth a human listen.

## 9. Export / publish

* Commit: the episode YAML, overrides, `*.script.json`, `*_script.md`, `*.cues.txt`, review notes, lexicon changes,
  new `voices/<id>/ref.wav` + `voices/registry.json`, and code. **Not** committed: `samples/` (MP3s), `build/`,
  `data/mbh.sqlite3`, candidates, model weights. MP3s are published as GitHub release assets.
* Bundle for hand-off without pushing: `git bundle create ../mahabharat-export/<branch>.bundle main..<branch>`.

## Sharded rendering (standard for every episode)

Episodes render in shards of a few minutes of speech each, split at line boundaries, and are assembled only after every shard is done. Short processes mean an interruption or hang loses at most one line.

```bash
mbh episode render --list-shards --shard-minutes 4 episodes/ep03.yaml   # print the shard plan
mbh episode render --shard 3 --shard-minutes 4 episodes/ep03.yaml        # render one shard
setsid nohup tools/render_sharded.sh episodes/ep03.yaml 4 > logs/render_ep03_sharded.log 2>&1 &
```

`tools/render_sharded.sh` runs each shard as its own process with retries, writes `build/shards/<episode>/shard_K.done`, then writes the full render manifest (all lines cached) and runs `assemble --music --music-preset A`. Lines share the per-line cache, so rerun the same command after a crash or VM restart and it resumes. A shard render never overwrites the full-episode manifest. Delete the `.done` markers if you change the script so shards are rechecked.

## Title song (opening intro)

The opening title song is Bhagavad Gita 2.62–63, chanted over a code-generated tanpura drone. To use it, add one line to an episode spec:

```yaml
intro: title_song          # named intro from configs/intros.yaml
# intro_crossfade_s: 2.5   # optional override (default from configs/intros.yaml)
```

`mbh episode assemble` (and Studio) mixes the episode body with its music bed, then prepends the intro. The intro's last `crossfade_s` seconds (its drone fade-out) overlap the start of the episode with an equal-power crossfade, and the whole episode is mastered to -16 LUFS together. `intro:` still accepts a plain WAV path (no crossfade unless `intro_crossfade_s` is set). Line timestamps in the assemble report are shifted by the intro's length.

Rebuilding the title song (CPU): `STYLES=chant SPELLINGS=r4,r7,r8,r9 proto/.venv-vox/bin/python tools/title_song/chant.py`, then `proto/.venv-vox/bin/python tools/title_song/split_r7.py` (splits the whole-verse takes), `proto/.venv-pocket/bin/python tools/title_song/score.py` (per-clip ASR vs Devanagari), `proto/.venv-vox/bin/python tools/title_song/mix.py chant r4 build/title_song/v1.wav --clips <mixes.v1.clips>`, and `tools/title_song/verify.py build/title_song/v1` (ASR on the finished mix). Copy the chosen WAV to `assets/intro/title_song_v1.wav`. The text, respellings, styles, and seeds are in `configs/title_song.json`.
