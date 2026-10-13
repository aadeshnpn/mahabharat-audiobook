"""Code-generated arrangement: tanpura, harmonium (drone + heterophonic melody), string pad with swells,
synthesised tabla (keherwa / dadra), bells. Everything is additive synthesis with numpy; no samples."""
from __future__ import annotations

import math

import numpy as np

from mbh.song.melody import swara_hz

PRESETS = {
    "devotional_title": {
        "tanpura": 0.55, "harmonium": 0.38, "harmonium_melody": 0.22, "strings": 0.42, "tabla": 0.36,
        "bells": 0.18, "swell": 0.30, "vocal_reverb": 0.22, "bed_db": -9.0,
    },
    "meditative": {
        "tanpura": 0.7, "harmonium": 0.25, "harmonium_melody": 0.0, "strings": 0.3, "tabla": 0.0,
        "bells": 0.25, "swell": 0.15, "vocal_reverb": 0.28, "bed_db": -12.0,
    },
}

TAALS = {  # bols per matra; "dha"=bass+treble, "ge"=bass, "na"/"ta"/"tin"=treble, "ka"/"ti"=closed, "-"=rest
    "keherwa": ["dha", "ge", "na", "ti", "na", "ka", "dhi", "na"],
    "dadra": ["dha", "dhi", "na", "dha", "tin", "na"],
}


def _rng(seed=0):
    return np.random.default_rng(seed)


def tanpura(sa: float, seconds: float, sr: int, seed: int = 1) -> np.ndarray:
    rng = _rng(seed)
    n = int(seconds * sr)
    out = np.zeros(n + 6 * sr)
    cycle = [sa * 0.75, sa, sa, sa / 2]

    def pluck(freq, dur=5.0):
        m = int(dur * sr); x = np.arange(m) / sr; y = np.zeros(m)
        for k in range(1, 24):
            f = freq * k * (1 + 0.0004 * rng.standard_normal())
            if f > 9000:
                break
            env = np.exp(-x * (0.6 + 0.12 * k)) * (1 - np.exp(-x * 40)) * (1 + 0.3 * np.sin(2 * np.pi * 0.3 * x * k))
            y += env * np.sin(2 * np.pi * f * x + rng.uniform(0, 6.28)) / k ** 0.9
        return y

    t, i = 0.0, 0
    while t < seconds:
        p = pluck(cycle[i % 4]); k = int(t * sr); out[k:k + len(p)] += p; t += 1.25; i += 1
    return _norm(out[:n])


def reed(freq: float, seconds: float, sr: int, attack=0.06, release=0.25) -> np.ndarray:
    """Harmonium-like reed: two slightly detuned reeds, odd-rich spectrum, gentle bellows tremor."""
    n = max(1, int(seconds * sr)); x = np.arange(n) / sr
    y = np.zeros(n)
    for det in (0.0, 1.6):
        for k in range(1, 14):
            amp = (1.0 / k) * (1.25 if k % 2 else 0.8)
            y += amp * np.sin(2 * np.pi * (freq + det) * k * x)
    env = np.minimum(1, x / attack) * np.minimum(1, (seconds - x) / release).clip(0, 1)
    return y * env * (1 + 0.04 * np.sin(2 * np.pi * 4.5 * x))


def strings(freqs: list[float], seconds: float, sr: int, attack=1.5, release=1.5, seed=2) -> np.ndarray:
    """Ensemble pad: detuned band-limited saws, slow attack, soft low-pass (simple one-pole)."""
    rng = _rng(seed)
    n = int(seconds * sr); x = np.arange(n) / sr; y = np.zeros(n)
    for f in freqs:
        for v in range(5):
            fv = f * (1 + 0.004 * rng.standard_normal()); ph = rng.uniform(0, 6.28)
            for k in range(1, 16):
                if fv * k > 7000:
                    break
                y += np.sin(2 * np.pi * fv * k * x + ph * k) / k * (1 + 0.15 * np.sin(2 * np.pi * (4.8 + v * 0.3) * x))
    env = np.minimum(1, x / attack) * np.clip((seconds - x) / release, 0, 1)
    y *= env
    from scipy.signal import lfilter

    a = math.exp(-2 * math.pi * 2500 / sr)  # one-pole low-pass
    return lfilter([1 - a], [1, -a], y)


def tabla_stroke(bol: str, sa: float, sr: int, rng) -> np.ndarray:
    n = int(0.9 * sr); x = np.arange(n) / sr; y = np.zeros(n)
    bass = bol in {"dha", "ge", "dhi"}
    treble = bol in {"dha", "na", "ta", "tin", "dhi", "ti"}
    closed = bol in {"ka", "ti"}
    if bass:  # bayan: low membrane with upward pitch glide (gamak)
        f = 75 * (1 + 0.35 * (1 - np.exp(-x * 9)))
        y += 1.0 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-x * 5.5)
    if treble:  # dayan tuned to Sa: harmonic modes, ringing
        base = sa * 2
        for k, amp, d in [(1, 1.0, 9), (2, 0.5, 12), (3, 0.35, 14), (4, 0.2, 18)]:
            y += amp * np.sin(2 * np.pi * base * k * x) * np.exp(-x * d * (2.2 if bol == "tin" else 1.0))
        y += 0.3 * rng.standard_normal(n) * np.exp(-x * 120)
    if closed:
        y += 0.6 * rng.standard_normal(n) * np.exp(-x * 60)
    return y * (1 - np.exp(-x * 800))


