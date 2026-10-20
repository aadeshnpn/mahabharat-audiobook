# Local setup (Linux, CPU only)

Everything here runs on a CPU; no GPU, no paid API. Tested on the build box (Debian 13, x86-64, 8 vCPU, 15 GB RAM,
Python 3.12.15). Expected to work the same on any recent x86-64 Linux (Ubuntu 22.04+, Debian 12+, Fedora 39+), e.g. an
HP EliteBook 845 G11 (AMD Ryzen, 8 cores / 16 threads): PyTorch's CPU wheels run on AMD and Intel alike.

## TL;DR

```bash
sudo apt install -y git ffmpeg curl          # Fedora: sudo dnf install git ffmpeg curl
git clone https://github.com/aadeshnpn/mahabharat-audiobook.git && cd mahabharat-audiobook
git checkout ep01-script                     # or main once merged
scripts/setup.sh                             # ~10-20 min: 3 venvs, ~5.2 GB model weights, DB seed, unit tests
scripts/smoke_test.sh                        # renders one short line end to end (~1-3 min), prints SMOKE TEST PASSED
scripts/render_episode.sh episodes/ep01.yaml --name ep01_full_v1 --qa    # a full episode (~1 h for 17 min)
```

## What you need

| | Minimum | Recommended |
|---|---|---|
| CPU | 4 cores x86-64 (AVX2) | 8+ cores |
| RAM | 12 GB + 8 GB swap | 16 GB+ |
| Disk | 15 GB free | 25 GB (weights 5.2 GB, venvs ~6 GB, render cache ~1 GB per episode) |
| OS | x86-64 Linux, glibc 2.31+ | |
| Tools | `git`, `ffmpeg` (MP3 encode + loudness check), `curl` | |

**RAM, measured:** loading VoxCPM2 peaks at **~9.4 GB** resident, then a render holds **~6 GB**. The QA venv
(Whisper small.en + resemblyzer) needs ~2 GB. Run one model job at a time; two VoxCPM2 processes at once will
exhaust 16 GB.

## Step by step (what `scripts/setup.sh` does)

1. **uv** (fast Python/venv manager; installs Python 3.12 for you, no root):
   `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv python install 3.12`.
2. **Three venvs**, kept separate because the TTS and ASR stacks pin different things:

   | venv | requirements | used for |
   |---|---|---|
   | `.venv` | `requirements/app.txt` | web app, `mbh episode build/estimate/breaks/cues`, voice install |
   | `proto/.venv-vox` | `requirements/render.txt` | VoxCPM2: voice design, `mbh episode render/assemble`, music, MP3 encode, unit tests |
   | `proto/.venv-pocket` | `requirements/qa.txt` | QA: faster-whisper ASR, resemblyzer speaker check, pronunciation scoring |

   On x86-64 the script installs the **exact lock files** in `requirements/lock/*.linux-x86_64.txt` (frozen from the
   working box); `--pins` uses the shorter direct-dependency pins instead. PyTorch comes from the CPU wheel index
   (`--extra-index-url https://download.pytorch.org/whl/cpu`) so you don't download ~2 GB of CUDA libraries.
   Manually:
   ```bash
   uv venv --python 3.12 proto/.venv-vox
   VIRTUAL_ENV=proto/.venv-vox uv pip install --extra-index-url https://download.pytorch.org/whl/cpu \
       --index-strategy unsafe-best-match -r requirements/lock/render.linux-x86_64.txt
   VIRTUAL_ENV=proto/.venv-vox uv pip install --no-deps -e .
   ```
   Key versions: torch 2.14.1+cpu, torchaudio 2.11.0, voxcpm 2.0.3, transformers 5.19.0, faster-whisper 1.2.1,
   resemblyzer 0.1.4, fastapi 0.143.0.
3. **Model weights** go to the Hugging Face cache (`~/.cache/huggingface/hub`, or `$HF_HOME`). **Never commit them**
   (`.gitignore` blocks `*.safetensors|*.bin|*.pt|*.onnx|*.gguf|*.ckpt`).
   ```bash
   proto/.venv-vox/bin/python -c "from huggingface_hub import snapshot_download as s; s('openbmb/VoxCPM2')"    # 4.7 GB
   proto/.venv-pocket/bin/python -c "from faster_whisper import WhisperModel as W; W('small.en', device='cpu', compute_type='int8')"  # 464 MB
   proto/.venv-pocket/bin/python -m nltk.downloader cmudict averaged_perceptron_tagger_eng   # pronunciation scorer only
   ```
   Resemblyzer's speaker encoder ships inside the pip package. Both models also download lazily on first use.
