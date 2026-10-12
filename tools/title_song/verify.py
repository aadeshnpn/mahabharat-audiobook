"""ASR check of a finished title-song mix, segment by segment (drone + reverb included). Run with proto/.venv-pocket.
usage: verify.py build/title_song/v1  (reads v1.wav and the v1.json written by mix.py)"""
import json, re, sys, difflib
from pathlib import Path
import librosa
from faster_whisper import WhisperModel
ROOT = Path(__file__).resolve().parents[2]
c = json.loads((ROOT / "configs/title_song.json").read_text())
norm = lambda s: re.sub(r"[^\u0900-\u0963\u0966-\u097F]", "", s).replace("ऽ", "")
R = [norm(x) for x in c["devanagari"]]
m = WhisperModel("small", device="cpu", compute_type="int8")
for base in sys.argv[1:]:
    info = json.loads(Path(base + ".json").read_text()); y = librosa.load(base + ".wav", sr=16000)[0]; sc = []
    for name, s, e in zip(info["clips"], info["starts"], info["ends"]):
        h = int(re.search(r"_h(\d)_", name).group(1)) - 1
        seg = y[int((s - 0.3) * 16000):int((e + 0.6) * 16000)]
        t = "".join(x.text for x in m.transcribe(seg, language="hi", beam_size=5, temperature=0, condition_on_previous_text=False, no_repeat_ngram_size=3)[0])
        sc.append(difflib.SequenceMatcher(None, norm(t), R[h]).ratio()); print(f"  h{h + 1} {sc[-1]:.2f} {t.strip()}")
    print(base, "mean", round(sum(sc) / len(sc), 3))
