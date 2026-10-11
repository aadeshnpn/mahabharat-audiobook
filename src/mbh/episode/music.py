"""Line-driven music beds and stings, synthesised on CPU and mixed under dialogue.

Cue choice is data (configs/music.yaml): per-line override > first matching scene rule >
emotion table > default. Synthesis is procedural (tanpura, drones, pads, temple bell, santoor-like
plucks, air and birds) around one tonic, so it is deterministic, open and needs no model.
Resolution is pure Python; synthesis and mixing need numpy and scipy (``pip install .[music]``).

Dialogue always wins: every bed ducks under spoken lines (with look-ahead), the music bus has a
wide speech-band dip, birds and stings are only placed in pauses, and levels sit 14+ dB under speech
before ducking.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mbh.episode.paths import repo_root


# ---------------------------------------------------------------- cue resolution (pure Python)

def load_music_config(path: Path | None = None, preset: str | None = None) -> dict:
    """Load the cue config and apply a level preset (``preset`` argument, else the file's ``preset:``)."""
    cfg = yaml.safe_load((path or repo_root() / "configs" / "music.yaml").read_text(encoding="utf-8"))
    name = preset or cfg.get("preset")
    if name:
        presets = cfg.get("presets") or {}
        if name not in presets:
            raise ValueError(f"unknown music preset {name!r}; have {sorted(presets)}")
        cfg.update(presets[name])
        cfg["preset"] = name
    for name, rule in enumerate(cfg.get("rules", [])):
        if rule.get("cue") not in cfg["cues"]:
            raise ValueError(f"rule {rule.get('name', name)} uses unknown cue {rule.get('cue')!r}")
    for emo, row in cfg.get("emotions", {}).items():
        if row["cue"] not in cfg["cues"]:
            raise ValueError(f"emotion {emo} uses unknown cue {row['cue']!r}")
    return cfg


@dataclass
class LineCue:
    line_id: str
    cue: str
    intensity: float
    source: str           # override | rule:<name> | emotion:<e> | default | inherit:<line>
    kind: str = "bed"     # bed | sting
    build_to_end: bool = False
    bed: str = ""         # the bed under this line (a sting's line keeps its neighbour's bed)
    bed_intensity: float = 0.0


def _as_list(v):
    return v if isinstance(v, list) else [v]


def _matches(match: dict, line, ctx: dict) -> bool:
    for key, want in match.items():
        if key == "text":
            if not re.search(want, line.text):
                return False
        elif key in ("speaker", "segment", "emotion", "fx", "paragraph"):
            have = {"segment": line.segment_id}.get(key, getattr(line, key, None))
            if have not in _as_list(want):
                return False
        elif key == "last_paragraph":
            if (line.segment_id, line.paragraph) != ctx["last_paragraph"] or not want:
                return False
        elif key == "next_emotion":
            if ctx["next"] is None or ctx["next"].emotion not in _as_list(want):
                return False
        elif key == "prev_emotion":
            if ctx["prev"] is None or ctx["prev"].emotion not in _as_list(want):
                return False
        else:
            raise ValueError(f"unknown music rule condition {key!r}")
    return True


def _override(line) -> dict | None:
    m = getattr(line, "music", None)
    if m is None:
        return None
    if isinstance(m, str):
        return {"cue": m}
    return dict(m)


def resolve_cues(lines: list, cfg: dict) -> list[LineCue]:
    """One LineCue per line. Pure function of the script tags and the config."""
    cues = cfg["cues"]
    last = (lines[-1].segment_id, lines[-1].paragraph) if lines else None
    out: list[LineCue] = []
    for i, line in enumerate(lines):
        ctx = {"prev": lines[i - 1] if i else None, "next": lines[i + 1] if i + 1 < len(lines) else None, "last_paragraph": last}
        ov = _override(line)
        if ov:
            if ov["cue"] not in cues:
                raise ValueError(f"{line.id}: unknown music cue {ov['cue']!r}")
            lc = LineCue(line.id, ov["cue"], float(ov.get("intensity", 0.6)), "override", build_to_end=bool(ov.get("build_to_end")))
        else:
            for rule in cfg.get("rules", []):
                if _matches(rule.get("match", {}), line, ctx):
                    lc = LineCue(line.id, rule["cue"], float(rule.get("intensity", 0.6)), f"rule:{rule.get('name', '?')}",
                                 build_to_end=bool(rule.get("build_to_end")))
                    break
            else:
                row = cfg.get("emotions", {}).get(line.emotion)
                lc = (LineCue(line.id, row["cue"], float(row.get("intensity", 0.5)), f"emotion:{line.emotion}") if row else
                      LineCue(line.id, cfg.get("default_cue", "narration_warm"), 0.3, "default"))
        lc.kind = cues[lc.cue].get("kind", "bed")
        out.append(lc)
    # speech tags ("Sauti said,", "The Rishi replied,") inherit the next line's bed: they introduce the
    # next speaker, so the music should already be in that speaker's situation. Overrides still win.
    max_words = int(cfg.get("tag_max_words", 3))
    tag_re = re.compile(cfg.get("tag_pattern", r"\b(said|replied|continued|spoke|asked|answered|rejoined)\W*$"), re.I)
    for i in range(len(out) - 2, -1, -1):
        line, lc = lines[i], out[i]
        is_tag = line.type == "narration" and len(re.findall(r"[\w']+", line.text)) <= max_words and tag_re.search(line.text)
        if is_tag and lc.source != "override" and out[i + 1].kind == "bed":
            nxt = out[i + 1]
            out[i] = LineCue(line.id, nxt.cue, nxt.intensity, f"inherit:{lines[i + 1].id}", "bed", nxt.build_to_end)
    # beds: a sting's line keeps the previous bed underneath
    bed, inten = cfg.get("default_cue", "narration_warm"), 0.3
    for lc in out:
        if lc.kind == "bed":
            bed, inten = lc.cue, lc.intensity
        lc.bed, lc.bed_intensity = bed, inten
    return out


@dataclass
class Region:
    cue: str
    start_s: float
    end_s: float
    intensity: float
    build_to_end: bool = False
    lines: list[str] = field(default_factory=list)


def plan(cues: list[LineCue], intervals: list[tuple[str, float, float]], total_s: float, cfg: dict) -> tuple[list[Region], list[dict]]:
    """Merge per-line beds into regions (boundaries in the pause before a change) and place stings
    in the pause after their line. ``intervals`` are (line_id, start_s, end_s) in the assembled audio."""
    at = {lid: (a, b) for lid, a, b in intervals}
    seq = [(c, at[c.line_id]) for c in cues if c.line_id in at]
    regions: list[Region] = []
    stings: list[dict] = []
    for idx, (c, (a, b)) in enumerate(seq):
        if c.kind == "sting":
            nxt = seq[idx + 1][1][0] if idx + 1 < len(seq) else total_s
            stings.append({"cue": c.cue, "at_s": b + 0.05, "gap_s": max(0.0, nxt - b), "intensity": c.intensity, "line_id": c.line_id})
        if regions and regions[-1].cue == c.bed:
            regions[-1].lines.append(c.line_id)
            regions[-1].intensity = max(regions[-1].intensity, c.bed_intensity)
            regions[-1].build_to_end |= c.build_to_end
            continue
        prev_end = seq[idx - 1][1][1] if idx else 0.0
        boundary = 0.0 if not regions else (prev_end + a) / 2
        if regions:
            regions[-1].end_s = boundary
        regions.append(Region(c.bed, boundary, total_s, c.bed_intensity, c.build_to_end, [c.line_id]))
    # absorb too-short regions into the longer neighbour (keeps the bed from flickering)
    min_s = float(cfg.get("min_region_s", 4.0))
    changed = True
    while changed and len(regions) > 1:
        changed = False
        for i, r in enumerate(regions):
            if r.end_s - r.start_s < min_s and r.cue not in ("celestial_swell", "sacred_invocation", "tender_resolve"):
                j = i - 1 if i and (i + 1 == len(regions) or regions[i - 1].end_s - regions[i - 1].start_s >= regions[i + 1].end_s - regions[i + 1].start_s) else i + 1
                lo, hi = sorted((i, j))
                keep = regions[j]
                keep.start_s, keep.end_s = regions[lo].start_s, regions[hi].end_s
                keep.lines = regions[lo].lines + regions[hi].lines
                del regions[i]
                changed = True
                break
    for i in range(len(regions) - 1, 0, -1):  # neighbours that became the same cue merge
        if regions[i].cue == regions[i - 1].cue:
            regions[i - 1].end_s = regions[i].end_s
            regions[i - 1].lines += regions[i].lines
            regions[i - 1].build_to_end |= regions[i].build_to_end
            del regions[i]
    return regions, stings


def cue_sheet(lines: list, cues: list[LineCue]) -> list[dict]:
    return [{"line_id": l.id, "speaker": l.speaker, "emotion": l.emotion, "cue": c.cue, "kind": c.kind, "bed": c.bed,
             "intensity": c.intensity, "source": c.source, "text": l.text[:70]} for l, c in zip(lines, cues)]


# ---------------------------------------------------------------- synthesis (numpy)

def _np():
    import numpy as np
    return np


def _rng(*key):
    np = _np()
    return np.random.default_rng(int(hashlib.sha256("|".join(map(str, key)).encode()).hexdigest()[:8], 16))


def _pluck(f0, rate, length_s, bright=1.0, n=18, decay=3.2):
    """Tanpura-like pluck: rich harmonics, slow decay, shimmering 'jawari' modulation per harmonic."""
    np = _np()
    t = np.arange(int(length_s * rate)) / rate
    y = np.zeros_like(t)
    for k in range(1, n + 1):
        if f0 * k > 6000:
            break
        amp = (1.0 / k ** (1.25 - 0.35 * bright)) * (1 + 0.6 * math.sin(k))
        env = np.exp(-t / (decay * (0.6 + 0.4 / math.sqrt(k)))) * (1 + 0.45 * np.sin(2 * np.pi * (0.35 + 0.05 * k) * t + k))
        y += amp * env * np.sin(2 * np.pi * f0 * k * (1 + 0.0004 * (k % 3 - 1)) * t + k * 0.7)
    attack = np.minimum(1, t / 0.012)
    return y * attack


def _tanpura(n, rate, sa, bright=0.6, period=0.85):
    np = _np()
    out = np.zeros(n)
    notes = [sa * 0.75, sa, sa, sa / 2]     # Pa (below), Sa, Sa, low Sa
    cache = {}
    pos, i = 0, 0
    while pos < n:
        f = notes[i % 4]
        if f not in cache:
            cache[f] = _pluck(f, rate, 4.0, bright)
        p = cache[f][: n - pos]
        out[pos:pos + len(p)] += p * (0.8 if i % 4 == 3 else 1.0)
        pos += int(period * rate * (1 + 0.03 * math.sin(i)))
        i += 1
    return out


def _drone(n, rate, freqs, harmonics=12, lfo_hz=0.07, rolloff=1.0):
    np = _np()
    t = np.arange(n) / rate
    y = np.zeros(n)
    for j, f in enumerate(freqs):
        for k in range(1, harmonics + 1):
            y += (1.0 / k ** (1 + rolloff)) * np.sin(2 * np.pi * f * k * t + j + k)
    return y * (0.75 + 0.25 * np.sin(2 * np.pi * lfo_hz * t))


def _pad(n, rate, freqs, detune_cents=4.0, shimmer=0.0):
    np = _np()
    t = np.arange(n) / rate
    y = np.zeros(n)
    for j, f in enumerate(freqs):
        for d in (-detune_cents, 0.0, detune_cents):
            ff = f * 2 ** (d / 1200)
            y += np.sin(2 * np.pi * ff * t + j * 1.3 + d) * (1 + shimmer * np.sin(2 * np.pi * (4.5 + j) * t)) / (1 + 0.3 * j)
    return y


def _bell(rate, f0, length_s=7.0):
    np = _np()
    t = np.arange(int(length_s * rate)) / rate
    y = np.zeros_like(t)
    for ratio, amp, tau in ((0.5, 0.6, 5.0), (1.0, 1.0, 3.5), (1.19, 0.5, 2.5), (1.56, 0.4, 2.0), (2.0, 0.45, 1.6), (2.66, 0.25, 1.1), (3.01, 0.2, 0.9)):
        y += amp * np.exp(-t / tau) * np.sin(2 * np.pi * f0 * ratio * t * (1 + 0.0007 * np.sin(2 * np.pi * 1.3 * t)))
    return y * np.minimum(1, t / 0.004)


def _santoor_run(rate, sa, intensity):
    np = _np()
    notes = [1, 9 / 8, 5 / 4, 3 / 2, 5 / 3, 2]
    step = 0.11
    y = np.zeros(int((step * len(notes) + 1.6) * rate))
    t = np.arange(int(1.6 * rate)) / rate
    for i, r in enumerate(notes):
        f = sa * 2 * r
        p = sum(a * np.exp(-t / tau) * np.sin(2 * np.pi * f * m * t) for m, a, tau in ((1, 1.0, 0.7), (2.0, 0.35, 0.4), (3.01, 0.15, 0.25)))
        p *= np.minimum(1, t / 0.003) * (1.0 if i < len(notes) - 1 else 1.3)
        s = int(i * step * rate)
        y[s:s + len(p)] += p
    return y


def _noise_band(n, rate, lo, hi, rng):
    np = _np()
    from scipy.signal import butter, sosfilt
    sos = butter(2, [lo, hi], btype="band", fs=rate, output="sos")
    return sosfilt(sos, rng.standard_normal(n))


def _birds(n, rate, gaps, rng, density=0.5):
    """Short chirp groups placed only inside pauses (never under speech)."""
    np = _np()
    y = np.zeros(n)
    for a, b in gaps:
        if b - a < 0.7 or rng.random() > density:
            continue
        s = a + 0.15 + rng.random() * max(0.0, b - a - 0.6)
        for c in range(int(rng.integers(2, 4))):
            dur = 0.07 + 0.06 * rng.random()
            t = np.arange(int(dur * rate)) / rate
            f = 2600 + 900 * rng.random()
            chirp = np.sin(2 * np.pi * (f * t + 1800 * t * t / dur)) * np.sin(np.pi * t / dur) ** 2
            i = int((s + c * 0.13) * rate)
            if i + len(chirp) < n and (s + c * 0.13 + dur) < b - 0.1:
                y[i:i + len(chirp)] += chirp
    return y


def synth_cue(cue: str, recipe: str, n: int, rate: int, sa: float, gaps: list[tuple[float, float]], spec: dict, key) -> "np.ndarray":
    np = _np()
    rng = _rng(cue, key)
    bright = float(spec.get("brightness", 0.6))
    t = np.arange(n) / rate
    if recipe == "silence":
        return np.zeros(n)
    if recipe == "tanpura":
        return _tanpura(n, rate, sa, bright)
    if recipe == "grave_drone":
        return _drone(n, rate, [sa / 2, sa * 0.75 / 2], harmonics=10, rolloff=1.2 - 0.4 * bright) + 0.35 * _tanpura(n, rate, sa / 2, 0.3, 1.1)
    if recipe == "celestial_swell":
        pad = _pad(n, rate, [sa * 2, sa * 3, sa * 4, sa * 6], shimmer=0.15)
        swell = np.sin(np.minimum(1, t / min(6.0, max(1.0, n / rate * 0.6))) * np.pi / 2) ** 2
        y = pad * swell
        b = _bell(rate, sa * 4)[:n]
        y[: len(b)] += 0.5 * b
        return y
    if recipe == "tender_pad":
        half = int(n * 0.6)
        y = _pad(n, rate, [sa * 2, sa * 2 * 5 / 4], detune_cents=3)
        z = _pad(n, rate, [sa * 2, sa * 3], detune_cents=3)
        x = np.clip((np.arange(n) - half) / max(1, int(1.5 * rate)), 0, 1)
        return (y * (1 - x) + z * x) * np.minimum(1, t / 1.5)
    if recipe == "sacred":
        y = 0.8 * _tanpura(n, rate, sa, 0.7)
        b = _bell(rate, sa * 4, 8.0)[:n]
        y[: len(b)] += 2.2 * b
        return y
    if recipe == "forest":
        air = _noise_band(n, rate, 180, 700, rng) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.05 * t + rng.random() * 6))
        return _tanpura(n, rate, sa, 0.5) + 0.5 * air + 0.25 * _birds(n, rate, gaps, rng)
    if recipe == "anticipation":
        return _tanpura(n, rate, sa, 0.6) + 0.6 * _pad(n, rate, [sa / 2, sa], detune_cents=2) + 0.25 * _pad(n, rate, [sa * 3], shimmer=0.1)
    if recipe == "bright_lift":
        return _santoor_run(rate, sa, 1.0)
    raise ValueError(f"unknown music recipe {recipe!r}")


