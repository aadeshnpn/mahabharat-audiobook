"""Design voice candidates from text briefs with VoxCPM2 on CPU (run with the render venv: proto/.venv-vox).
usage: design.py BRIEFS.json [--steps 10] [--only ID,ID]
BRIEFS.json: [{"id": "<character_id>-<label>", "n": 2, "prompt": "voice description, clear Indian English accent", "line": "text to speak"}]
Writes voices/<character_id>/candidates/<id>_vox_s<steps>_<k>.wav (resumable: existing files are skipped) and a JSON log line per clip.
"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
ap = argparse.ArgumentParser(); ap.add_argument("briefs"); ap.add_argument("--steps", type=int, default=10); ap.add_argument("--only")
a = ap.parse_args()
briefs = json.loads(Path(a.briefs).read_text()); only = set(a.only.split(",")) if a.only else None
todo = []
for b in briefs:
    if only and b["id"] not in only: continue
    char = b["id"].split("-")[0]
    for k in range(b.get("n", 1)):
        out = ROOT / f"voices/{char}/candidates/{b['id']}_vox_s{a.steps}_{k}.wav"
        if not out.exists(): todo.append((b, out))
print(f"{len(todo)} candidate(s) to design", flush=True)
if todo:
    import soundfile as sf
    from mbh.episode.voxcpm2 import load_model  # bf16 load: fits in ~10 GB peak RAM
    t = time.time(); model, sr = load_model(); print("load_s", round(time.time() - t, 1), flush=True)
    for b, out in todo:
        out.parent.mkdir(parents=True, exist_ok=True); t = time.time()
        wav = model.generate(text=f"({b['prompt']}){b['line']}", cfg_value=2.0, inference_timesteps=a.steps)
        sf.write(out, wav, sr); dt = time.time() - t
        print(json.dumps(dict(out=str(out.relative_to(ROOT)), gen_s=round(dt, 1), audio_s=round(len(wav) / sr, 1), rtf=round(dt * sr / len(wav), 2))), flush=True)
