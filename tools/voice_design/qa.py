"""Score voice candidates (run with the QA venv: proto/.venv-pocket).
usage: qa.py design BRIEFS.json        -> each designed candidate: ASR WER vs its line, median F0, words/min,
                                         cosine (resemblyzer) to every approved voice and to the other characters' candidates
       qa.py clone CHAR [CHAR ...]     -> each clone test in voices/<char>/candidates/clone_log.json: WER, similarity to its
                                         own candidate (identity) vs the closest approved voice
Rule of thumb used so far: WER ~0 (names aside), max cosine to any approved voice <= ~0.78 (the approved voices'
own pairwise max), and in clone tests own-candidate similarity clearly above every other voice (~0.85+).
Writes build/voice_qa_<mode>.json.
"""
import json, re, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
import numpy as np, librosa
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
mode, args = sys.argv[1], sys.argv[2:]
asr = WhisperModel("small.en", device="cpu", compute_type="int8"); enc = VoiceEncoder("cpu")
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
def wer(r, h):
    d = np.arange(len(h) + 1)
    for i, rw in enumerate(r, 1):
        p = d.copy(); d[0] = i
        for j, hw in enumerate(h, 1): d[j] = min(p[j] + 1, d[j - 1] + 1, p[j - 1] + (rw != hw))
    return round(float(d[-1] / max(1, len(r))), 3)
E_ = lambda p: enc.embed_utterance(preprocess_wav(str(p)))
def hear(p):
    y, _ = librosa.load(str(p), sr=16000)
    return y, " ".join(s.text for s in asr.transcribe(y, beam_size=5, language="en", condition_on_previous_text=False)[0]).strip()
rows = []
if mode == "design":
    briefs = json.loads(Path(args[0]).read_text()); chars = {b["id"].split("-")[0] for b in briefs}
    REFS = {p.parent.name: E_(p) for p in sorted(ROOT.glob("voices/*/ref.wav")) if p.parent.name not in chars}
    files = [(b, f) for b in briefs for f in sorted(ROOT.glob(f"voices/{b['id'].split('-')[0]}/candidates/{b['id']}_vox_s*_[0-9].wav"))]
    emb = {f: E_(f) for _, f in files}
    for b, f in files:
        char = b["id"].split("-")[0]; y, hyp = hear(f); f0, _, _ = librosa.pyin(y, fmin=50, fmax=400, sr=16000)
        sims = {k: round(float(emb[f] @ v), 3) for k, v in REFS.items()}
        other = [float(emb[f] @ e) for g, e in emb.items() if not g.name.startswith(char + "-")]
        r = dict(file=f.name, wer=wer(norm(b["line"]), norm(hyp)), f0_hz=round(float(np.nanmedian(f0)), 1),
                 wpm=round(len(norm(b["line"])) / (len(y) / 16000) * 60), max_sim_approved=max(sims.values()), closest=max(sims, key=sims.get),
                 max_sim_new_others=round(max(other), 3) if other else None, asr=hyp)
        rows.append(r); print(f"{r['file']:44s} WER {r['wer']:.3f}  F0 {r['f0_hz']:6.1f}  wpm {r['wpm']:4d}  max {r['max_sim_approved']:.3f} {r['closest']:15s} new {r['max_sim_new_others']}", flush=True)
else:
    REFS = {p.parent.name: E_(p) for p in sorted(ROOT.glob("voices/*/ref.wav")) if p.parent.name not in args}
    for char in args:
        for c in json.loads((ROOT / f"voices/{char}/candidates/clone_log.json").read_text()):
            y, hyp = hear(c["out"]); e = E_(c["out"]); sims = {k: float(e @ v) for k, v in REFS.items()}; own = float(e @ E_(c["ref"]))
            r = dict(ref=Path(c["ref"]).stem, line=c["line"], wer=wer(norm(c["text"]), norm(hyp)), own=round(own, 3),
                     max_other=round(max(sims.values()), 3), closest=max(sims, key=sims.get), identity_ok=own > max(sims.values()), asr=hyp)
            rows.append(r); print(f"{r['ref']:40s} {r['line']}  WER {r['wer']:.3f}  own {r['own']:.3f}  max_other {r['max_other']:.3f} {r['closest']:15s} {'OK' if r['identity_ok'] else 'IDENTITY?'}", flush=True)
(ROOT / "build").mkdir(exist_ok=True); (ROOT / f"build/voice_qa_{mode}.json").write_text(json.dumps(rows, indent=1))
