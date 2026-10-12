"""Clone-test ep01 ref candidates on held-out Episode 1 lines with the episode renderer's backend.
usage (from repo root, vox venv): proto/clone_test_ep01.py REF_ID[,REF_ID...]   REF_ID = design file stem, e.g. vyasa-A_seer_poet_vox_s10_0"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, "src")
from mbh.episode.render import VoxCPM2Backend, instruction_for
from mbh.episode.models import ScriptLine
s = json.load(open("episodes/ep01.script.json"))
lines = [ScriptLine(**{**l, "src_span": tuple(l["src_span"]) if l.get("src_span") else None}) for l in s["lines"]]
by_text = lambda start: next(l for l in lines if l.text.startswith(start))
TEST = {  # held-out lines (not the design text), Episode 1
    "vyasa": [by_text("O guide of the Ganas"), by_text("Wherever there be anything")],
    "brahma": [by_text("There shall be no poets"), by_text("Let Ganesa be thought of")],
    "ganesa": [by_text("I will become the writer")],
}
be = VoxCPM2Backend(); out = Path("proto/out/clone_ep01"); out.mkdir(parents=True, exist_ok=True)
logp = Path("proto/logs/clone_ep01.json"); log = json.loads(logp.read_text()) if logp.exists() else []
for ref in sys.argv[1].split(","):
    char = ref.split("-")[0]; ref_path = f"proto/out/design/{ref}.wav"
    for l in TEST[char]:
        dst = out / f"{ref}__{l.id[-4:]}.wav"
        if any(r["out"] == str(dst) for r in log): continue
        inst = instruction_for(l); t = time.time()
        be.synthesize(text=f"{inst} {l.tts_text}", instruction=inst, reference_wav=Path(ref_path), out_wav=dst, params={"steps": 10, "cfg_value": 2.0})
        r = dict(ref=ref, ref_path=ref_path, line=l.id, out=str(dst), gen_s=round(time.time() - t, 1), text=l.text, inst=inst)
        print(r, flush=True); log.append(r); logp.write_text(json.dumps(log, indent=1))
