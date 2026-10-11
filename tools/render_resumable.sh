#!/usr/bin/env bash
# Resumable episode render: every line is cached on completion; rerun this script after any interruption.
# usage: tools/render_resumable.sh episodes/ep01.yaml [max_passes]
set -u
cd "$(dirname "$0")/.."
spec=$1; passes=${2:-4}; py=proto/.venv-vox/bin/python
for i in $(seq 1 "$passes"); do
  echo "== pass $i $(date +%T)"
  PYTHONPATH=src MBH_VOX_PYTHON=$py $py -m mbh.cli episode render "$spec" 2>&1 | rg -v "it/s\]|^\s*$"
  left=$(PYTHONPATH=src $py -m mbh.cli episode render --dry-run "$spec" | rg -c "^(would_render|missing_voice)" || true)
  echo "== left: ${left:-0}"; [ "${left:-0}" = 0 ] && { echo RENDER_DONE; exit 0; }
done
echo RENDER_INCOMPLETE; exit 1
