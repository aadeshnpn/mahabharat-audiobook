"""Render a voice audition from real episode lines with the episode renderer (render venv: proto/.venv-vox).
usage: audition.py EPISODE.yaml OUT.mp3 LINE_ID[,LINE_ID] [LINE_ID,...] ...
Each positional group after OUT is one speaker block: lines in a block are 1.2 s apart, blocks 2.5 s apart (silence).
Lines go through render_script (same cache as the episode, so they are reused by the full render), each is
normalized to -16 LUFS like the assembler does, and the result is encoded with tools/encode_mp3.py (-16 LUFS verified).
"""
import subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.audioio import read_mono, resample, write_pcm16
from mbh.episode.build import build_episode
from mbh.episode.loudness import limit_peaks, normalize_line
from mbh.episode.render import VoxCPM2Backend, render_script
from mbh.episode.spec import load_spec
from mbh.episode.timing import load_timing

spec_path, out = Path(sys.argv[1]), Path(sys.argv[2])
blocks = [g.split(",") for g in sys.argv[3:]]
spec = load_spec(spec_path); script = build_episode(spec); _, settings = load_timing(spec.timing_path)
wanted = {i for b in blocks for i in b}
missing = wanted - {l.id for l in script.lines}
if missing: sys.exit(f"unknown line ids: {sorted(missing)}")
res = {r.line_id: r for r in render_script(script, VoxCPM2Backend(), settings, only=wanted)}
rate = 48000; audio = []
for bi, block in enumerate(blocks):
    if bi: audio += [0.0] * int(2.5 * rate)
    for li, lid in enumerate(block):
        r = res[lid]
        if r.status not in ("rendered", "cached"): sys.exit(f"{lid}: {r.status}")
        x, sr = read_mono(Path(r.path)); x = list(resample(x, sr, rate)) if sr != rate else list(x)
        x, info = normalize_line(x, rate, -16.0)
        if li: audio += [0.0] * int(1.2 * rate)
        audio += list(x)
        print(lid, r.status, r.speaker, info, flush=True)
lim = limit_peaks(audio, rate, -1.5); audio = list(lim[0] if isinstance(lim, tuple) else lim)
out.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    wav = Path(td) / "audition.wav"; write_pcm16(wav, audio, rate)
    subprocess.run([sys.executable, str(ROOT / "tools" / "encode_mp3.py"), str(wav), str(out)], check=True)
print("wrote", out)
