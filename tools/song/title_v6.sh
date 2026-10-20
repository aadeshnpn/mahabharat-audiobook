#!/usr/bin/env bash
# Title v6 end to end (resumable). setsid nohup tools/song/title_v6.sh > logs/title_v6.log 2>&1 &
set -eu; cd "$(dirname "$0")/../.."
V=proto/.venv-vox/bin/python; P=proto/.venv-pocket/bin/python; H=configs/songs/title_v6_hook.yaml
PYTHONPATH=src $V tools/title_song/krishna.py takes; PYTHONPATH=src $P tools/title_song/krishna.py score
PYTHONPATH=src $V -m mbh.cli song takes $H; PYTHONPATH=src $P -m mbh.cli song score $H
mkdir -p build/title_v6; [ -f build/title_v6/hook.json ] || PYTHONPATH=src $V -m mbh.cli song render $H --out build/title_v6/hook.wav
PYTHONPATH=src $V tools/song/title_v6.py build "$@"
PYTHONPATH=src $P tools/song/title_v6.py asr "$@"
echo V6_DONE
