#!/usr/bin/env bash
# One-shot local setup (Linux x86-64, Python 3.12, CPU only). Idempotent: safe to re-run.
#   scripts/setup.sh                 # all three venvs + model weights + DB seed
#   scripts/setup.sh --no-qa         # skip the QA/ASR venv (render-only machine)
#   scripts/setup.sh --no-models     # skip weight downloads (they also download lazily on first use)
#   scripts/setup.sh --pins          # use requirements/*.txt pins instead of the exact Linux lock files
# See docs/LOCAL_SETUP.md.
set -euo pipefail
cd "$(dirname "$0")/.."
QA=1; MODELS=1; MODE=auto
for a in "$@"; do case $a in --no-qa) QA=0;; --no-models) MODELS=0;; --pins) MODE=pins;; --lock) MODE=lock;; *) echo "unknown option $a"; exit 2;; esac; done
say() { printf '\n== %s\n' "$*"; }

say "prerequisites"
[ "$(uname -s)" = Linux ] || { echo "Linux only (see docs/LOCAL_SETUP.md)"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg missing: sudo apt install ffmpeg  (Fedora: sudo dnf install ffmpeg)"; exit 1; }
if ! command -v uv >/dev/null; then
  echo "installing uv (Python/venv manager) to ~/.local/bin"; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
fi
uv python install 3.12 >/dev/null
os=$(uname -s); arch=$(uname -m)
if [ "$MODE" = auto ]; then [ "$arch" = x86_64 ] && MODE=lock || MODE=pins; fi
TORCH_IDX=(--extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match)
echo "OS=$os ARCH=$arch requirements=$MODE"

mkvenv() {  # mkvenv <path> <name>
  local v=$1 n=$2 req
  [ "$MODE" = lock ] && req=requirements/lock/$n.linux-x86_64.txt || req=requirements/$n.txt
  say "venv $v <- $req"
  [ -x "$v/bin/python" ] || uv venv -q --python 3.12 "$v"
  VIRTUAL_ENV=$v uv pip install -q "${TORCH_IDX[@]}" -r "$req"
  VIRTUAL_ENV=$v uv pip install -q --no-deps -e .
}
mkvenv .venv app
mkvenv proto/.venv-vox render
[ $QA = 1 ] && mkvenv proto/.venv-pocket qa

if [ $MODELS = 1 ]; then
  say "model weights (Hugging Face cache, ~5.2 GB; never committed)"
  proto/.venv-vox/bin/python -c "from huggingface_hub import snapshot_download as s; print(s('openbmb/VoxCPM2'))"
  if [ $QA = 1 ]; then
    proto/.venv-pocket/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8'); print('whisper small.en ok')"
    proto/.venv-pocket/bin/python -m nltk.downloader -q cmudict averaged_perceptron_tagger_eng averaged_perceptron_tagger || echo "WARN: NLTK data download failed (only the pronunciation harness scorer needs it)"
  fi
fi

say "web-app database (characters + 12 voices from voices/registry.json)"
[ -f data/mbh.sqlite3 ] && echo "data/mbh.sqlite3 exists, keeping it (re-seed: .venv/bin/python -m mbh.webapp.reseed)" || .venv/bin/python -m mbh.webapp.seed

say "tests (no TTS model needed)"
proto/.venv-vox/bin/python -m pytest -q --ignore=tests/e2e_ui.py
say "done. Next: scripts/smoke_test.sh (renders one short line, ~1-2 min), then docs/EPISODE_WORKFLOW.md"
