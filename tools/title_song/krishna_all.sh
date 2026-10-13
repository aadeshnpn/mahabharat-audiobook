#!/usr/bin/env bash
# v5 Krishna title track end to end (resumable). setsid nohup tools/title_song/krishna_all.sh > logs/title_v5.log 2>&1 &
set -eu; cd "$(dirname "$0")/../.."
k() { PYTHONPATH=src "$1" tools/title_song/krishna.py "${@:2}"; }
V=proto/.venv-vox/bin/python; P=proto/.venv-pocket/bin/python
k $V design; k $P score; echo DESIGNS_DONE
k $V takes; k $P score; echo TAKES_DONE
k $V mix --out build/title_song_v5/title_song_v5_krishna.wav; echo V5_DONE
