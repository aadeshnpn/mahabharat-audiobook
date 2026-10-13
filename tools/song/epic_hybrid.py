import sys, json; sys.path.insert(0, "/workspace/mbh-title/src")
from pathlib import Path
from mbh.song.spec import load_song
from mbh.song.ace import generate
spec = load_song("/workspace/mbh-title/configs/songs/title_song.yaml"); E = spec.raw["epic"]
D = Path("/workspace/mahabharat/build/song/title_song/epic_hyb"); src = Path("/workspace/mahabharat/build/song/title_song/A_world.vocal.wav")
for s in (0, 1, 2):
    o = D / f"hyb_e1_s{s}.wav"
    if not o.exists(): print(json.dumps(generate(spec, o, line_ids=["2.62a"], seed=s, mode="complete", src=src, prompt=E["prompts"]["e1"]))[:150], flush=True)
print("HYB_DONE")
