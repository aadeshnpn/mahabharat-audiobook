"""Title track v5: Gita 2.62-63 chanted by a Krishna voice over a tanpura bed (config: configs/title_song_krishna.json).
Steps (resumable; outputs in build/title_song_v5/):
  design  (.venv-vox)    4 voice designs speaking 2.62a -> voices/krishna/candidates/krishna-<id>.wav
  score   (.venv-pocket) ASR every design/take -> scores.json   (designs vs 2.62a; takes split at the caesura vs each half)
  takes   (.venv-vox)    whole-verse takes (v62, v63) per seed with the chosen design as reference, per-verse emotion
  mix     (.venv-vox)    best takes split at the caesura, long natural pauses, tanpura + swells + bells (+ conch), master
usage: PYTHONPATH=src <venv>/bin/python tools/title_song/krishna.py design|score|takes|mix [--voice A] [--out samples/x.wav]"""
import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
CFG = json.loads((ROOT / "configs/title_song_krishna.json").read_text())
B = ROOT / "build/title_song_v5"; CAND = ROOT / "voices/krishna/candidates"
SCORES = B / "scores.json"
ap = argparse.ArgumentParser(); ap.add_argument("step"); ap.add_argument("--voice"); ap.add_argument("--out")
a = ap.parse_args()

def scores():
    return json.loads(SCORES.read_text()) if SCORES.exists() else {}

def best_voice():
    if a.voice: return a.voice
    if CFG.get("voice"): return CFG["voice"]
    s = {k: v for k, v in scores().items() if k.startswith("design_")}
    return max(s, key=lambda k: s[k]["score"]).split("_")[1].split(".")[0]

def gen(model, text, out, seed, ref=None):
    import soundfile as sf, torch
    torch.manual_seed(seed); t = time.time()
    kw = dict(reference_wav_path=str(ref)) if ref else {}
    wav = model.generate(text=text, cfg_value=2.0, inference_timesteps=CFG["steps"], **kw)
    out.parent.mkdir(parents=True, exist_ok=True); sf.write(out, wav, model.tts_model.sample_rate if hasattr(model, "tts_model") else 48000)
    print(json.dumps({"out": str(out.relative_to(ROOT)), "s": round(time.time() - t, 1)}), flush=True)

def model():
    from mbh.episode.voxcpm2 import load_model
    return load_model()[0]

def split_verse(y):
    """Split a whole-verse take at the longest pause between 35% and 70% of its length (as tools/title_song/mix.py)."""
    import librosa
    y = librosa.effects.trim(y, top_db=35)[0]
    hop = 480; e = librosa.feature.rms(y=y, frame_length=1920, hop_length=hop)[0]; quiet = e < 0.08 * e.max()
    lo, hi = int(len(e) * 0.35), int(len(e) * 0.7); best, run, pos = 0, 0, lo
    for i in range(lo, hi):
        run = run + 1 if quiet[i] else 0
        if run > best: best, pos = run, i - run // 2
    cut = pos * hop
    return [librosa.effects.trim(y[:cut], top_db=35)[0], librosa.effects.trim(y[cut:], top_db=35)[0]]

if a.step == "design":
    m = None
    for d in CFG["designs"]:
        out = CAND / f"krishna-{d['id']}.wav"
        if out.exists(): continue
        m = m or model(); gen(m, f"({d['prompt']}){CFG['design_line']}", out, d["seed"])
elif a.step == "takes":
    v = best_voice(); m = None
    for vid, verse in CFG["verses"].items():
        for seed in CFG["take_seeds"]:
            out = B / "takes" / f"{vid}_{v}_s{seed}.wav"
            if out.exists(): continue
            m = m or model(); gen(m, f"({verse['instruction']}){verse['text']}", out, seed, CAND / f"krishna-{v}.wav")