4. **Database**: `.venv/bin/python -m mbh.webapp.seed` builds `data/mbh.sqlite3` (gitignored) from
   `characters/book01.json` and attaches all approved voices from `voices/registry.json`. Web app
   (character map and Episode Studio), bound to localhost with no login:
   `PYTHONPATH=src .venv/bin/python -m mbh.webapp` and open http://127.0.0.1:8765/ (studio at `/studio`,
   API docs at `/docs`). `MBH_HOST` defaults to `127.0.0.1`; set it only behind a trusted proxy.
   See [STUDIO.md](STUDIO.md).
5. **Tests**: `proto/.venv-vox/bin/python -m pytest -q --ignore=tests/e2e_ui.py` (no model needed, ~10 s).
   The UI test needs Playwright: `VIRTUAL_ENV=.venv uv pip install playwright && .venv/bin/playwright install chromium`.

## The half-precision load trick (why it fits in 16 GB)

VoxCPM2 constructs its modules in fp32 by default, which peaks above 15 GB. All loaders here
(`src/mbh/episode/voxcpm2.py`, `src/mbh/voices/design_one.py`, `tools/voice_design/design.py`) do:

```python
torch.set_default_dtype(torch.bfloat16)        # build the model directly in bf16
model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False)
torch.set_default_dtype(torch.float32)         # restore for everything else
```

`load_denoiser=False` skips the extra denoiser download; `optimize=False` skips torch.compile (slow to warm up and
not worth it on CPU). Threads: `MBH_THREADS=8` (default: all cores). On a 16-thread Ryzen, try `MBH_THREADS=8` vs
`16`; physical cores are often faster than SMT threads for this workload.

## Expected speed

Measured on the build box (8 vCPU Xeon, 10 diffusion steps): **real-time factor about 2.5 to 3**. One second of
speech takes 2.5–3 s to render.

| Job | Time |
|---|---|
| Model load | 15–20 s per process |
| One voice-design candidate (~11 s of speech) | ~30 s |
| Pilot (5 min of speech) | ~15 min |
| Episode 1 (17 min, 83 lines) | ~45–60 min |
| Assembly + music + master | 2–4 min |
| QA (ASR + speaker check) of a 17 min episode | ~5–8 min |

A modern 8-core laptop should be in the same range or faster. Plugged in, with "performance" power mode, it can be
noticeably quicker than on battery.

## Caches and resuming

* Rendered lines: `build/cache/voxcpm2/<sha256>.wav` (+ `.json` sidecar). The key covers TTS text, instruction,
  voice ref **content hash**, engine params, fx and retake number. An interrupted render loses at most the line in
  progress. Re-run the same command (`tools/render_resumable.sh` loops until nothing is left).
* Changing a voice's `ref.wav` re-renders only that voice's lines; editing a line's text re-renders only that line.
* `build/` is disposable (`rm -rf build/cache` forces a full re-render). Copy `build/cache/` between machines to
  reuse renders: the keys are content-based, so they stay valid.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Process killed, `Killed` / exit 137 / `dmesg` shows `oom-kill` | Another model job was running, or RAM < 12 GB. Close browsers, run one job at a time, add swap: `sudo fallocate -l 8G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`. Check that the bf16 trick is in your loader. |
| pip pulls `nvidia-*` packages / huge downloads | Torch came from PyPI instead of the CPU index. Reinstall with `--extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match`. |
| `ModuleNotFoundError: yaml / voxcpm / soundfile` | Wrong interpreter. Render/assemble with `proto/.venv-vox/bin/python`, QA with `proto/.venv-pocket/bin/python`. |
| `VoxCPM2 is not installed in this interpreter` | Set `MBH_VOX_PYTHON=proto/.venv-vox/bin/python` or run the CLI with that python. |
| Everything re-renders after `git pull` | Shouldn't happen: keys use the ref's content hash. If a `ref.wav` really changed, that voice re-renders by design. |
| Very slow (RTF > 6) | Laptop on battery / power-saver; thermal throttling; try `MBH_THREADS` = number of physical cores. |
| `nltk` LookupError in `tools/pronunciation/score.py` | `proto/.venv-pocket/bin/python -m nltk.downloader cmudict averaged_perceptron_tagger_eng`. |
| Hugging Face download stalls | `export HF_HUB_ENABLE_HF_TRANSFER=0`, retry; or download on another machine and copy `~/.cache/huggingface/hub/models--openbmb--VoxCPM2`. |
| MP3 louder/quieter than -16 LUFS | Use `tools/encode_mp3.py` (it re-measures the MP3 and corrects once); `ffmpeg -i x.mp3 -af ebur128=peak=true -f null -` to check. |

## Getting the render cache (skip re-rendering)

After cloning, `python3 tools/cache_sync.py pull` downloads every rendered line from the `render-cache` release
(public, no token). After rendering, `python3 tools/cache_sync.py push` (with `gh auth login`) uploads the new lines. See
docs/EPISODE_WORKFLOW.md "Render cache off the box".
