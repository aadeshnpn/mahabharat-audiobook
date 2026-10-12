# Episode Studio

The character-map server also hosts Episode Studio: a browser UI and a JSON API for the same episode pipeline the CLI uses. Creating an episode, estimating it, suggesting an ending, editing a line, rendering, assembling, and running QA all go through `/api/studio`. The pages under `/studio` call that API and do not keep a second copy of the pipeline.

OpenAPI is at [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs). This file is the walkthrough, including a copy-pasteable agent flow at the end.

## Run

From the repo root, after `scripts/setup.sh` (or any venv that has `requirements/app.txt`):

```bash
PYTHONPATH=src .venv/bin/python -m mbh.webapp
```

- Character map: http://127.0.0.1:8765/
- Studio: http://127.0.0.1:8765/studio
- API docs: http://127.0.0.1:8765/docs

`MBH_HOST` defaults to `127.0.0.1` and `MBH_PORT` to `8765`. There is no login. That is safe only while the process is reachable from your own machine. If you set `MBH_HOST` to anything else, the server prints a warning and still does not authenticate. Put a trusted proxy in front before you do that, or leave the default.

Rendering, assembly, QA, pronunciation tests, and voice design share **one** background worker. A second heavy job stays `queued` until the first finishes. On a 16 GB machine, do not also start `mbh episode render` or a voice-design script while a studio job is `running`: two VoxCPM2 processes will exhaust RAM.

## What the pages do

| Page | What you do there |
|---|---|
| Episodes | List specs in the episodes folder, with the last duration estimate and whether a script or a mix exists. |
| New | Pick a section and an inclusive paragraph range, a target duration, and a music preset. Estimate is live. Suggest endings runs the break suggester; choosing one sets the end paragraph. An optional bridge is stored as `non_kmg: true`. |
| Script | One row per line: speaker, emotion, pace, KMG text, TTS text, music cue, take. Save writes an overrides row and rebuilds, so the edit survives the next build. Split parts must re-join to the KMG wording. Merge joins this line with the next. Bridges stay badged as non-KMG. |
| Play | Assembled wav, a waveform, and a line list. Clicking a line seeks the player. QA flags and the non-KMG badge sit on the row, with the line's start time. Download wav or MP3. |
| Lexicon | Search `lexicon/book01.tsv`. Edit the human respelling and the spoken form, mark verified, and queue a pronunciation test you can play. Only `spoken` is sent to TTS, and only once verified; otherwise the builder keeps the KMG spelling. |
| Voices | Characters from the database. Design candidates from the brief, audition them, and pick one as `voices/<id>/ref.wav`. The same clip is what the character map's Voice tab plays. |
| Jobs | Progress, log, and cancel. Cancel takes effect between lines. Lines already written stay in the render cache. |

Playback files live in `build/studio/<id>/` (`episode.wav`, `episode.mp3`, `assemble.json`, `qa.json`). The render manifest stays `episodes/<id>.render.json`, the same path the CLI writes. Both directories are gitignored.

## Jobs

Kinds: `render`, `rerender` (a render with `only`), `assemble`, `qa`, `pronunciation`, `design_voice`. Every one of them is heavy. The worker claims the oldest `queued` row, and a restart moves leftover `running` rows back to `queued`. Render and pronunciation skip files that are already cached, so a killed job repeats only the line that was in progress. A wav is written to `*.partial.wav` and renamed when the line finishes, so a half-written file is not treated as a cache hit.

`POST /api/jobs/{id}/cancel` marks a queued job `cancelled` immediately. A running job stops at the next line boundary, or kills the QA / synth subprocess it spawned. `GET /api/jobs/{id}/log` is the plain-text log. `output` on a finished job is a JSON string.

`MBH_STUDIO_MOCK=1` swaps synthesis for a short tone. Use it to exercise the API without VoxCPM2. It does not produce listenable speech.

## Environment

| Variable | Default | |
|---|---|---|
| `MBH_HOST` | `127.0.0.1` | Bind address. Anything else is unauthenticated. |
| `MBH_PORT` | `8765` | |
| `MBH_DB` | `data/mbh.sqlite3` | Characters, relationships, and the job queue. |
| `MBH_EPISODES` | `episodes/` | Episode YAML and overrides. |
| `MBH_LEXICON` | `lexicon/book01.tsv` | |
| `MBH_BUILD` | `build/` | Cache, playback, pronunciation clips. |
| `MBH_VOX_PYTHON` | `proto/.venv-vox/bin/python` | Render, assemble, voice design, pronunciation synth. |
| `MBH_QA_PYTHON` | `proto/.venv-pocket/bin/python` | `tools/qa_episode.py`. |
| `MBH_STUDIO_MOCK` | unset | `1` skips VoxCPM2 and Whisper. |

