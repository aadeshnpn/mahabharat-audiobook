"""Clone-test Naimisha ref candidates on held-out pilot lines with the episode renderer's own backend (VoxCPM2Backend)."""
import json, time, sys
from pathlib import Path
sys.path.insert(0, "src")
from mbh.episode.render import VoxCPM2Backend, instruction_for
from mbh.episode.models import ScriptLine
s = json.load(open("episodes/ep00_pilot.script.json")); L = {l["id"]: l for l in s["lines"]}
ids = ["ep00_pilot-0023", "ep00_pilot-0033"]
refs = {k: f"proto/out/design/naimisha_rishis-{k}.wav" for k in ("A_aged_sage_vox_s10_0", "A_aged_sage_vox_s10_0_chorus", "D_hermit_elders_vox_s10_0", "C_light_elder_vox_s10_1")}
be = VoxCPM2Backend(); out = Path("proto/out/clone_naimisha"); out.mkdir(parents=True, exist_ok=True); log = []
for k, ref in refs.items():
    for i in ids:
        l = L[i]; inst = f"({l['emotion'].replace('_',' ')}, {l.get('pace') or 'measured'} pace)"
        try: inst = instruction_for(ScriptLine(**l))
        except Exception as e: pass
        t = time.time(); dst = out / f"{k}__{i[-4:]}.wav"
        be.synthesize(text=f"{inst} {l['tts_text']}", instruction=inst, reference_wav=Path(ref), out_wav=dst, params={"steps": 10, "cfg_value": 2.0})
        r = dict(ref=k, line=i, out=str(dst), gen_s=round(time.time() - t, 1), text=l["text"], inst=inst); print(r, flush=True); log.append(r)
json.dump(log, open("proto/logs/clone_naimisha.json", "w"), indent=1)
