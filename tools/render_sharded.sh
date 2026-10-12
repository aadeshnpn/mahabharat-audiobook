#!/usr/bin/env bash
# Sharded episode render: each shard (~N minutes of lines) runs as its own short process with retries,
# writes build/shards/<episode>/shard_K.done, and the episode is assembled only after every shard is done.
# Line-level cache is shared, so re-running after any interruption resumes where it stopped.
# usage: tools/render_sharded.sh episodes/ep03.yaml [shard_minutes=4] [retries=6]
# long runs: setsid nohup tools/render_sharded.sh episodes/ep03.yaml > logs/render_ep03_sharded.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
spec=$1; mins=${2:-4}; retries=${3:-6}; py=proto/.venv-vox/bin/python
ep=$(basename "$spec" .yaml); marks=build/shards/$ep; mkdir -p "$marks"
mbh() { PYTHONPATH=src MBH_VOX_PYTHON=$py $py -m mbh.cli episode "$@"; }
mbh render --list-shards --shard-minutes "$mins" "$spec" | tee "$marks/plan.txt"
n=$(rg -o "shards=(\d+)" -r '$1' "$marks/plan.txt")
for k in $(seq 1 "$n"); do
  [ -f "$marks/shard_$k.done" ] && { echo "== shard $k/$n already done"; continue; }
  for t in $(seq 1 "$retries"); do
    echo "== shard $k/$n try $t $(date +%T)"
    mbh render --shard "$k" --shard-minutes "$mins" "$spec" 2>&1 | rg -v "it/s\]|^\s*$"
    left=$(mbh render --dry-run --shard "$k" --shard-minutes "$mins" "$spec" | rg -c "^(would_render|missing_voice)" || true)
    [ "${left:-0}" = 0 ] && { date +%FT%T > "$marks/shard_$k.done"; echo "== shard $k done"; break; }
    echo "== shard $k: $left lines left"
  done
  [ -f "$marks/shard_$k.done" ] || { echo SHARD_FAILED "$k"; exit 1; }
done
mbh render "$spec" | tail -1          # all cached: writes the full manifest without loading the model
mbh assemble --music --music-preset A "$spec" && echo EPISODE_DONE
