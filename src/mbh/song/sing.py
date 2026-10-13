"""Turn a spoken take into singing: WORLD analysis, syllable segmentation, re-timing onto the melody's notes and a
new f0 contour (glides + vibrato), then WORLD resynthesis. Needs numpy, pyworld, soundfile (render venv)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FRAME_MS = 5.0


@dataclass
class Segment:
    a: int        # first frame of the syllable
    ns: int       # nucleus (vowel) start
    ne: int       # nucleus end (coda starts)
    b: int        # end (exclusive)


def analyse(y: np.ndarray, sr: int):
    import pyworld as pw

    x = y.astype(np.float64)
    f0, t = pw.harvest(x, sr, f0_floor=60, f0_ceil=500, frame_period=FRAME_MS)
    sp = pw.cheaptrick(x, f0, t, sr)
    ap = pw.d4c(x, f0, t, sr)
    return f0, sp, ap


def frame_db(y: np.ndarray, sr: int, n_frames: int) -> np.ndarray:
    hop = int(sr * FRAME_MS / 1000)
    pad = np.pad(y, (hop, hop))
    rms = np.array([np.sqrt(np.mean(pad[i * hop:i * hop + 2 * hop] ** 2) + 1e-12) for i in range(n_frames)])
    db = 20 * np.log10(rms + 1e-9)
    k = 7  # ~35 ms smoothing
    return np.convolve(db, np.ones(k) / k, mode="same")


def segment_syllables(db: np.ndarray, f0: np.ndarray, n: int, min_gap: int = 12) -> list[Segment]:
    """Split the take into ``n`` syllables at the deepest loudness valleys (vowels are loudness peaks)."""
    floor = db.max() - 45
    active = np.where(db > floor)[0]
    start, end = (int(active[0]), int(active[-1]) + 1) if len(active) else (0, len(db))
    cands = []
    for i in range(start + 2, end - 2):
        if db[i] <= db[i - 1] and db[i] <= db[i + 1]:
            left = db[max(start, i - 40):i].max()
            right = db[i + 1:min(end, i + 41)].max()
            unvoiced = 3.0 if f0[i] <= 0 else 0.0  # consonant / pause between vowels
            cands.append((min(left, right) - db[i] + unvoiced, i))
    cands.sort(reverse=True)
    cuts: list[int] = []
    for _depth, i in cands:
        if len(cuts) == n - 1:
            break
        if all(abs(i - c) >= min_gap for c in cuts):
            cuts.append(i)
    bounds = sorted([start, *cuts, end])
    while len(bounds) - 1 < n:  # not enough valleys: split the longest syllable
        k = max(range(len(bounds) - 1), key=lambda j: bounds[j + 1] - bounds[j])
        bounds.insert(k + 1, (bounds[k] + bounds[k + 1]) // 2)
    segs = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = db[a:b]
        peak = seg.max()
        loud = np.where((seg > peak - 7) & (f0[a:b] > 0))[0]
        if len(loud) == 0:
            loud = np.where(seg > peak - 7)[0]
        ns, ne = a + int(loud[0]), a + int(loud[-1]) + 1
        segs.append(Segment(a, ns, max(ne, ns + 1), b))
    return segs


def f0_contour(notes, sa_hz: float, beat_s: float, n_out: int, offset_s: float, voice: dict, seed: int = 0) -> np.ndarray:
    """Target f0 per output frame (Hz; 0 in rests): log-domain glides between notes, delayed vibrato, slight drift."""
    from mbh.song.melody import swara_hz

    rng = np.random.default_rng(seed)
    octave = float(voice.get("octave", 0))
    glide = float(voice.get("glide_s", 0.09))
    vib_c, vib_hz = float(voice.get("vibrato_cents", 28)), float(voice.get("vibrato_hz", 5.2))
    t = np.arange(n_out) * FRAME_MS / 1000
    logf = np.full(n_out, np.nan)
    since = np.zeros(n_out)
    for note in notes:
        if note.is_rest:
            continue
        s, e = offset_s + note.start_beat * beat_s, offset_s + (note.start_beat + note.beats) * beat_s
        m = (t >= s) & (t < e)
        logf[m] = math.log2(swara_hz(note.swara, sa_hz) * 2 ** octave)
        since[m] = t[m] - s
    # glides: smooth note-to-note steps with a raised-cosine kernel (meend-like); fill rests by holding
    filled = logf.copy()
    idx = np.where(~np.isnan(filled))[0]
    if len(idx):
        filled = np.interp(np.arange(n_out), idx, filled[idx])
    k = max(1, int(glide * 1000 / FRAME_MS))
    win = np.hanning(2 * k + 1); win /= win.sum()
    smooth = np.convolve(np.pad(filled, (k, k), mode="edge"), win, mode="valid")
    depth = np.clip((since - 0.22) / 0.35, 0, 1) * vib_c / 1200
    vib = depth * np.sin(2 * np.pi * vib_hz * t + 0.3 * np.sin(2 * np.pi * 0.37 * t))
    drift = np.convolve(rng.standard_normal(n_out), np.ones(60) / 60, mode="same") * 0.004
    hz = 2 ** (smooth + vib + drift)
    hz[np.isnan(logf)] = 0.0
    return hz


def segments_from_alignment(times, n_frames: int) -> list[Segment]:
    """(start, vowel_start, vowel_end, end) seconds per syllable -> contiguous WORLD-frame segments
    (pauses longer than 0.15 s between syllables are skipped)."""
    fr = FRAME_MS / 1000
    segs = []
    for i, (s, vs, ve, e) in enumerate(times):
        if i > 0:
            pe = times[i - 1][3]
            s = (pe + s) / 2 if s - pe < 0.15 else s - 0.03
        if i + 1 < len(times):
            ns_ = times[i + 1][0]
            e = (e + ns_) / 2 if ns_ - e < 0.15 else e + 0.03
        a = max(0, int(s / fr)); b = min(n_frames, max(a + 2, int(e / fr)))
        coda = max(0.0, times[i][3] - ve)
        ns = min(max(a, int(vs / fr)), b - 1); ne = min(b, max(ns + 1, int((e - coda) / fr)))
        segs.append(Segment(a, ns, ne, b))
    return segs


def sing_line(y: np.ndarray, sr: int, notes, n_syllables: int, sa_hz: float, beat_s: float, voice: dict,
              lead_s: float = 0.6, seed: int = 0, syllables: list[str] | None = None):
    """Return (audio, info). The first sung vowel lands at ``lead_s``; consonant onsets anticipate their note."""
    import pyworld as pw

    f0, sp, ap = analyse(y, sr)
    db = frame_db(y, sr, len(f0))
    method = "energy"
    if syllables:
        try:
            from mbh.song.align import align_syllables
            segs = segments_from_alignment(align_syllables(y, sr, syllables), len(f0)); method = "mms_fa"
        except Exception as exc:  # aligner unavailable: fall back to loudness valleys
            print(f"forced alignment failed ({exc}); using loudness segmentation")
            segs = segment_syllables(db, f0, n_syllables)
    else:
        segs = segment_syllables(db, f0, n_syllables)
    fr = FRAME_MS / 1000
    # syllable spans in beats
    span: dict[int, list[float]] = {}
    for note in notes:
        if note.syllable >= 0:
            s, e = span.get(note.syllable, [note.start_beat, note.start_beat + note.beats])
            span[note.syllable] = [min(s, note.start_beat), max(e, note.start_beat + note.beats)]
    total_beats = max(n.start_beat + n.beats for n in notes)
    n_out = int((lead_s + total_beats * beat_s + 0.8) / fr)
    src = np.full(n_out, -1.0)        # fractional source frame per output frame (-1 = silence)
    for i, seg in enumerate(segs):
        s_out = lead_s + span[i][0] * beat_s
        e_out = lead_s + span[i][1] * beat_s
        on = (seg.ns - seg.a) * fr
        coda = (seg.b - seg.ne) * fr
        nxt_on = (segs[i + 1].ns - segs[i + 1].a) * fr if i + 1 < len(segs) else 0.0
        o0 = max(0, int((s_out - on) / fr)); o1 = int(s_out / fr)
        v1 = int((e_out - nxt_on - coda) / fr); c1 = int((e_out - nxt_on) / fr)
        v1 = max(v1, o1 + 1); c1 = max(c1, v1)
        src[o0:o1] = np.linspace(seg.a, seg.ns, max(1, o1 - o0), endpoint=False)[:o1 - o0]
        # vowel: stretch the nucleus uniformly over the note(s); WORLD interpolates the spectra smoothly
        src[o1:v1] = np.linspace(seg.ns, seg.ne - 1, v1 - o1)
        src[v1:c1] = np.linspace(seg.ne, seg.b, max(1, c1 - v1), endpoint=False)[:c1 - v1]
    out_f0 = f0_contour(notes, sa_hz, beat_s, n_out, lead_s, voice, seed)
    silent = src < 0
    srci = np.clip(src, 0, len(f0) - 1)
    lo = np.floor(srci).astype(int); hi = np.minimum(lo + 1, len(f0) - 1); w = (srci - lo)[:, None]
    sp_o = sp[lo] * (1 - w) + sp[hi] * w
    ap_o = ap[lo] * (1 - w) + ap[hi] * w
    voiced = (f0[np.rint(srci).astype(int)] > 0) & ~silent & (out_f0 > 0)
    f0_o = np.where(voiced, out_f0, 0.0)
    sp_o[silent] = sp.min(axis=0) * 1e-4 + 1e-16
    ap_o[silent] = 1.0
    audio = pw.synthesize(np.ascontiguousarray(f0_o), np.ascontiguousarray(sp_o), np.ascontiguousarray(ap_o), sr, FRAME_MS)
    gain = np.ones(n_out); gain[silent] = 0.0
    gain = np.convolve(gain, np.ones(6) / 6, mode="same")
    g = np.interp(np.arange(len(audio)) / sr, np.arange(n_out) * fr, gain)
    info = {"align": method, "segments": [[s.a, s.ns, s.ne, s.b] for s in segs], "seconds": round(len(audio) / sr, 2),
            "first_vowel_s": lead_s, "beats": total_beats}
    return audio * g, info