def _norm_to(y, rate, lufs):
    from mbh.episode import loudness
    np = _np()
    if not np.any(y):
        return y
    v, _m = loudness.measure(y, rate)
    return y if v is None else y * 10 ** ((lufs - v) / 20)


def _speech_band_dip(y, rate, cut_db, f0=1600.0, q=0.5):
    from scipy.signal import lfilter
    a_lin = 10 ** (-abs(cut_db) / 40)
    w0 = 2 * math.pi * f0 / rate
    alpha = math.sin(w0) / (2 * q)
    b = [1 + alpha * a_lin, -2 * math.cos(w0), 1 - alpha * a_lin]
    a = [1 + alpha / a_lin, -2 * math.cos(w0), 1 - alpha / a_lin]
    return lfilter([x / a[0] for x in b], [x / a[0] for x in a], y)


def duck_envelope(n, rate, speech: list[tuple[float, float]], duck_db, attack_s, release_s, bloom_db=0.0, bloom_min_gap_s=0.9):
    """Gain curve: 1.0 in pauses (``bloom_db`` higher in long pauses), 10^(-duck/20) under speech,
    with look-ahead attack and slower release."""
    np = _np()
    ctl_rate = 200
    m = int(n / rate * ctl_rate) + 2
    target = np.ones(m)
    if bloom_db:
        spans = sorted(speech)
        edges = [0.0] + [x for a, b in spans for x in (a, b)] + [n / rate]
        for g0, g1 in zip(edges[::2], edges[1::2]):
            if g1 - g0 >= bloom_min_gap_s and g0 > 0:  # not before the first line
                target[int(g0 * ctl_rate): int(g1 * ctl_rate)] = 10 ** (bloom_db / 20)
    low = 10 ** (-duck_db / 20)
    for a, b in speech:
        target[max(0, int((a - attack_s) * ctl_rate)): int(b * ctl_rate) + 1] = low
    env = np.empty(m)
    g = 1.0
    up = 1 - math.exp(-1 / (release_s * ctl_rate))
    down = 1 - math.exp(-1 / (0.03 * ctl_rate))
    for i in range(m):
        g += (target[i] - g) * (down if target[i] < g else up)
        env[i] = g
    return np.interp(np.arange(n) / rate * ctl_rate, np.arange(m), env)


