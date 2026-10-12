"""Write voices/registry.json: the tracked record of every approved voice (what the web-app DB holds, minus the DB).
usage: python tools/export_voice_registry.py            (reads data/mbh.sqlite3; run after attaching/approving a voice)
A fresh clone seeds the web app from this file (mbh.webapp.seed), and the episode renderer only needs voices/<id>/ref.wav.
"""
import hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from mbh.webapp.db import Store
st = Store(); chars = st.list_characters()
users = {}
for c in chars:
    if c.get("voice_group"): users.setdefault(c["voice_group"], []).append(c["id"])
out = {}
for c in sorted(chars, key=lambda c: c["id"]):
    ref = ROOT / f"voices/{c['id']}/ref.wav"
    if not (c.get("voice_clip") and ref.exists()): continue
    out[c["id"]] = dict(name=c["name"], ref="voices/%s/ref.wav" % c["id"], ref_sha256=hashlib.sha256(ref.read_bytes()).hexdigest(),
                        engine=c.get("voice_engine", ""), prompt=c.get("voice_prompt", ""), sample_line=c.get("sample_line", ""),
                        notes=c.get("voice_notes", ""), shared_by=sorted(users.get(c["id"], [])))
reg = dict(about="Approved voices. Each ref.wav is a VoxCPM2 voice-design clip leveled to -20 LUFS; the renderer clones it. "
                 "Design briefs/candidates: proto/voices*.json + tools/voice_design/. Characters with voice_group use that group's voice.",
           voices=out)
(ROOT / "voices/registry.json").write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
print(len(out), "voices ->", "voices/registry.json")
