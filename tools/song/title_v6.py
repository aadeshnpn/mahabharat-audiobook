"""Title v6 builder. usage:
  PYTHONPATH=src proto/.venv-vox/bin/python tools/song/title_v6.py build [concept ...]   -> build/title_v6/<concept>.wav/.json
  PYTHONPATH=src proto/.venv-pocket/bin/python tools/song/title_v6.py asr [concept ...]   -> per-segment ASR on the masters"""
import json, sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
CFG = yaml.safe_load((ROOT / "configs/title_v6.yaml").read_text()); OUT = ROOT / "build/title_v6"
step, names = sys.argv[1], sys.argv[2:] or CFG["concepts"] + ["ending"]


def clips():
    import librosa, numpy as np
    from mbh.song.title6 import SR
    kt = ROOT / CFG["krishna_takes"]; S = json.loads((kt / "scores.json").read_text())
    def split_verse(y):
        y = librosa.effects.trim(y, top_db=35)[0]
        hop = 480; e = librosa.feature.rms(y=y, frame_length=1920, hop_length=hop)[0]; quiet = e < 0.08 * e.max()
        lo, hi = int(len(e) * 0.35), int(len(e) * 0.7); best, run, pos = 0, 0, lo
        for i in range(lo, hi):
            run = run + 1 if quiet[i] else 0
            if run > best: best, pos = run, i - run // 2
        return [librosa.effects.trim(y[:pos * hop], top_db=35)[0], librosa.effects.trim(y[pos * hop:], top_db=35)[0]]
    best = lambda vid: max((k for k in S if k.startswith(vid + "_")), key=lambda k: S[k]["score"])
    c, picks = {}, {}
    for vid, keys in (("v62", ("k62a", "k62b")), ("v63", ("k63a", "k63b"))):
        picks[vid] = best(vid); halves = split_verse(librosa.load(kt / "takes" / picks[vid], sr=SR)[0])
        c.update(zip(keys, halves))
    picks["e63b"] = best("e63b"); c["e63b"] = librosa.effects.trim(librosa.load(kt / "takes" / picks["e63b"], sr=SR)[0], top_db=35)[0]
    rep = json.loads((OUT / "hook.json").read_text()); h = librosa.load(OUT / "hook.dry.wav", sr=SR)[0]
    st = rep["lines"][0]["starts_s"] - CFG["hook_onset_s"]; h = h[int(max(0, st) * SR):]
    c["hook"] = h[: int((CFG["hook_onset_s"] + 6.5) * SR)]
    return c, picks


if step == "build":
    import numpy as np, soundfile as sf
    from mbh.song.title6 import SR, build
    from mbh.song.master import master_file
    c, picks = clips()
    for name in names:
        y, tl = build(name, c, CFG); raw = OUT / f"{name}.premaster.wav"
        sf.write(raw, (y / np.abs(y).max() * 0.9).T, SR, subtype="FLOAT")
        r = master_file(raw, OUT / f"{name}.wav", CFG["master"]["lufs"], CFG["master"]["true_peak_db"], 0.0, None, 0.02, 0.05)
        r.update(timeline=tl, takes=picks); (OUT / f"{name}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(name, r["seconds"], r["lufs"], flush=True)
elif step == "asr":
    import librosa
    from mbh.song.asr import best_window_similarity, transcribe
    for name in names:
        r = json.loads((OUT / f"{name}.json").read_text()); y = librosa.load(OUT / f"{name}.wav", sr=16000)[0]; rows = []
        for seg in r["timeline"]:
            key = seg["what"].split()[0]
            if key not in CFG["texts"]: continue
            a = int(max(0, seg["at"] - 0.2) * 16000); b = int((seg["at"] + seg["s"] + 0.3) * 16000)
            hyp = transcribe(y[a:b]); rows.append({"seg": seg["what"], "score": round(best_window_similarity(hyp, CFG["texts"][key]), 3), "asr": hyp})
        r["asr"] = rows; (OUT / f"{name}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(name, " ".join(f"{x['seg']}={x['score']}" for x in rows), flush=True)
