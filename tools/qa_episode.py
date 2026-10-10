"""QA a rendered episode, line by line (run with proto/.venv-pocket python).
usage: qa_episode.py episodes/<id>.script.json episodes/<id>.render.json [--out build/qa_<id>.json] [--only id,id]
Per line: Whisper WER vs the KMG text, lexicon names heard, speaker identity vs every voice ref,
cut-off ending, internal silences, repetition/insertion artifacts, duration vs expected, clipping."""
import argparse, json, re, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
import numpy as np, librosa, soundfile as sf
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
from mbh.episode.pronounce import key_similarity
from mbh.episode.lexicon import load_lexicon

def norm(t): return re.sub(r"[^a-z' ]", " ", t.lower().replace("-", " ")).split()
def align(r, h):
    """Levenshtein with counts (sub, del, ins)."""
    n, m = len(r), len(h); d = np.zeros((n + 1, m + 1), int); d[:, 0] = range(n + 1); d[0, :] = range(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (r[i - 1] != h[j - 1]))
    return int(d[n, m])

ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("manifest"); ap.add_argument("--out"); ap.add_argument("--only")
a = ap.parse_args()
lines = {l["id"]: l for l in json.loads(Path(a.script).read_text())["lines"]}
man = {r["line_id"]: r for r in json.loads(Path(a.manifest).read_text())}
only = set(a.only.split(",")) if a.only else None
NAMES = sorted({r.term for r in load_lexicon() if r.term[0].isupper()}, key=len, reverse=True)
asr = WhisperModel("small.en", device="cpu", compute_type="int8"); enc = VoiceEncoder("cpu")
refs = {p.parent.name: enc.embed_utterance(preprocess_wav(str(p))) for p in sorted((ROOT / "voices").glob("*/ref.wav"))}
WPM = 160.9
out = {}
for lid, line in lines.items():
    if only and lid not in only: continue
    r = man.get(lid)
    if not r or not r.get("path"): out[lid] = dict(status="missing"); continue
    y, sr = librosa.load(r["path"], sr=16000); dur = len(y) / sr
    segs = list(asr.transcribe(y.astype(np.float32), beam_size=5, language="en", word_timestamps=True)[0])
    hyp = " ".join(s.text for s in segs).strip(); words = [w for s in segs for w in (s.words or [])]
    R, H = norm(line["text"] if not line.get("non_kmg") else line["tts_text"]), norm(hyp)
    # gloss-stripped lines: score against what was spoken (tts_text) where they differ
    R2 = norm(line["tts_text"]); Rref = R2 if "gloss_stripped" in (line.get("flags") or []) else R
    errs = align(Rref, H); wer = errs / max(1, len(Rref))
    # names in the KMG text (word-level, possessive/plural tolerant), heard if a hyp window matches by sound key
    names = []
    for nm in NAMES:
        for m in re.finditer(rf"\b{re.escape(nm)}(?:'s|s)?\b", line["text"]):
            k = len(nm.split("-")) + nm.count(" ")
            cands = [" ".join(H[i:i + w]) for w in (k, k + 1, max(1, k - 1)) for i in range(len(H))]
            best = max([key_similarity(c, nm) for c in cands] or [0])
            names.append(dict(name=nm, heard=best >= 0.75, sim=round(best, 2)))
    # identity
    e = enc.embed_utterance(preprocess_wav(r["path"])); sims = {k: float(e @ v) for k, v in refs.items()}
    closest = max(sims, key=sims.get); own = sims.get(line["voice_id"], 0)
    # silences inside the line (> 1.2 s below -45 dBFS between first and last speech)
    hop = int(0.02 * sr); rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9); voiced = np.where(db > -45)[0]; gaps = []
    if len(voiced):
        run = 0
        for v in (db[voiced[0]:voiced[-1]] <= -45):
            run = run + 1 if v else 0
            if run * 0.02 > 1.2 and (not gaps or gaps[-1] != "x"): gaps.append("x")
        gaps = len(gaps)
    tail_db = float(20 * np.log10(np.sqrt(np.mean(y[-int(0.05 * sr):] ** 2)) + 1e-9)); peak_db = float(np.max(db)) if len(db) else -99
    lastw_ok = (not Rref) or any(key_similarity(Rref[-1], w) >= 0.75 for w in H[-3:]) if H else False
    trigrams = [" ".join(H[i:i + 3]) for i in range(len(H) - 2)]; rep = len(trigrams) - len(set(trigrams))
    exp = len(R2) / WPM * 60; ratio = dur / exp if exp else 1
    y48, sr48 = sf.read(r["path"]); clip = int(np.sum(np.abs(y48) >= 0.999))
    flags = []
    if wer > 0.25: flags.append(f"wer {wer:.2f}")
    if closest != line["voice_id"]: flags.append(f"voice closest={closest}")
    if gaps: flags.append(f"{gaps} silence>1.2s")
    if not lastw_ok: flags.append("ending not heard (cut-off?)")
    if tail_db > peak_db - 12: flags.append(f"abrupt end ({tail_db:.0f} dB)")
    if rep >= 2 or len(H) > 1.25 * len(Rref) + 2: flags.append("repetition/insertions")
    if ratio < 0.6 or ratio > 1.6: flags.append(f"duration x{ratio:.2f} of expected")
    if clip: flags.append(f"{clip} clipped samples")
    if any(not n["heard"] for n in names): flags.append("name missed: " + ",".join(n["name"] for n in names if not n["heard"]))
    out[lid] = dict(speaker=line["speaker"], voice_id=line["voice_id"], dur_s=round(dur, 2), words=len(Rref), errors=errs, wer=round(wer, 3),
                    own_sim=round(own, 3), closest=closest, margin=round(own - max(v for k, v in sims.items() if k != line["voice_id"]), 3),
                    names=names, silences=gaps, tail_db=round(tail_db, 1), dur_ratio=round(ratio, 2), flags=flags, asr=hyp, tts=line["tts_text"])
    print(lid[-4:], line["speaker"][:12].ljust(12), f"{dur:5.1f}s wer={wer:.2f} own={own:.2f} {'OK' if not flags else 'FLAG ' + '; '.join(flags)}", flush=True)
Path(a.out or ROOT / "build" / "qa_episode.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
