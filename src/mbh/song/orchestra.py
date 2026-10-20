"""Code-generated orchestra for title stings (numpy/scipy only): deep drum, bowed strings, low ostinato, bansuri-like
lead, brass swell, and a choir built from a sung vocal. All pitched parts take swara names (mbh.song.melody)."""
from __future__ import annotations

import numpy as np

from mbh.song.melody import parse_swara, swara_hz


def _env(n, sr, a=0.05, r=0.3):
    e = np.ones(n); ka, kr = min(n, int(a * sr)), min(n, int(r * sr))
    if ka: e[:ka] = np.linspace(0, 1, ka)
    if kr: e[-kr:] *= np.linspace(1, 0, kr)
    return e


def lowpass(y, sr, hz, order=2):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, hz, "low", fs=sr, output="sos"), y)


def drum(sr, seconds=2.2, f0=58.0, seed=0):
    """Deep pakhawaj/taiko-like 'dhum': pitch-dropping sine body, sub, skin noise, slap."""
    rng = np.random.default_rng(seed); n = int(seconds * sr); t = np.arange(n) / sr
    f = f0 * (1 + 0.9 * np.exp(-t / 0.04)) * (1 - 0.25 * (1 - np.exp(-t / 0.4)))
    body = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.55)
    sub = np.sin(2 * np.pi * f0 / 2 * t) * np.exp(-t / 0.9) * 0.5
    skin = lowpass(rng.standard_normal(n), sr, 900) * np.exp(-t / 0.05) * 0.6
    slap = lowpass(rng.standard_normal(n), sr, 4000) * np.exp(-t / 0.008) * 0.3
    y = body + sub + skin + slap
    return y / np.abs(y).max()


def string_tone(hz, seconds, sr, voices=5, cents=9, bright=3500, attack=0.35, release=0.6, seed=1):
    """Ensemble of detuned band-limited saws with slow vibrato, low-passed: a bowed section."""
    rng = np.random.default_rng(seed); n = int(seconds * sr); t = np.arange(n) / sr; y = np.zeros(n)
    for v in range(voices):
        det = 2 ** ((rng.uniform(-1, 1) * cents) / 1200)
        vib = 1 + 0.004 * np.sin(2 * np.pi * (4.8 + rng.uniform(-.5, .5)) * t + rng.uniform(0, 6))
        ph = 2 * np.pi * np.cumsum(hz * det * vib) / sr + rng.uniform(0, 6)
        for k in range(1, 18):
            if hz * k > bright * 2: break
            y += np.sin(k * ph) / k
    return lowpass(y, sr, bright) * _env(n, sr, attack, release) / voices


def brass(hz, seconds, sr, attack=0.6):
    n = int(seconds * sr); t = np.arange(n) / sr
    bright = 600 + 2400 * np.clip(t / max(attack, 1e-3), 0, 1)   # opens as it swells
    y = string_tone(hz, seconds, sr, voices=3, cents=5, bright=3000, attack=attack, release=0.4, seed=7)
    return y * (0.6 + 0.4 * np.clip(t / attack, 0, 1))


def bansuri(hz, seconds, sr, seed=2):
    rng = np.random.default_rng(seed); n = int(seconds * sr); t = np.arange(n) / sr
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t - 0.25, 0, 1)
    ph = 2 * np.pi * np.cumsum(hz * vib) / sr
    tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    from scipy.signal import butter, sosfilt
    breath = sosfilt(butter(2, [hz * 0.8, hz * 4], "band", fs=sr, output="sos"), rng.standard_normal(n)) * 0.12
    return (tone + breath) * _env(n, sr, 0.08, 0.25)


def line(instr, swaras, start_beat_s, sa, sr, legato=1.05, **kw):
    """Render a list of 'swara:beats' tokens with an instrument; returns (audio, seconds)."""
    t, parts = 0.0, []
    for tok in swaras:
        sw, beats = tok.split(":")
        dur = float(beats) * start_beat_s
        parts.append((t, swara_hz(sw, sa), dur)); t += dur
    y = np.zeros(int((t + 1.5) * sr))
    for at, hz, dur in parts:
        s = instr(hz, dur * legato + 0.3, sr, **kw); k = int(at * sr); y[k:k + len(s)] += s[: len(y) - k]
    return y, t


def ostinato(sa, seconds, sr, beat_s=0.5, pattern=("S.", "S.", "r.", "S."), g0=0.3, g1=1.0):
    """Low cello pulse (mandra saptak) with a crescendo from g0 to g1."""
    n = int(seconds * sr); y = np.zeros(n + sr); t, i = 0.0, 0
    while t < seconds:
        hz = swara_hz(pattern[i % len(pattern)], sa)
        s = string_tone(hz, beat_s * 0.9, sr, voices=3, bright=1500, attack=0.02, release=0.12, seed=i)
        k = int(t * sr); y[k:k + len(s)] += s * (g0 + (g1 - g0) * t / seconds); t += beat_s; i += 1
    return y[:n]


def choir(vocal, sr, cents=(-11, 0, 9, 16), delays_ms=(0, 17, 31, 44), octave_db=-8.0):
    """A small chorus from one sung vocal: detuned/delayed copies spread L/R, plus a quiet octave below."""
    import librosa
    L = np.zeros(len(vocal) + sr); R = np.zeros_like(L)
    for i, (c, d) in enumerate(zip(cents, delays_ms)):
        v = librosa.effects.pitch_shift(vocal, sr=sr, n_steps=c / 100) if c else vocal
        k = int(d * sr / 1000); pan = (i / (len(cents) - 1)) if len(cents) > 1 else 0.5
        L[k:k + len(v)] += v * np.cos(pan * np.pi / 2); R[k:k + len(v)] += v * np.sin(pan * np.pi / 2)
    low = librosa.effects.pitch_shift(vocal, sr=sr, n_steps=-12) * 10 ** (octave_db / 20)
    L[:len(low)] += low; R[:len(low)] += low
    return np.stack([L, R]) / len(cents)
