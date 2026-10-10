"""Score harness clips: ASR -> target words -> phonemes vs intended (run with proto/.venv-pocket python).
usage: score.py JOBS.json [JOBS2.json ...] -> writes build/pron/scores.json (merged, keyed by out path)."""
import json, re, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
import numpy as np, librosa, cmudict
from faster_whisper import WhisperModel
import g2p_en.g2p as G
from mbh.episode.pronounce import extract_between, extract_target, key_similarity, looks_spelled_out, phoneme_similarity

CMU = cmudict.dict()
def _g2p_model():
    g = G.G2p.__new__(G.G2p)  # skip nltk downloads (blocked here); use only the neural predictor
    g.graphemes = ["<pad>", "<unk>", "</s>"] + list("abcdefghijklmnopqrstuvwxyz")
    g.phonemes = ["<pad>", "<unk>", "<s>", "</s>"] + "AA0 AA1 AA2 AE0 AE1 AE2 AH0 AH1 AH2 AO0 AO1 AO2 AW0 AW1 AW2 AY0 AY1 AY2 B CH D DH EH0 EH1 EH2 ER0 ER1 ER2 EY0 EY1 EY2 F G HH IH0 IH1 IH2 IY0 IY1 IY2 JH K L M N NG OW0 OW1 OW2 OY0 OY1 OY2 P R S SH T TH UH0 UH1 UH2 UW UW0 UW1 UW2 V W Y Z ZH".split()
    g.g2idx = {x: i for i, x in enumerate(g.graphemes)}; g.idx2g = dict(enumerate(g.graphemes))
    g.p2idx = {x: i for i, x in enumerate(g.phonemes)}; g.idx2p = dict(enumerate(g.phonemes)); g.load_variables(); return g
G2P = _g2p_model()
NUM = {"1": "one", "2": "two", "3": "three", "4": "four"}
def phones(text):
    out = []
    for w in re.findall(r"[a-z0-9']+", text.lower().replace("-", " ")):
        w = NUM.get(w, w).strip("'")
        if not w or w in ("the", "a", "o"): continue
        out += CMU[w][0] if w in CMU else G2P.predict(w)
    return out

asr = WhisperModel("small.en", device="cpu", compute_type="int8")
dest = ROOT / "build/pron/scores.json"; scores = json.loads(dest.read_text()) if dest.exists() else {}
for jf in sys.argv[1:]:
    for j in json.load(open(jf)):
        p = ROOT / j["out"]
        if not p.exists() or (j["out"] in scores and scores[j["out"]].get("mtime") == p.stat().st_mtime and "ksim" in scores[j["out"]]): continue
        y, sr = librosa.load(p, sr=16000)
        hyp = " ".join(s.text for s in asr.transcribe(y.astype(np.float32), beam_size=5, language="en")[0]).strip()
        _t, ok = extract_target(hyp); tgt = extract_between(hyp)
        inconclusive = tgt is None or not tgt.strip()
        tgt = tgt or ""; spelled = looks_spelled_out(tgt)
        psim = phoneme_similarity(phones(tgt), j["intended"]) if tgt else 0.0
        ksim = key_similarity(tgt, j.get("key", j["term"])) if tgt else 0.0
        sim = max(psim, ksim)
        heard_term = tgt.lower().replace("-", " ").strip(" ,.!?") == j["term"].lower().replace("-", " ")
        passed = (not inconclusive) and not spelled and (sim >= 0.8 or heard_term)
        scores[j["out"]] = dict(j, asr=hyp, heard=tgt, carrier_ok=ok, inconclusive=inconclusive, spelled=spelled, sim=sim, psim=psim, ksim=ksim, heard_term=heard_term,
                                passed=passed, dur_s=round(len(y) / sr, 2), mtime=p.stat().st_mtime)
        print(f"{j['voice']:13} {j['term']:18} {j['fmt']:4} {'PASS' if passed else ('retake' if inconclusive else 'fail')} sim={sim:.2f} (p{psim:.2f}/k{ksim:.2f}) {'SPELLED ' if spelled else ''}| {tgt}", flush=True)
dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(json.dumps(scores, indent=1))
