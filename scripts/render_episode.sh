#!/usr/bin/env bash
# Build -> render (resumable) -> assemble dry + music -> MP3s at -16 LUFS [-> QA].  CPU only.
#   scripts/render_episode.sh episodes/ep01.yaml [--preset A|B|quiet] [--name ep01_full_v1] [--qa]
# Interrupted? Run it again: each line is cached in build/cache/voxcpm2/ the moment it is rendered.
set -euo pipefail
cd "$(dirname "$0")/.."
spec=$1; shift; preset=""; qa=0; name=""
while [ $# -gt 0 ]; do case $1 in --preset) preset=$2; shift;; --qa) qa=1;; --name) name=$2; shift;; *) echo "unknown option $1"; exit 2;; esac; shift; done
id=$(basename "$spec" .yaml); name=${name:-${id}_full}
VOX=proto/.venv-vox/bin/python; QA_PY=proto/.venv-pocket/bin/python
export PYTHONPATH=src MBH_VOX_PYTHON=$VOX
mkdir -p samples logs build
echo "== build $(date +%T)"; $VOX -m mbh.cli episode build "$spec"
echo "== render $(date +%T)"; tools/render_resumable.sh "$spec" "${MBH_RENDER_PASSES:-20}"   # each pass reloads the model; OOM-killed passes just resume
echo "== assemble dry $(date +%T)"
$VOX -m mbh.cli episode assemble "$spec" --no-music --out "build/$name.wav" > "build/$name.report.json"
echo "== assemble music ${preset:-(configs/music.yaml default)} $(date +%T)"
$VOX -m mbh.cli episode assemble "$spec" --music ${preset:+--music-preset "$preset"} \
  --out "build/${name}_music.wav" --music-stem "build/${name}_music_stem.wav" > "build/${name}_music.report.json"
for f in "$name" "${name}_music"; do $VOX tools/encode_mp3.py "build/$f.wav" "samples/$f.mp3"; done
if [ $qa = 1 ]; then
  echo "== QA $(date +%T)"
  $QA_PY tools/qa_episode.py "episodes/$id.script.json" "episodes/$id.render.json" --out "build/qa_$id.json"
  $QA_PY tools/qa_music.py "episodes/$id.script.json" "build/${name}_music.report.json" "build/${name}_music.wav" \
    "build/$name.wav" "build/${name}_music_stem.wav" --out "build/qa_music_$id.json"
fi
echo "== done $(date +%T)"
