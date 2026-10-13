"""Mix the title song: chosen chant clips over a code-generated tanpura (Sa-Pa) drone with soft bells, fades,
mastered to -16 LUFS / -2 dBTP via mbh.episode.loudness.  Run with proto/.venv-vox python.
usage: mix.py STYLE SPELLING OUT.wav [--pick h1=s11,h2=s23,...]   (default per half-verse: best ASR score)
       mix.py chant r4 OUT.wav --clips chant_r9_h1_s37,chant_r8t_h2_s11,...  (explicit takes, in order)"""
import argparse, json, sys
from pathlib import Path
import numpy as np, soundfile as sf, librosa
from scipy.signal import fftconvolve, butter, sosfilt
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode import loudness
ap = argparse.ArgumentParser(); ap.add_argument("style"); ap.add_argument("spelling"); ap.add_argument("out"); ap.add_argument("--pick", default="")
ap.add_argument("--order", default="1,2,3,4", help="half-verses in order; a repeat uses the other seed")
ap.add_argument("--clips", default="", help="explicit clip names in order (overrides --order/--pick), e.g. chant_r9_h1_s37,...")
ap.add_argument("--stretch", type=float, default=1.0, help="time-stretch rate (<1 slower, pitch kept); ASR shows stretching blurs consonants, so 1.0 is the default")
ap.add_argument("--wet", type=float, default=0.15, help="temple reverb send"); ap.add_argument("--bed-db", type=float, default=-16.0); ap.add_argument("--gap", type=float, default=3.0); ap.add_argument("--vgap", type=float, default=5.0)
a = ap.parse_args()
CFG = json.loads((ROOT / "configs/title_song.json").read_text())
SR = 48000; rng = np.random.default_rng(62)
scores = json.loads((ROOT / "build/title_song/scores.json").read_text()) if (ROOT / "build/title_song/scores.json").exists() else {}
pick = dict(p.split("=") for p in a.pick.split(",") if p)
def split_verse(y):
    """A whole-verse take (r7): split at the longest pause between 35% and 70% of its length."""
    hop = 480; e = librosa.feature.rms(y=y, frame_length=1920, hop_length=hop)[0]; quiet = e < 0.08 * e.max()
    lo, hi = int(len(e) * 0.35), int(len(e) * 0.7); best, run, start, pos = 0, 0, lo, lo
    for i in range(lo, hi):
        run = run + 1 if quiet[i] else 0
        if run > best: best, pos = run, i - run // 2
    cut = pos * hop
    return librosa.effects.trim(y[:cut], top_db=35)[0], librosa.effects.trim(y[cut:], top_db=35)[0]
clips, chosen = [], []
used: dict[int, int] = {}
def ranked(h):
    names = [f"{a.style}_{a.spelling}_h{h}_s{s}.wav" for s in CFG["seeds"]]
    names = [n for n in names if (ROOT / "build/title_song/clips" / n).exists()]
    if f"h{h}" in pick: names.insert(0, (pick[f"h{h}"] if pick[f"h{h}"].startswith(("chant", "melodic")) else f"{a.style}_{a.spelling}_h{h}_{pick[f'h{h}']}") + ".wav")
    else: names.sort(key=lambda n: -scores.get(n, {}).get("score", 0))
    return names
import re as _re
plan = [(int(_re.search(r"_h(\d)_", c).group(1)), c if c.endswith(".wav") else c + ".wav") for c in a.clips.split(",")] if a.clips else None
if plan is None:
    plan = []
    for h in [int(x) for x in a.order.split(",")]:
        names = ranked(h); plan.append((h, names[used.get(h, 0) % len(names)])); used[h] = used.get(h, 0) + 1
for h, name in plan:
    y, sr = librosa.load(ROOT / "build/title_song/clips" / name, sr=SR, mono=True)
    y, _ = librosa.effects.trim(y, top_db=35)
    if "_r7_" in name or "_r8_" in name: y = split_verse(y)[1 if h in (2, 4) else 0]
    if a.stretch != 1.0: y = librosa.effects.time_stretch(y, rate=a.stretch)
    clips.append(y / (np.sqrt(np.mean(y ** 2)) + 1e-9) * 0.1); chosen.append(name)
