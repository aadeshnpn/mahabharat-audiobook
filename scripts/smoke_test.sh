#!/usr/bin/env bash
# (audio is passed to Whisper as an array: the pinned PyAV can't open files for faster-whisper 1.2.1)
# Render one short line end to end and (if the QA venv exists) check it with ASR. Exit 0 = pipeline works.
set -euo pipefail
cd "$(dirname "$0")/.."
proto/.venv-vox/bin/python scripts/smoke_render.py
if [ -x proto/.venv-pocket/bin/python ]; then
  proto/.venv-pocket/bin/python - <<'P'
import json, re, librosa
from faster_whisper import WhisperModel
r = json.load(open("build/smoke_test.json")); m = WhisperModel("small.en", device="cpu", compute_type="int8")
hyp = " ".join(s.text for s in m.transcribe(librosa.load(r["out"], sr=16000)[0], beam_size=5, language="en")[0])
w = lambda s: set(re.sub(r"[^a-z ]", " ", s.lower()).split()); ref = w(r["text"]); hit = len(ref & w(hyp)) / max(1, len(ref))
print(f"ASR: {hyp.strip()!r}  word recall {hit:.0%}"); raise SystemExit(0 if hit >= 0.7 else 1)
P
fi
echo "SMOKE TEST PASSED"
