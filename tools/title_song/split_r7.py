"""Split whole-verse takes at the caesura: chant_r7_h4_* (2.63) -> r7a_h3 + r7t_h4, chant_r8_h2_* (2.62) -> r8a_h1 + r8t_h2 (run with .venv-vox)."""
import sys
from pathlib import Path
import librosa, soundfile as sf
ROOT = Path(__file__).resolve().parents[2]; D = ROOT / "build/title_song/clips"
sys.argv = [sys.argv[0], "x", "x", "x"]
src = (ROOT / "tools/title_song/mix.py").read_text()
exec(src[src.index("def split_verse"):src.index("clips, chosen = [], []")], globals())
for f in sorted(D.glob("chant_r7_h4_*.wav")) + sorted(D.glob("chant_r8_h2_*.wav")):
    y, sr = librosa.load(f, sr=48000)
    a, b = split_verse(librosa.effects.trim(y, top_db=35)[0])
    if "_r7_" in f.name: na, nb = f.name.replace("_r7_h4_", "_r7a_h3_"), f.name.replace("_r7_", "_r7t_")
    else: na, nb = f.name.replace("_r8_h2_", "_r8a_h1_"), f.name.replace("_r8_", "_r8t_")
    sf.write(D / na, a, sr); sf.write(D / nb, b, sr)
    print(f.name, round(len(a) / sr, 1), round(len(b) / sr, 1))