Music assembly needs `numpy` and `scipy` (`pip install -e '.[music]'`, already in the vox venv). Pass `"music": false` on assemble when that stack is not installed. Presets are `quiet`, `A`, and `B` (`configs/music.yaml`). Preset A is the default.

Voice design in the studio writes candidates and can install one as the reference clip. The separate WER, distinctness, and clone-test steps in [EPISODE_WORKFLOW.md](EPISODE_WORKFLOW.md) are still the way a new voice is approved before it is committed.

## Agent usage

The browser and this flow call the same routes. Poll a job until `status` is `done`, `failed`, or `cancelled`. A 202 means the job was queued, not that audio exists yet.

Set `MBH_STUDIO_MOCK=1` in the server environment for a no-model rehearsal. Leave it unset when you want real speech.

```bash
BASE=http://127.0.0.1:8765

# 1. Duration of a draft. Nothing is written.
curl -s -X POST "$BASE/api/studio/estimate" -H 'content-type: application/json' -d '{
  "id": "ep02",
  "title": "Episode 2",
  "target_duration_s": 1050,
  "music": true,
  "music_preset": "A",
  "speech_tags": "keep",
  "narrator_default": "sauti",
  "strip_glosses": true,
  "end_reason": "Pause after the frame is set.",
  "segments": [
    {"id": "main", "kind": "section", "section": 1, "paragraphs": [1, 8], "narrator": "sauti", "label": "invocation"}
  ]
}'

# 2. Legal endings near that target. The same body works; "limit" is optional.
#    A suggestion's "paragraph" is the end paragraph to store on the section segment.
curl -s -X POST "$BASE/api/studio/breaks" -H 'content-type: application/json' -d '{
  "id": "ep02",
  "title": "Episode 2",
  "target_duration_s": 1050,
  "music": true,
  "music_preset": "A",
  "end_reason": "Pause after the frame is set.",
  "segments": [
    {"id": "main", "kind": "section", "section": 1, "paragraphs": [1, 8], "narrator": "sauti"}
  ],
  "limit": 5
}'

# 3. Create. 201, and the script is built. A bridge must be non_kmg.
curl -s -X POST "$BASE/api/studio/episodes" -H 'content-type: application/json' -d '{
  "id": "ep02",
  "title": "Episode 2",
  "target_duration_s": 1050,
  "music": true,
  "music_preset": "A",
  "speech_tags": "keep",
  "narrator_default": "sauti",
  "strip_glosses": true,
  "end_reason": "Ends at a narration boundary.",
  "segments": [
    {"id": "main", "kind": "section", "section": 1, "paragraphs": [1, 8], "narrator": "sauti", "label": "invocation"},
    {"id": "bridge", "kind": "bridge", "speaker": "sauti", "non_kmg": true, "text": "Here the telling pauses."}
  ]
}'

# 4. Review. Pick a line id from "lines". non_kmg lines are the bridge.
curl -s "$BASE/api/studio/episodes/ep02/script" -o /tmp/ep02.script.json

# 5. Override one line, then the script is rebuilt. This is written to
#    episodes/overrides/ep02.json and survives another POST .../build.
LINE=$(python3 -c 'import json;print(json.load(open("/tmp/ep02.script.json"))["lines"][1]["id"])')
curl -s -X POST "$BASE/api/studio/episodes/ep02/lines/$LINE" \
  -H 'content-type: application/json' \
  -d '{"emotion":"commanding","tts_text":null}'

# 6. Render. Cached lines are skipped. "only" re-renders those line ids.
curl -s -X POST "$BASE/api/studio/episodes/ep02/render" \
  -H 'content-type: application/json' -d '{}' -o /tmp/render.job.json
JOB=$(python3 -c 'import json;print(json.load(open("/tmp/render.job.json"))["id"])')
while true; do
  curl -s "$BASE/api/jobs/$JOB" -o /tmp/job.json
  ST=$(python3 -c 'import json;print(json.load(open("/tmp/job.json"))["status"])')
  echo "render $ST"
  case "$ST" in done|failed|cancelled) break;; esac
  sleep 5
done
curl -s "$BASE/api/jobs/$JOB/log"

# 7. Assemble. Omit music to follow the YAML; preset A is the house default.
curl -s -X POST "$BASE/api/studio/episodes/ep02/assemble" \
  -H 'content-type: application/json' \
  -d '{"music": true, "music_preset": "A"}' -o /tmp/assemble.job.json
JOB=$(python3 -c 'import json;print(json.load(open("/tmp/assemble.job.json"))["id"])')
while true; do
  curl -s "$BASE/api/jobs/$JOB" -o /tmp/job.json
  ST=$(python3 -c 'import json;print(json.load(open("/tmp/job.json"))["status"])')
  echo "assemble $ST"
  case "$ST" in done|failed|cancelled) break;; esac
  sleep 5
done

# 8. QA, then read flags and timestamps. Download the MP3.
curl -s -X POST "$BASE/api/studio/episodes/ep02/qa" \
  -H 'content-type: application/json' -d '{}' -o /tmp/qa.job.json
JOB=$(python3 -c 'import json;print(json.load(open("/tmp/qa.job.json"))["id"])')
while true; do
  curl -s "$BASE/api/jobs/$JOB" -o /tmp/job.json
  ST=$(python3 -c 'import json;print(json.load(open("/tmp/job.json"))["status"])')
  echo "qa $ST"
  case "$ST" in done|failed|cancelled) break;; esac
  sleep 5
done
curl -s "$BASE/api/studio/episodes/ep02/qa"
curl -s -o ep02.mp3 "$BASE/api/studio/episodes/ep02/episode.mp3"
```

