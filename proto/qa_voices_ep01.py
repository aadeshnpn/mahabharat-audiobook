"""QA for the ep01 voice candidates (Vyasa, Brahma, Ganesa); run with .venv-pocket python from proto/.
Design stage:  qa_voices_ep01.py design   -> logs/qa_design_ep01.json
Clone stage:   qa_voices_ep01.py clone    -> logs/qa_clone_ep01.json   (needs logs/clone_ep01.json)
Per clip: Whisper WER vs the scripted line, median F0, words/min, resemblyzer cosine to every approved
voice (voices/*/ref.wav) and to the other new characters' candidates; clone stage adds identity vs own ref."""
import json, glob, re, sys, numpy as np, librosa
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
stage = sys.argv[1]
asr = WhisperModel("small.en", device="cpu", compute_type="int8"); enc = VoiceEncoder("cpu")
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
def wer(r, h):
    d = np.arange(len(h) + 1)
    for i, rw in enumerate(r, 1):
        p = d.copy(); d[0] = i
        for j, hw in enumerate(h, 1): d[j] = min(p[j] + 1, d[j - 1] + 1, p[j - 1] + (rw != hw))
    return d[-1] / max(1, len(r))
E_ = lambda p: enc.embed_utterance(preprocess_wav(p))
REFS = {p.split("/")[-2]: E_(p) for p in sorted(glob.glob("../voices/*/ref.wav")) if p.split("/")[-2] not in ("vyasa", "brahma", "ganesa")}
briefs = {b["id"]: b for fn in ("voices_ep01.json", "voices_ep01_vyasa2.json") for b in json.load(open(fn))}
cands = sorted(f for f in glob.glob("out/design/*_vox_s10_*.wav") if f.split("/")[-1].split("-")[0] in ("vyasa", "brahma", "ganesa"))
cemb = {f: E_(f) for f in cands}
def hear(path):
    y, sr = librosa.load(path, sr=16000)
    return y, " ".join(s.text for s in asr.transcribe(y.astype(np.float32), beam_size=5, language="en", condition_on_previous_text=False)[0]).strip()
def others(char, e):
    """max cosine to candidates of the OTHER new characters"""
    return round(max(float(e @ v) for f, v in cemb.items() if not f.split("/")[-1].startswith(char)), 3)
out = {}
if stage == "design":
    for f in cands:
        name = f.split("/")[-1]; bid = name.rsplit("_vox_", 1)[0]; char = bid.split("-")[0]
        y, hyp = hear(f); f0, _, _ = librosa.pyin(y, fmin=50, fmax=400, sr=16000)
        sims = {k: round(float(cemb[f] @ v), 3) for k, v in REFS.items()}
        line = briefs[bid]["line"]
        out[name] = dict(char=char, wer=round(wer(norm(line), norm(hyp)), 3), f0=round(float(np.nanmedian(f0)), 1),
                         wpm=round(len(norm(line)) / (len(y) / 16000) * 60, 1), max_sim_existing=max(sims.values()),
                         closest=max(sims, key=sims.get), max_sim_new_others=others(char, cemb[f]), sims=sims, asr=hyp)
        r = out[name]; print(name, "WER", r["wer"], "F0", r["f0"], "wpm", r["wpm"], "max", r["max_sim_existing"], r["closest"], "new", r["max_sim_new_others"], flush=True)
    ks = list(REFS); base = [float(REFS[a] @ REFS[b]) for i, a in enumerate(ks) for b in ks[i + 1:]]
    json.dump(dict(clips=out, approved_pairwise_max=round(max(base), 3), approved_pairwise_mean=round(float(np.mean(base)), 3)), open("logs/qa_design_ep01.json", "w"), indent=1)
    print("approved pairwise max", round(max(base), 3), "mean", round(float(np.mean(base)), 3))
else:
    rows = []
    for r in json.load(open("logs/clone_ep01.json")):
        y, hyp = hear("../" + r["out"]); e = E_("../" + r["out"])
        own = float(e @ E_("../" + r["ref_path"])); sims = {k: round(float(e @ v), 3) for k, v in REFS.items()}
        row = dict(ref=r["ref"], line=r["line"][-4:], wer=round(wer(norm(r["text"]), norm(hyp)), 3), own_ref_sim=round(own, 3),
                   max_other=max(sims.values()), closest_other=max(sims, key=sims.get), identity_ok=own > max(sims.values()), asr=hyp)
        rows.append(row); print(row, flush=True)
    json.dump(rows, open("logs/qa_clone_ep01.json", "w"), indent=1)
