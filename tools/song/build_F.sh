#!/usr/bin/env bash
# Preset F title song, end to end (resumable). usage: tools/song/build_F.sh [seed=0] [out=build/song/title_song/F]
# long runs: setsid nohup tools/song/build_F.sh 0 > logs/song_F.log 2>&1 &
set -eu; cd "$(dirname "$0")/../.."
S=${SONG:-configs/songs/title_song.yaml}; seed=${1:-0}; D=${2:-build/song/$(basename "$S" .yaml)/F}; mkdir -p "$D"
song() { PYTHONPATH=src "$1" -m mbh.cli song "${@:2}"; }
[ -f "$D/F_world.json" ] || song proto/.venv-vox/bin/python render $S --out "$D/F_world.wav"
[ -f "$D/band_s$seed.wav" ] || song proto/.venv-ace/bin/python ace $S --mode complete --src "$D/F_world.vocal.wav" --prompt-key epic_band --seed "$seed" --out "$D/band_s$seed.wav"
[ -f "$D/sep/htdemucs/band_s$seed/no_vocals.wav" ] || proto/.venv-pocket/bin/python -m demucs --two-stems vocals -n htdemucs -o "$D/sep" "$D/band_s$seed.wav"
song proto/.venv-vox/bin/python finish $S --world "$D/F_world.json" --band "$D/sep/htdemucs/band_s$seed/no_vocals.wav" --out "$D/F_full_s$seed.wav"
song proto/.venv-pocket/bin/python asr $S "$D/F_full_s$seed.wav" "$D/F_full_s$seed.vox.wav" --lines 2.62a,2.62b,2.63a,2.63b
echo F_DONE "$D/F_full_s$seed.wav"