def render_music(regions: list[Region], stings: list[dict], speech: list[tuple[float, float]], total_s: float, rate: int, cfg: dict):
    """The music bus for the whole episode (already ducked and carved)."""
    np = _np()
    n = int(round(total_s * rate))
    bus = np.zeros(n)
    sa = float(cfg.get("tonic_hz", 146.83))
    xf = float(cfg.get("crossfade_s", 2.0))
    bed = float(cfg.get("bed_lufs", -30))
    accent = float(cfg.get("accent_db", 0))
    gaps = []
    prev = 0.0
    for a, b in sorted(speech):
        if a > prev:
            gaps.append((prev, a))
        prev = max(prev, b)
    gaps.append((prev, total_s))
    for i, r in enumerate(regions):
        spec = cfg["cues"][r.cue]
        a = max(0.0, r.start_s - (xf / 2 if i else 0))
        b = min(total_s, r.end_s + (xf / 2 if i + 1 < len(regions) else 0))
        s0, s1 = int(a * rate), int(b * rate)
        if s1 <= s0 or spec.get("recipe") == "silence":
            continue
        local_gaps = [(max(0, g0 - a), min(b, g1) - a) for g0, g1 in gaps if g1 > a and g0 < b]
        y = synth_cue(r.cue, spec["recipe"], s1 - s0, rate, sa, local_gaps, spec, (i, round(a, 2)))
        y = _norm_to(y, rate, bed + 20 * math.log10(max(0.1, r.intensity)) + accent * float(spec.get("accent", 0)))
        t = np.arange(s1 - s0) / rate
        if r.build_to_end:  # reverent anticipation: rises ~7 dB across the region toward the ending hook
            y *= 10 ** ((7.0 * np.clip(t / max(1e-3, t[-1]), 0, 1) - 3.0) / 20)
        fade = np.ones(s1 - s0)
        if i:
            k = min(len(fade), int(xf * rate)); fade[:k] = np.sin(np.linspace(0, np.pi / 2, k)) ** 2
        if i + 1 < len(regions):
            k = min(len(fade), int(xf * rate)); fade[-k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
        else:
            k = min(len(fade), int(3.0 * rate)); fade[-k:] *= np.cos(np.linspace(0, np.pi / 2, k)) ** 2
        bus[s0:s1] += y * fade
    for st in stings:
        spec = cfg["cues"][st["cue"]]
        y = synth_cue(st["cue"], spec["recipe"], 0, rate, sa, [], spec, st["line_id"])
        y = _norm_to(y, rate, bed + 6 + 20 * math.log10(max(0.1, st["intensity"])) + accent * float(spec.get("accent", 0)))
        s0 = int(st["at_s"] * rate)
        y = y[: max(0, n - s0)]
        bus[s0:s0 + len(y)] += y
    bus = _speech_band_dip(bus, rate, float(cfg.get("speech_band_cut_db", 8)))
    bus *= duck_envelope(n, rate, speech, float(cfg.get("duck_db", 10)), float(cfg.get("duck_attack_s", 0.12)), float(cfg.get("duck_release_s", 0.7)),
                         float(cfg.get("pause_bloom_db", 0)), float(cfg.get("bloom_min_gap_s", 0.9)))
    return bus
