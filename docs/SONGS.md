# Sung pieces (`mbh song`)

This covers title songs and shlokas sung as songs. Everything is open source and runs on the CPU. Each piece is reproducible from one YAML file in `configs/songs/`.

## Config (`configs/songs/<id>.yaml`)

| Key | Meaning |
|---|---|
| `raga`, `sa_hz`, `tempo_bpm` | Mode, tonic (Sa) frequency and pulse. The melody is validated against the raga's scale (`mbh.song.melody.RAGAS`). |
| `lines[]` | `id`, `text` (Devanagari, exactly what the voice reads), `syllables` (one entry per sung syllable, space-separated), `melody` (one entry per syllable), optional `context` (a longer text to speak, from which this line is cut; it fixes weak word onsets) and `take` (a fixed take file). |
| `melody` entries | `"swara:beats"`. Several in one entry make a melisma: `"N.:0.5 R:1"`. `{rest: 0.5}` inserts a rest. Swaras are `S r R g G m M P d D n N` (lowercase r, g, d, n are komal; `m` is shuddha ma; `M` is tivra ma). A `.` suffix means the lower octave and `'` the upper. Notes use just intonation. |
| `voice` | The singer for the WORLD path: `id` (`voices/<id>/ref.wav`, or `ref:` to point at a candidate), VoxCPM2 `prompt`, `seeds`, `octave`, `vibrato_cents`, `vibrato_hz`, `glide_s`. |
| `arrangement` | `preset` (`devotional_title`, `meditative`; see `mbh.song.arrange.PRESETS`), `intro_beats`, `gap_beats`, `outro_beats`, `tabla` (`keherwa` or `dadra`), and an optional `mix:` override of the preset levels. |
| `structure` | The order of sung lines (repeats allowed): `[{line: "2.62a"}, ...]`. |
| `ace` | ACE-Step settings: `prompt` (style), `language`, `bpm`, `keyscale`, `steps`, `duration`, `script` (`devanagari` or `roman`), `repeat`. |
| `master` | `lufs` (default -16) and `true_peak_db` (default -2). |

## Two engines

**1. WORLD path (our own melody, fully controllable).**
1. `mbh song takes` speaks each line with the singer voice (a VoxCPM2 clone), using several seeds.
2. `mbh song score` transcribes each take with Whisper (Devanagari) and keeps the best-scoring one.
3. `mbh song render` sings the take onto the composed melody:
   - The MMS multilingual forced aligner (torchaudio `MMS_FA`, run on an ASCII romanisation from `mbh.song.translit`) gives the syllable and vowel timings.
   - WORLD (`pyworld`) re-times each syllable: consonants keep their natural length and anticipate the beat; the vowel is stretched over the note or notes.
   - The new f0 contour is built from the notes, with log-domain glides (meend), delayed vibrato and slight drift.
   - The arrangement is generated in code: a tanpura (Sa–Pa), a harmonium (drone plus the melody doubled), string swells with an intro hook, a synthesised tabla, and bells.
   - The result is mastered to the target.

**2. ACE-Step 1.5 path (a realistic, fully produced song).** `mbh song ace` runs `ACE-Step/acestep-v15-xl-turbo-diffusers` (MIT licence; diffusers `AceStepPipeline`) on the CPU. It takes about 35 s per 30 s clip, using 8 turbo steps in bf16.
- `--mode text2music`: the model composes the melody and the orchestration from the Devanagari lyrics and the style prompt.
- `--mode complete --src <WORLD vocal>`: keeps our sung vocal (our melody) and adds a generated accompaniment.
- `--mode lego --src <WORLD mix>`: adds a generated track over our mix.
- `cover` needs ACE's audio tokenizer, which the diffusers checkpoint does not ship.

Then run `mbh song master` (trim, fades, -16 LUFS / -2 dBTP) and `mbh song asr` (Whisper similarity against the line text) to check pronunciation on any file.

## Environments

| Venv | Used for | Notes |
|---|---|---|
| `proto/.venv-vox` | `takes`, `render`, `master` | Needs `pyworld` (C++ build: `sudo apt-get install g++`, then `uv pip install pyworld "setuptools<81"`) and `torchaudio`. |
| `proto/.venv-pocket` | `score`, `asr`, `verify` | Uses faster-whisper `small` (multilingual). |
| `proto/.venv-ace` | `ace` | Python 3.12, CPU torch, diffusers from git, transformers. The model download is about 11 GB. |

Run every command as `PYTHONPATH=src <venv>/bin/python -m mbh.cli song ...`.

## Example: the title-song sample

```bash
S=configs/songs/title_song.yaml
PYTHONPATH=src .venv/bin/python -m mbh.cli song check $S
PYTHONPATH=src proto/.venv-vox/bin/python -m mbh.cli song takes $S --lines 2.62a --voice singer_m --voice-ref voices/singer_m/candidates/singer_m-A_vox_s10_0.wav
PYTHONPATH=src proto/.venv-pocket/bin/python -m mbh.cli song score $S
PYTHONPATH=src proto/.venv-vox/bin/python -m mbh.cli song render $S --lines 2.62a --voice singer_m --out build/song/title_song/world.wav
PYTHONPATH=src proto/.venv-ace/bin/python -m mbh.cli song ace $S --lines 2.62a --seed 5 --out build/song/title_song/ace.wav
PYTHONPATH=src proto/.venv-vox/bin/python -m mbh.cli song master $S build/song/title_song/ace.wav samples/x.wav --end 28
PYTHONPATH=src proto/.venv-pocket/bin/python -m mbh.cli song asr $S samples/x.wav --lines 2.62a
```

## Copyright

Melodies in `configs/songs/` are original compositions. ACE-Step outputs are newly generated: the prompt names a style (devotional TV epic title song, harmonium, strings, tabla), never a specific song. Do not transcribe or prompt for an existing film or TV melody.