# Sa from the chanter's median pitch, folded into the C3..B3 octave
f0 = librosa.yin(librosa.resample(np.concatenate(clips), orig_sr=SR, target_sr=16000), fmin=60, fmax=300, sr=16000, frame_length=1024)
med = float(np.nanmedian(f0)) if np.any(~np.isnan(f0)) else 130.8
sa = med
while sa > 160: sa /= 2
while sa < 110: sa *= 2
# timeline
lead, gap, vgap, tail = 9.0, a.gap, a.vgap, 11.0
starts, t = [], lead
for i, c in enumerate(clips):
    starts.append(t); t += len(c) / SR + (vgap if i % 2 == 1 else gap)
total = t - gap + tail; n = int(total * SR)
voice = np.zeros(n)
for s, c in zip(starts, clips): voice[int(s * SR):int(s * SR) + len(c)] += c
# temple reverb: exponentially decaying filtered noise IR
ir_t = np.arange(int(1.6 * SR)) / SR
ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t * 4.0); ir = sosfilt(butter(2, 5000, fs=SR, output="sos"), ir); ir /= np.sqrt(np.sum(ir ** 2))
voice = voice + a.wet * fftconvolve(voice, ir)[:n]
# tanpura: plucks Pa, Sa', Sa', Sa (low) every 1.2 s with jawari-like rich harmonics; plus a soft sustained pad
tt = np.arange(n) / SR
def pluck(freq, dur=5.0):
    m = int(dur * SR); x = np.arange(m) / SR; y = np.zeros(m)
    for k in range(1, 24):
        f = freq * k * (1 + 0.0004 * rng.standard_normal())
        if f > 9000: break
        env = np.exp(-x * (0.6 + 0.12 * k)) * (1 - np.exp(-x * 40)) * (1 + 0.3 * np.sin(2 * np.pi * 0.3 * x * k))
        y += env * np.sin(2 * np.pi * f * x + rng.uniform(0, 6.28)) / k ** 0.9
    return y
drone = np.zeros(n + 6 * SR)
cycle = [sa * 1.5 / 2, sa, sa, sa / 2]  # Pa (mandra), Sa, Sa, Sa (low)
i, t = 0, 0.0
while t < total:
    p = pluck(cycle[i % 4]); k = int(t * SR); drone[k:k + len(p)] += p * (0.9 if i % 4 else 1.0); t += 1.25; i += 1
drone = drone[:n]
pad = sum(np.sin(2 * np.pi * f * tt) * w for f, w in [(sa / 2, 0.5), (sa, 0.35), (sa * 1.5, 0.2), (sa * 2, 0.1)])
pad *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.07 * tt)
bed = drone / (np.sqrt(np.mean(drone ** 2)) + 1e-9) * 0.1 + pad / (np.sqrt(np.mean(pad ** 2))) * 0.03
# soft bells: at the start, before each later pair of half-verses, and at the close
def bell(f0, dur=6.0):
    m = int(dur * SR); x = np.arange(m) / SR
    return sum(np.exp(-x * d) * np.sin(2 * np.pi * f0 * r * x) * w for r, d, w in [(1, 0.8, 1), (2.76, 1.6, 0.5), (5.4, 3, 0.25), (8.9, 5, 0.1)]) * (1 - np.exp(-x * 200))
for bt in [2.0] + [starts[j] - vgap * 0.6 for j in range(2, len(starts), 2)] + [total - tail + 1.5]:
    b = bell(sa * 4); k = int(bt * SR); seg = b[:max(0, min(len(b), n - k))]; bed[k:k + len(seg)] += 0.08 * seg
# duck the bed a little under the voice (slow envelope)
env = np.convolve(np.abs(voice), np.ones(int(0.4 * SR)) / int(0.4 * SR), mode="same")
duck = 1.0 - 0.35 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
bed_level = 10 ** (a.bed_db / 20)  # bed level relative to the chant
mix = voice + bed * duck * bed_level * (np.sqrt(np.mean(voice[voice != 0] ** 2)) / (np.sqrt(np.mean(bed ** 2)) + 1e-9))
fade_in, fade_out = 5.0, 7.0
mix[:int(fade_in * SR)] *= np.linspace(0, 1, int(fade_in * SR)) ** 2
mix[-int(fade_out * SR):] *= np.linspace(1, 0, int(fade_out * SR)) ** 2
mastered, info = loudness.master(mix, SR, -16.0, -2.0)
sf.write(a.out, np.asarray(mastered), SR, subtype="PCM_16")
print(json.dumps({"out": a.out, "starts": [round(x, 2) for x in starts], "ends": [round(x + len(c) / SR, 2) for x, c in zip(starts, clips)], "seconds": round(n / SR, 1), "sa_hz": round(sa, 1), "chant_f0_median": round(med, 1), "clips": chosen, "master": info}))
