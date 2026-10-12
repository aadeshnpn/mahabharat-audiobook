"""Smoke test: render ONE short real line through the full pipeline (build -> VoxCPM2 render -> -16 LUFS assemble).
Run with the render venv:  proto/.venv-vox/bin/python scripts/smoke_render.py   (or scripts/smoke_test.sh)
Uses a throwaway cache, so it always really synthesizes (~10 GB peak RAM during model load, ~1-3 min on 8 cores).
If the QA venv exists, the shell wrapper also transcribes the clip and checks the words."""
import json, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.spec import load_spec
from mbh.episode.build import build_episode
from mbh.episode.render import VoxCPM2Backend, render_script, reference_wav
from mbh.episode.assemble import assemble
from mbh.cli import load_timing
from mbh.episode.audioio import read_mono
from mbh.episode.loudness import integrated_lufs
spec = load_spec(ROOT / "episodes/ep01.yaml"); script = build_episode(spec); timing, settings = load_timing(spec.timing_path)
line = min((l for l in script.lines if reference_wav(l.voice_id).exists() and len(l.text.split()) >= 6), key=lambda l: len(l.text))
script.lines = [line]
tmp = Path(tempfile.mkdtemp(prefix="mbh_smoke_")); t = time.time()
res = render_script(script, VoxCPM2Backend(), settings, cache_dir=tmp / "cache")
out = ROOT / "build/smoke_test.wav"; out.parent.mkdir(exist_ok=True)
assemble(script, res, timing, settings, out, music_cfg=None)
y, sr = read_mono(out); dur = len(y) / sr; lufs = integrated_lufs(y, sr)
ok = res[0].status == "rendered" and 0.8 < dur < 30 and lufs is not None and abs(lufs - settings.loudness_lufs) < 1.0
r = dict(ok=ok, line=line.id, speaker=line.speaker, text=line.text, render_s=round(time.time() - t, 1), dur_s=round(dur, 2), lufs=round(lufs or -99, 1), out=str(out))
print(json.dumps(r)); (ROOT / "build/smoke_test.json").write_text(json.dumps(r, indent=1)); sys.exit(0 if ok else 1)
