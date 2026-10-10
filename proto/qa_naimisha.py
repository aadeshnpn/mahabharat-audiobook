"""QA for the Naimisha Rishis group-voice candidates (run with .venv-pocket python).
For each candidate (and a chorus/doubled variant of it): ASR WER vs the scripted line, median F0, speaking rate,
and resemblyzer cosine similarity to every approved reference voice (voices/*/ref.wav), esp. the narrators."""
import json, glob, re, sys, numpy as np, soundfile as sf, librosa
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav

LINE = json.load(open("voices_naimisha.json"))[0]["line"]
REFS = {p.split("/")[-2]: p for p in sorted(glob.glob("../voices/*/ref.wav")) if "naimisha" not in p}
asr = WhisperModel("small.en", device="cpu", compute_type="int8"); enc = VoiceEncoder("cpu")
norm = lambda s: re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()
def wer(r, h):
    d = np.arange(len(h) + 1)
    for i, rw in enumerate(r, 1):
        p = d.copy(); d[0] = i
        for j, hw in enumerate(h, 1): d[j] = min(p[j] + 1, d[j - 1] + 1, p[j - 1] + (rw != hw))
    return d[-1] / max(1, len(r))

def chorus(src, dst):
    """Subtle 3-voice doubling: dry + two copies detuned +/-0.25 semitone, delayed 21/34 ms, -7 dB; light 60 ms room tail."""
    y, sr = sf.read(src); y = y.astype(np.float32)
    out = y.copy()
    for st, ms in ((0.25, 21), (-0.25, 34)):
        v = librosa.effects.pitch_shift(y, sr=sr, n_steps=st); d = int(sr * ms / 1000)
        v = np.concatenate([np.zeros(d, np.float32), v])[:len(y)]; out += 0.45 * v
    tail = int(sr * 0.06); out[tail:] += 0.12 * out[:-tail]
    out = out / (np.max(np.abs(out)) + 1e-9) * 0.89; sf.write(dst, out, sr)

ref_emb = {k: enc.embed_utterance(preprocess_wav(p)) for k, p in REFS.items()}
files = sorted(glob.glob("out/design/naimisha_rishis-*_vox_s10_*.wav"))
files = [f for f in files if "_chorus" not in f]
allf = []
for f in files:
    c = f.replace(".wav", "_chorus.wav"); chorus(f, c); allf += [f, c]
res = {}
for f in allf:
    y, sr = librosa.load(f, sr=16000)
    segs, _ = asr.transcribe(y.astype(np.float32), beam_size=5, language="en"); hyp = " ".join(s.text for s in segs).strip()
    f0, _, _ = librosa.pyin(y, fmin=60, fmax=400, sr=sr); dur = len(y) / sr
    e = enc.embed_utterance(preprocess_wav(f)); sims = {k: round(float(e @ v), 3) for k, v in ref_emb.items()}
    res[f] = dict(wer=round(wer(norm(LINE), norm(hyp)), 3), f0_median_hz=round(float(np.nanmedian(f0)), 1), dur_s=round(dur, 1),
                  wpm=round(len(norm(LINE)) / dur * 60, 1), sim_narrators={k: sims[k] for k in ("sauti", "vaisampayana", "bhishma")},
                  max_sim_any=max(sims.values()), closest=max(sims, key=sims.get), asr=hyp)
    r = res[f]; print(f.split("/")[-1], "WER", r["wer"], "F0", r["f0_median_hz"], "wpm", r["wpm"], "narr", r["sim_narrators"], "max", r["max_sim_any"], r["closest"], flush=True)
# inter-reference baseline: how similar are the approved voices to each other?
ks = list(ref_emb); base = [float(ref_emb[a] @ ref_emb[b]) for i, a in enumerate(ks) for b in ks[i + 1:]]
narr_pairs = {f"{a}~{b}": round(float(ref_emb[a] @ ref_emb[b]), 3) for a, b in (("sauti", "vaisampayana"), ("sauti", "bhishma"), ("vaisampayana", "bhishma"))}
json.dump(dict(line=LINE, clips=res, approved_pairwise_max=round(max(base), 3), approved_pairwise_mean=round(float(np.mean(base)), 3),
               narrator_pairs=narr_pairs), open("logs/qa_naimisha.json", "w"), indent=1)
print("approved voices pairwise cos: max", round(max(base), 3), "mean", round(float(np.mean(base)), 3), narr_pairs)
