"""Clone-test candidates on real (held-out) episode lines with the episode renderer's own backend (render venv).
usage: clone.py EPISODE.yaml LINE_ID[,LINE_ID] CANDIDATE.wav [CANDIDATE.wav ...]
Writes <candidate>__<line4>.wav next to each candidate and appends to voices/<char>/candidates/clone_log.json.
Pick lines the candidate was NOT designed on, in the emotions the character really uses.
"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.spec import load_spec
from mbh.episode.build import build_episode
from mbh.episode.render import VoxCPM2Backend, instruction_for
spec, ids, cands = Path(sys.argv[1]), sys.argv[2].split(","), [Path(p) for p in sys.argv[3:]]
lines = {l.id: l for l in build_episode(load_spec(spec)).lines}
be = VoxCPM2Backend()
for c in cands:
    logp = c.parent / "clone_log.json"; log = json.loads(logp.read_text()) if logp.exists() else []
    for i in ids:
        l = lines[i]; dst = c.with_name(f"{c.stem}__{i[-4:]}.wav")
        if dst.exists(): continue
        inst = instruction_for(l); t = time.time()
        be.synthesize(text=f"{inst} {l.tts_text}", instruction=inst, reference_wav=c, out_wav=dst, params={"steps": 10, "cfg_value": 2.0})
        r = dict(ref=str(c), line=i, out=str(dst), text=l.text, inst=inst, gen_s=round(time.time() - t, 1))
        print(r, flush=True); log.append(r); logp.write_text(json.dumps(log, indent=1))
