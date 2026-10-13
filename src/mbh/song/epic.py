"""Preset F ("epic"): our WORLD-sung vocal (clear diction) over an ACE-Step generated epic band, plus a synthesized
shankh (conch). Steps (each in its own venv, see docs/SONGS.md "Preset F"):
  1. ``mbh song render`` -> F_world.wav + F_world.dry.wav (dry sung vocal) + F_world.json (line timeline)
  2. ``mbh song ace --mode complete --src F_world.vocal.wav --prompt-key epic`` -> band take (ACE re-sings too)
  3. demucs two-stem split of the band take -> keep ``no_vocals`` (the band), drop ACE's vocal
  4. ``mbh song finish`` (this module): deepen the dry vocal, build dynamics, add conch, mix, master."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SR = 48000


def _load(path, sr=SR):
    import librosa
    y, _ = librosa.load(str(path), sr=sr, mono=False)
    return y if y.ndim == 2 else np.stack([y, y])


def shelf(y, sr, low_db=3.0, high_db=-2.0):
    """Warmth: lift lows (<250 Hz), soften highs (>6 kHz)."""
    from scipy.signal import butter, sosfilt
    lo = sosfilt(butter(2, 250, "low", fs=sr, output="sos"), y)
    hi = sosfilt(butter(2, 6000, "high", fs=sr, output="sos"), y)
    return y + lo * (10 ** (low_db / 20) - 1) + hi * (10 ** (high_db / 20) - 1)


def deepen(dry, sr, cfg):
    """Fuller vocal: a detuned, delayed double (L/R), a quiet octave-below shadow, warmth EQ. Returns stereo."""
    import librosa
    d = int(cfg.get("double_ms", 24) * sr / 1000)
    dbl = librosa.effects.pitch_shift(dry, sr=sr, n_steps=cfg.get("double_cents", 9) / 100)
    dbl = np.concatenate([np.zeros(d), dbl])[: len(dry)] * 10 ** (cfg.get("double_db", -8) / 20)
    sub = librosa.effects.pitch_shift(dry, sr=sr, n_steps=-12) * 10 ** (cfg.get("octave_db", -16) / 20)
    core = shelf(dry + sub, sr, cfg.get("low_shelf_db", 3), cfg.get("high_shelf_db", -1.5))
    return np.stack([core + dbl, core + 0.6 * dbl])


def hall(st, sr, wet, seconds=3.2):
    from mbh.song.render import reverb
    return np.stack([reverb(st[0], wet, sr, seconds, seed=3), reverb(st[1], wet, sr, seconds, seed=4)])


def conch(sr, seconds=3.6, f0=233.08, seed=1):
    """Shankh: a breathy brass-like blast with a slight upward scoop, slow swell and natural decay (code-synthesized)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    f = f0 * 2 ** ((-0.6 * np.exp(-t / 0.25) + 0.08 * np.sin(2 * np.pi * 4.6 * t) * np.clip(t - 1, 0, 1)) / 12)
    ph = 2 * np.pi * np.cumsum(f) / sr
    tone = sum(a * np.sin(k * ph) for k, a in [(1, 1), (2, .55), (3, .5), (4, .22), (5, .25), (6, .1), (7, .08)])
    from scipy.signal import butter, sosfilt
    breath = sosfilt(butter(2, [f0 * 1.5, f0 * 8], "band", fs=sr, output="sos"), rng.standard_normal(len(t))) * 0.25
    env = np.clip(t / 0.5, 0, 1) ** 1.5 * np.clip((seconds - t) / 1.4, 0, 1)
    y = (tone + breath * (0.6 + 0.4 * np.sin(ph * 0.5) ** 2)) * env
    return y / (np.abs(y).max() + 1e-9)


def finish(spec, world_json: Path, band_wav: Path, out: Path) -> dict:
    import soundfile as sf
    from mbh.song.master import master_file
    cfg = spec.raw.get("f", {})
    rep = json.loads(Path(world_json).read_text())
    dry = _load(Path(rep["out"]).with_suffix(".dry.wav"))[0]
    band = _load(band_wav)
    n = max(len(dry), band.shape[1]) + int(4 * SR)
    pad = lambda x: np.pad(x, [(0, 0)] * (x.ndim - 1) + [(0, n - x.shape[-1])])
    dry, band = pad(dry), pad(band)
    # dynamic build: per-line vocal/band gains (dB), ramped between line starts
    starts = [l["starts_s"] for l in rep["lines"]]
    vg, bg = cfg.get("vocal_build_db", [0] * len(starts)), cfg.get("band_build_db", [0] * len(starts))
    t = np.arange(n) / SR
    vgain = 10 ** (np.interp(t, starts, vg) / 20); bgain = 10 ** (np.interp(t, [0] + starts, [bg[0] - 2] + bg) / 20)
    voc = deepen(dry / (np.sqrt(np.mean(dry[np.abs(dry) > 1e-4] ** 2)) + 1e-9) * 0.1, SR, cfg) * vgain
    voc = hall(voc, SR, cfg.get("reverb", 0.3))
    band = band / (np.sqrt(np.mean(band ** 2)) + 1e-9) * 0.1 * 10 ** (cfg.get("band_db", -4) / 20) * bgain
    env = np.convolve(np.abs(voc[0]), np.ones(int(0.3 * SR)) / int(0.3 * SR), mode="same")
    band = band * (1 - cfg.get("duck", 0.25) * np.clip(env / (env.max() + 1e-9) * 4, 0, 1))
    mix = voc + band
    c = conch(SR) * 0.1 * 10 ** (cfg.get("conch_db", 2) / 20)
    for at in cfg.get("conch_at_s", [0.3]):
        k = int((at if at >= 0 else n / SR + at) * SR); seg = c[: n - k]
        mix[:, k:k + len(seg)] += hall(np.stack([seg, seg]), SR, 0.35)
    raw = out.with_suffix(".premaster.wav"); out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(raw, (mix / (np.abs(mix).max() + 1e-9) * 0.9).T, SR, subtype="FLOAT")
    m = master_file(raw, out, float(spec.master.get("lufs", -16)), float(spec.master.get("true_peak_db", -2)),
                    0.0, cfg.get("end_s"), 0.3, cfg.get("fade_out_s", 4.0))
    sf.write(out.with_suffix(".vox.wav"), (voc / (np.abs(voc).max() + 1e-9) * 0.9).T, SR, subtype="PCM_16")
    return m
