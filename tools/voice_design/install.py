"""Install a chosen candidate as a character's voice (app venv: .venv).
usage: install.py CHARACTER_ID CANDIDATE.wav [--prompt "..."] [--notes "..."]
Backs up any existing ref (ref_replaced_<unix>.wav), copies the candidate to voices/<id>/ref.wav, levels it to
-20 LUFS / -1.5 dBTP (the renderer's convention; lines are later normalized to -16 LUFS), attaches it in the
web-app DB, and rewrites voices/registry.json. Commit voices/<id>/ref.wav + voices/registry.json afterwards.
If the web app is running you can instead pick the candidate in its Voice panel, then run tools/export_voice_registry.py.
"""
import argparse, shutil, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from mbh.voices.normalize_refs import normalize_ref
from mbh.webapp.db import Store
ap = argparse.ArgumentParser(); ap.add_argument("cid"); ap.add_argument("candidate"); ap.add_argument("--prompt"); ap.add_argument("--notes", default="")
a = ap.parse_args()
st = Store(); c = st.get_character(a.cid)
if not c: sys.exit(f"unknown character {a.cid!r}: add it to src/mbh/characters/extracted/ and re-seed first")
d = ROOT / "voices" / a.cid; d.mkdir(parents=True, exist_ok=True); ref = d / "ref.wav"
if ref.exists(): ref.rename(d / f"ref_replaced_{int(time.time())}.wav")
shutil.copy(a.candidate, ref); print(normalize_ref(ref, -20.0, -1.5))
st.update_character(a.cid, {"voice_clip": f"voices/{a.cid}/ref.wav", "voice_engine": "voxcpm2 (10 steps)",
                            "voice_prompt": a.prompt or c["voice_prompt"], "voice_notes": a.notes or f"Selected {Path(a.candidate).stem}"})
subprocess.run([sys.executable, str(ROOT / "tools/export_voice_registry.py")], check=True)