elif a.step == "score":
    import librosa
    from mbh.song.asr import best_window_similarity, transcribe
    S = scores(); B.mkdir(parents=True, exist_ok=True)
    ref62a = CFG["verses"]["v62"]["halves"][0]
    for f in sorted(CAND.glob("krishna-*.wav")):
        k = f"design_{f.stem.split('-')[1]}"
        if k in S: continue
        hyp = transcribe(librosa.load(f, sr=16000)[0]); S[k] = {"score": round(best_window_similarity(hyp, ref62a), 3), "asr": hyp}
        print(k, S[k], flush=True); SCORES.write_text(json.dumps(S, ensure_ascii=False, indent=1))
    for f in sorted((B / "takes").glob("*.wav")):
        if f.name in S: continue
        y = librosa.load(f, sr=16000)[0]; halves = split_verse(y); refs = CFG["verses"][f.stem.split("_")[0]]["halves"]
        rows = [transcribe(h) for h in halves]
        sc = [round(best_window_similarity(h, r), 3) for h, r in zip(rows, refs)]
        S[f.name] = {"score": round(sum(sc) / 2, 3), "halves": sc, "asr": rows, "seconds": round(len(y) / 16000, 1)}
        print(f.name, S[f.name], flush=True); SCORES.write_text(json.dumps(S, ensure_ascii=False, indent=1))
elif a.step == "mix":
    import librosa, numpy as np, soundfile as sf
    from mbh.song.arrange import bell, swell, tanpura
    from mbh.song.epic import conch, hall
    from mbh.song.master import master_file
    from mbh.episode import loudness
    SR = 48000; M = CFG["mix"]; S = scores(); v = best_voice()
    ranked = {vid: sorted([k for k in S if k.startswith(f"{vid}_{v}_")], key=lambda k: -S[k]["score"]) for vid in CFG["verses"]}
    pick = {"v62": ranked["v62"][0], "v63": ranked["v63"][0], "v63b": (ranked["v63"][1:] or ranked["v63"])[0]}
    pick.update(CFG.get("takes", {}))
    halves = {}
    for key, name in pick.items():
        y = librosa.load(B / "takes" / name, sr=SR)[0]
        halves[key] = [loudness.normalize_line(h, SR, -18.0)[0] for h in split_verse(y)]
    t, place = M["lead_s"], []
    for key, i, gap in M["sequence"]:
        h = np.asarray(halves[key][i]); place.append((t, h, key, i)); t += len(h) / SR + gap
    total = t + M["tail_s"]; n = int(total * SR)
    voice = np.zeros(n)
    for start, h, *_ in place:
        k = int(start * SR); voice[k:k + len(h)] += h[: n - k]
    voice = hall(np.stack([voice, voice]), SR, M["voice_reverb"], 2.6)
    bed = tanpura(M["sa_hz"], total, SR)
    bed = np.stack([bed, bed]) if bed.ndim == 1 else bed
    bed = bed / (np.sqrt(np.mean(bed ** 2)) + 1e-9) * 0.1 * 10 ** (M["bed_db"] / 20)
    def add(sig, at, gain):
        k = int(at * SR); s = np.asarray(sig)[: n - k] * gain
        bed[:, k:k + len(s)] += s
    verse2 = next(st for st, h, key, i in place if key == "v63" and i == 0)
    repeat = next(st for st, h, key, i in place if key == "v63b" and i == 0)
    for at, g in [(verse2 - 4.0, 0.02), (repeat - 4.0, 0.02)]:
        add(swell(4.0, SR), at, g)
    for at in [M["lead_s"] - 2.5, verse2 - 1.0, total - M["tail_s"] + 1.0]:
        add(bell(2 * M["sa_hz"] * 2, SR), at, 0.012)
    if M.get("conch"):
        c = conch(SR) * 0.05; add(c, 0.2, 1.0)
    mix = voice + bed
    fi = int(1.5 * SR); mix[:, :fi] *= np.linspace(0, 1, fi)
    B.mkdir(parents=True, exist_ok=True); raw = B / "v5_premaster.wav"
    sf.write(raw, (mix / np.abs(mix).max() * 0.9).T, SR, subtype="FLOAT")
    out = Path(a.out or B / "title_song_v5_krishna.wav")
    r = master_file(raw, out, M["lufs"], M["true_peak_db"], 0.0, None, 0.05, 5.0)
    r["takes"] = pick; r["voice"] = v
    r["timeline"] = [{"at": round(st, 2), "verse": key, "half": i, "s": round(len(h) / SR, 1)} for st, h, key, i in place]
    out.with_suffix(".json").write_text(json.dumps(r, ensure_ascii=False, indent=1)); print(json.dumps(r, ensure_ascii=False))
