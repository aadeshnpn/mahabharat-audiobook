"""ASR check of chant clips (run with proto/.venv-pocket python; multilingual faster-whisper 'small').
Transcribes each clip as Hindi/Sanskrit (Devanagari) and scores character similarity to the reference half-verse.
usage: score.py -> build/title_song/scores.json"""
import json, re, sys, difflib, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
from faster_whisper import WhisperModel
CFG = json.loads((ROOT / "configs/title_song.json").read_text())
REF = [re.sub(r"[\s।॥'ऽ\-]", "", s) for s in CFG["devanagari"]]
model = WhisperModel("small", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^\u0900-\u0963\u0966-\u097F]", "", s).replace("ऽ", "")
sp = ROOT / "build/title_song/scores.json"
out = json.loads(sp.read_text()) if sp.exists() else {}
for wav in sorted((ROOT / "build/title_song/clips").glob("*.wav")):
    if wav.name in out: continue
    h = int(re.search(r"_h(\d)_", wav.name).group(1)) - 1
    best = None
    import librosa
    audio = librosa.load(str(wav), sr=16000, mono=True)[0]
    for lang in ("hi",):
        segs, _ = model.transcribe(audio, language=lang, beam_size=5, temperature=0)
        text = "".join(s.text for s in segs)
        ref = REF[2] + REF[3] if "_r7_" in wav.name else REF[0] + REF[1] if "_r8_" in wav.name else REF[h]
        score = difflib.SequenceMatcher(None, norm(text), ref).ratio()
        if best is None or score > best[0]: best = (score, lang, text.strip())
    out[wav.name] = {"score": round(best[0], 3), "lang": best[1], "asr": best[2]}
    print(wav.name, out[wav.name], flush=True)
(ROOT / "build/title_song/scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