def tabla(taal: str, sa: float, beat_s: float, start_s: float, end_s: float, seconds: float, sr: int,
          seed=3, fade_beats: float = 4) -> np.ndarray:
    rng = _rng(seed)
    bols = TAALS[taal]
    out = np.zeros(int(seconds * sr) + sr)
    t, i = start_s, 0
    while t < end_s:
        bol = bols[i % len(bols)]
        if bol != "-":
            s = tabla_stroke(bol, sa, sr, rng) * (1.0 if i % len(bols) == 0 else 0.75) * (0.9 + 0.2 * rng.random())
            ramp = min(1.0, (t - start_s) / (fade_beats * beat_s) + 0.25)
            k = int((t + 0.008 * rng.standard_normal()) * sr); k = max(0, k)
            out[k:k + len(s)] += s[:len(out) - k] * ramp
        t += beat_s; i += 1
    return out[:int(seconds * sr)]


def bell(f0: float, sr: int, dur=6.0) -> np.ndarray:
    m = int(dur * sr); x = np.arange(m) / sr
    return sum(np.exp(-x * d) * np.sin(2 * np.pi * f0 * r * x) * w
               for r, d, w in [(1, 0.8, 1), (2.76, 1.6, 0.5), (5.4, 3, 0.25), (8.9, 5, 0.1)]) * (1 - np.exp(-x * 200))


def swell(seconds: float, sr: int, seed=4) -> np.ndarray:
    """Rising filtered-noise + cymbal-like shimmer that peaks at the end."""
    from scipy.signal import butter, sosfilt
    rng = _rng(seed)
    n = int(seconds * sr); x = np.arange(n) / sr
    noise = sosfilt(butter(2, [2000, 9000], btype="band", fs=sr, output="sos"), rng.standard_normal(n))
    return noise * (x / seconds) ** 3


def _norm(y: np.ndarray) -> np.ndarray:
    r = np.sqrt(np.mean(y ** 2)) + 1e-12
    return y / r * 0.1


def place(buf: np.ndarray, y: np.ndarray, t: float, sr: int, gain: float = 1.0) -> None:
    k = max(0, int(t * sr))
    if k >= len(buf):
        return
    seg = y[:len(buf) - k]
    buf[k:k + len(seg)] += gain * seg


def arrangement(spec, timeline: list[tuple], seconds: float, sr: int, intro_s: float) -> dict[str, np.ndarray]:
    """``timeline``: [(SongLine, first_vowel_s)] already placed. Returns named stems (unnormalised mix gains applied)."""
    cfg = {**PRESETS[spec.arrangement.get("preset", "devotional_title")], **spec.arrangement.get("mix", {})}
    sa, beat = spec.sa_hz, spec.beat_s
    n = int(seconds * sr)
    stems: dict[str, np.ndarray] = {}
    stems["tanpura"] = tanpura(sa, seconds, sr) * cfg["tanpura"]
    # harmonium: Sa+Pa drone through the song (left hand) and the melody doubled softly (right hand, heterophony)
    h = np.zeros(n)
    drone = (reed(sa, seconds, sr, attack=2.0, release=3.0) + 0.7 * reed(sa * 1.5, seconds, sr, attack=2.0, release=3.0))
    h += _norm(drone) * cfg["harmonium"]
    mel = np.zeros(n)
    for line, t0 in timeline:
        for note in line.notes:
            if note.is_rest:
                continue
            f = swara_hz(note.swara, sa) * 2
            place(mel, reed(f, note.beats * beat * 0.98, sr, attack=0.04, release=0.12), t0 + note.start_beat * beat - 0.02, sr)
    if cfg["harmonium_melody"]:
        h = h + (_norm(mel) * cfg["harmonium_melody"] if mel.any() else 0)
    stems["harmonium"] = h
    # strings: intro hook = first line's opening phrase played by the strings; then a sustained pad with swells
    st = np.zeros(n)
    if timeline:
        first = timeline[0][0]
        t = intro_s * 0.25
        for note in first.notes[:9]:
            if note.is_rest:
                break
            f = swara_hz(note.swara, sa) * 2
            place(st, strings([f, f * 2], note.beats * beat * 1.05 + 0.4, sr, attack=0.25, release=0.5), t + note.start_beat * beat, sr, 0.8)
    pad_chords = [[sa, sa * 1.5, sa * 2], [sa * 5 / 4, sa * 1.5, sa * 15 / 8], [sa * 9 / 8, sa * 45 / 32, sa * 5 / 3]]
    for j, (line, t0) in enumerate(timeline):
        dur = max(n.start_beat + n.beats for n in line.notes) * beat
        for c, frac in enumerate((0.0, 0.5)):
            chord = pad_chords[(j * 2 + c) % len(pad_chords)]
            place(st, strings(chord, dur * 0.5 + 1.5, sr, attack=1.2, release=1.4), t0 + dur * frac - 0.3, sr, 0.6)
    stems["strings"] = _norm(st) * cfg["strings"] if st.any() else st
    # tabla: enters halfway through the intro, stops a bar before the end
    if cfg["tabla"] and spec.arrangement.get("tabla"):
        end_s = seconds - spec.arrangement.get("outro_beats", 6) * beat * 0.6
        stems["tabla"] = _norm(tabla(spec.arrangement["tabla"], sa, beat, intro_s * 0.5, end_s, seconds, sr)) * cfg["tabla"]
    # bells at the start and at the end; a swell leading into the first sung line
    b = np.zeros(n)
    place(b, bell(sa * 4, sr), 0.5, sr); place(b, bell(sa * 4, sr), seconds - 6.5, sr, 0.8)
    stems["bells"] = _norm(b) * cfg["bells"]
    sw = np.zeros(n)
    if timeline:
        place(sw, swell(3.0, sr), timeline[0][1] - 3.0, sr)
    stems["swell"] = _norm(sw) * cfg["swell"] if sw.any() else sw
    return stems
