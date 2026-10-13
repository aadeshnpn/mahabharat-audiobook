"""Epic title-song sweep: ACE-Step text2music over prompts x lyric formats x seeds for line(s) of a song config.
usage (proto/.venv-ace): PYTHONPATH=src python tools/song/epic_sweep.py configs/songs/title_song.yaml OUTDIR [seeds=0-5]
Prompts, bpm, key, duration, lines and formats come from the config's ``epic`` section. Resumable."""
import json, sys
from pathlib import Path
from mbh.song.spec import load_song
from mbh.song.ace import generate, lyrics_format
spec = load_song(sys.argv[1]); out = Path(sys.argv[2]); a, b = (sys.argv[3] if len(sys.argv) > 3 else "0-5").split("-")
E = spec.raw["epic"]
for seed in range(int(a), int(b) + 1):
    for pk, prompt in E["prompts"].items():
        for fmt in E["formats"]:
            o = out / f"{pk}_{fmt}_s{seed}.wav"
            if o.exists(): continue
            info = generate(spec, o, seed=seed, prompt=prompt, lyrics=lyrics_format(spec, E["lines"], fmt),
                            bpm=E["bpm"], keyscale=E.get("keyscale"), duration=E["duration"], steps=E.get("steps"))
            print(json.dumps({k: info[k] for k in ("out", "seed", "gen_s")}), flush=True)
print("SWEEP_DONE", flush=True)
