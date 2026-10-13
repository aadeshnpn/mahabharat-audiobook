#!/usr/bin/env bash
# takes for every line (cached) -> ASR-score -> build_F.sh. usage: setsid nohup tools/song/full_F.sh [seed] > logs/song_F.log 2>&1 &
set -eu; cd "$(dirname "$0")/../.."; S=${SONG:-configs/songs/title_song.yaml}
PYTHONPATH=src proto/.venv-vox/bin/python -m mbh.cli song takes $S
PYTHONPATH=src proto/.venv-pocket/bin/python -m mbh.cli song score $S
echo TAKES_DONE
tools/song/build_F.sh "${1:-0}"
