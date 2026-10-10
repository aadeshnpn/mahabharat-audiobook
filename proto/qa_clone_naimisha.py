import json, glob, re, numpy as np, librosa
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
asr = WhisperModel("small.en", device="cpu", compute_type="int8"); enc = VoiceEncoder("cpu")
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
def wer(r, h):
    d = np.arange(len(h) + 1)
    for i, rw in enumerate(r, 1):
        p = d.copy(); d[0] = i
        for j, hw in enumerate(h, 1): d[j] = min(p[j] + 1, d[j - 1] + 1, p[j - 1] + (rw != hw))
    return d[-1] / max(1, len(r))
E_ = lambda p: enc.embed_utterance(preprocess_wav(p))
REFS = {p.split("/")[-2]: E_(p) for p in sorted(glob.glob("../voices/*/ref.wav")) if "naimisha" not in p}
log = json.load(open("logs/clone_naimisha.json")); own = {}; out = []
for r in log:
    if r["ref"] not in own: own[r["ref"]] = E_(f"out/design/naimisha_rishis-{r['ref']}.wav")
    y, sr = librosa.load("../" + r["out"], sr=16000)
    hyp = " ".join(s.text for s in asr.transcribe(y.astype(np.float32), beam_size=5, language="en")[0]).strip()
    e = E_("../" + r["out"]); sims = {k: round(float(e @ v), 3) for k, v in REFS.items()}
    row = dict(ref=r["ref"], line=r["line"][-4:], wer=round(wer(norm(r["text"]), norm(hyp)), 3), own_ref_sim=round(float(e @ own[r["ref"]]), 3),
               narr=dict(sauti=sims["sauti"], vaisampayana=sims["vaisampayana"], bhishma=sims["bhishma"]), max_other=max(sims.values()), closest_other=max(sims, key=sims.get),
               identity_ok=float(e @ own[r["ref"]]) > max(sims.values()), dur_s=round(len(y) / sr, 1), asr=hyp)
    out.append(row); print(row, flush=True)
json.dump(out, open("logs/qa_clone_naimisha.json", "w"), indent=1)
