"""Render harness jobs with the episode renderer's VoxCPM2 backend (run with proto/.venv-vox python). Resumable."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.render import VoxCPM2Backend
jobs = json.load(open(sys.argv[1])); be = VoxCPM2Backend(); t0 = time.time(); n = 0
for j in jobs:
    out = ROOT / j["out"]
    if out.exists() and out.stat().st_size: continue
    out.parent.mkdir(parents=True, exist_ok=True); t = time.time()
    be.synthesize(text=f"(warm, measured pace) {j['text']}", instruction="", reference_wav=ROOT / "voices" / j["voice"] / "ref.wav",
                  out_wav=out, params={"steps": 10, "cfg_value": 2.0}); n += 1
    print(json.dumps(dict(out=j["out"], gen_s=round(time.time() - t, 1))), flush=True)
print(json.dumps(dict(rendered=n, wall_s=round(time.time() - t0, 1))), flush=True)