Per-line audio is `GET /api/studio/episodes/ep02/lines/{line_id}/audio`. The player payload is `GET /api/studio/episodes/ep02/waveform` (`peaks`, `seconds`, `timeline[].start_s`, and QA flags).

Other calls an agent will want:

```bash
# Re-render one line after a take bump.
curl -s -X POST "$BASE/api/studio/episodes/ep02/lines/$LINE" \
  -H 'content-type: application/json' -d '{"take": 1}'
curl -s -X POST "$BASE/api/studio/episodes/ep02/render" \
  -H 'content-type: application/json' -d "{\"only\": [\"$LINE\"]}"

# Cancel. Queued jobs die immediately; a running render stops between lines.
curl -s -X POST "$BASE/api/jobs/$JOB/cancel"

# Lexicon: spoken form, then a listening test. Play clips[0].relative via /api/studio/media?path=
curl -s -X PUT "$BASE/api/studio/lexicon" -H 'content-type: application/json' -d '{
  "term": "Prachetas", "respelling": "pruh-CHAY-tus", "spoken": "Prachetas", "verified": 0, "notes": "pending listen"
}'
curl -s -X POST "$BASE/api/studio/lexicon/test" -H 'content-type: application/json' -d '{
  "term": "Prachetas", "voices": ["sauti", "vaisampayana"], "formats": ["orig"], "extra": ["Prachaytas"]
}'

# Voice candidates from the character brief, then install one as the reference.
curl -s -X POST "$BASE/api/studio/voices/vyasa/design" \
  -H 'content-type: application/json' -d '{"n": 2}'
curl -s -X POST "$BASE/api/characters/vyasa/voice/select" \
  -H 'content-type: application/json' \
  -d '{"file": "voices/vyasa/candidates/cand_YYYYMMDD_HHMMSS_0.wav"}'
```

`GET /api/jobs?episode=ep02&kind=render` lists the queue. Section text for a range picker is `GET /api/studio/sections/1`. Speakers the editor will accept are `GET /api/studio/cast`.

Split and merge:

```bash
curl -s -X POST "$BASE/api/studio/episodes/ep02/lines/$LINE/split" \
  -H 'content-type: application/json' \
  -d '{"parts": [{"text": "first words"}, {"text": "rest of the line", "speaker": "sauti"}]}'
curl -s -X POST "$BASE/api/studio/episodes/ep02/lines/$LINE/merge"
```

A split that does not re-join to the KMG text returns 422. Deleting the override is `DELETE /api/studio/episodes/ep02/lines/$LINE/override`.

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_studio.py tests/test_api.py
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_e2e_studio.py   # needs Playwright and Chrome; skipped otherwise
```

`tests/test_studio.py` sets `MBH_STUDIO_MOCK=1` and points episodes, lexicon, and build at a temp directory, so the repo's `episodes/ep01.yaml` and `lexicon/book01.tsv` are not modified. The heavy backend is a tone generator.
