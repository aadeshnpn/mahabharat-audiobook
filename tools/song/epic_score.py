"""Score sweep candidates: ASR (best-window vs the Devanagari text) + ears proxies. Writes OUTDIR/scores.json. Resumable.
usage (proto/.venv-pocket): PYTHONPATH=src python tools/song/epic_score.py configs/songs/title_song.yaml OUTDIR"""
import json, sys
from pathlib import Path
from mbh.song.spec import load_song
from mbh.song.asr import score_file
from mbh.song.ears import sung_metrics
spec = load_song(sys.argv[1]); d = Path(sys.argv[2]); E = spec.raw["epic"]
ref = " ".join(l.text for l in spec.lines if l.id in E["lines"])
sp = d / "scores.json"; S = json.loads(sp.read_text()) if sp.exists() else {}
for w in sorted(d.glob("*.wav")):
    if w.name in S or not w.with_suffix(".json").exists(): continue
    import subprocess
    voc = d / "sep" / "htdemucs" / w.stem / "vocals.wav"
    if not voc.exists():
        subprocess.run([sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs", "-o", str(d / "sep"), str(w)], check=True, capture_output=True)
    r = score_file(voc, ref); r["asr_mix"] = score_file(w, ref)["score"]; r.update(sung_metrics(w, vocals=voc)); S[w.name] = r
    sp.write_text(json.dumps(S, ensure_ascii=False, indent=1)); print(w.name, json.dumps(r, ensure_ascii=False), flush=True)
