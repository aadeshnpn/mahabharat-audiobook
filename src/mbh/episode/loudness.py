"""ITU-R BS.1770-4 loudness, per-line normalisation and episode mastering. No required dependencies.

K-weighting and gating follow libebur128 (shelf + high-pass biquads re-derived for any sample rate,
400 ms blocks with 75 % overlap, -70 LUFS absolute gate, -10 LU relative gate). scipy, when present,
only accelerates the filters. Lines too short to gate reliably (< ``SHORT_S``) use the same gating on
100 ms blocks, offset to agree with integrated loudness on speech (``SHORT_OFFSET_DB``).
"""

from __future__ import annotations

import math

try:  # optional accelerator; results are identical to the pure-Python path
    from scipy.signal import lfilter as _lfilter
    import numpy as _np
except Exception:  # pragma: no cover - exercised where scipy is absent
    _lfilter = None
    _np = None

SHORT_S = 1.5
MAX_LINE_GAIN_DB = 24.0  # rendered lines measured down to -35 LUFS (needs +19 dB to reach -16)
_FLOOR = -70.0


def _coeffs(rate: int) -> list[tuple[list[float], list[float]]]:
    f0, gain_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / rate)
    vh = 10 ** (gain_db / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    shelf = ([(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0],
             [1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / rate)
    d = 1 + k / q + k * k
    highpass = ([1.0, -2.0, 1.0], [1.0, 2 * (k * k - 1) / d, (1 - k / q + k * k) / d])
    return [shelf, highpass]


def _biquad(x: list[float], b: list[float], a: list[float]) -> list[float]:
    b0, b1, b2 = b
    _a0, a1, a2 = a
    x1 = x2 = y1 = y2 = 0.0
    out = [0.0] * len(x)
    for i, xn in enumerate(x):
        yn = b0 * xn + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, xn, y1, yn
        out[i] = yn
    return out


def k_weighted_power(samples, rate: int) -> list[float]:
    """Squared K-weighted signal."""
    if _lfilter is not None:
        y = _np.asarray(samples, dtype=float)
        for b, a in _coeffs(rate):
            y = _lfilter(b, a, y)
        return (y * y).tolist()
    y = list(samples)
    for b, a in _coeffs(rate):
        y = _biquad(y, b, a)
    return [v * v for v in y]


def _prefix(power: list[float]) -> list[float]:
    acc, out = 0.0, [0.0]
    for p in power:
        acc += p
        out.append(acc)
    return out


def _lufs(ms: float) -> float:
    return -0.691 + 10 * math.log10(ms) if ms > 0 else float("-inf")


def integrated_lufs(samples, rate: int, power: list[float] | None = None) -> float | None:
    """Gated integrated loudness (LUFS), or None when there is no block above the absolute gate."""
    power = power if power is not None else k_weighted_power(samples, rate)
    block, step = int(0.4 * rate), int(0.1 * rate)
    if len(power) < block:
        return None
    pre = _prefix(power)
    z = [(pre[s + block] - pre[s]) / block for s in range(0, len(power) - block + 1, step)]
    z = [v for v in z if _lufs(v) > _FLOOR]
    if not z:
        return None
    rel = _lufs(sum(z) / len(z)) - 10
    gated = [v for v in z if _lufs(v) > rel]
    return round(_lufs(sum(gated) / len(gated)), 2)


SHORT_OFFSET_DB = -0.9  # calibrated on 26 rendered speech clips >= 2 s: short gating reads 0.92 dB above BS.1770


def short_lufs(samples, rate: int, power: list[float] | None = None) -> float | None:
    """Short-clip fallback: BS.1770 gating on 100 ms blocks (25 ms hop), calibrated to integrated."""
    power = power if power is not None else k_weighted_power(samples, rate)
    block, step = max(1, int(0.1 * rate)), max(1, int(0.025 * rate))
    if len(power) < block:
        block = step = len(power)
    if not power:
        return None
    pre = _prefix(power)
    z = [(pre[s + block] - pre[s]) / block for s in range(0, len(power) - block + 1, step)]
    z = [v for v in z if _lufs(v) > _FLOOR]
    if not z:
        return None
    rel = _lufs(sum(z) / len(z)) - 10
    gated = [v for v in z if _lufs(v) > rel]
    return round(_lufs(sum(gated) / len(gated)) + SHORT_OFFSET_DB, 2)


def measure(samples, rate: int) -> tuple[float | None, str]:
    """(loudness, method). Integrated BS.1770 for lines >= SHORT_S, calibrated short gating otherwise."""
    power = k_weighted_power(samples, rate)
    if len(samples) >= SHORT_S * rate:
        value = integrated_lufs(samples, rate, power)
        if value is not None:
            return value, "bs1770"
    return short_lufs(samples, rate, power), "short"


def gain(samples, db: float) -> list[float]:
    g = 10 ** (db / 20)
    return [s * g for s in samples]


def normalize_line(samples, rate: int, target_lufs: float) -> tuple[list[float], dict]:
    """Bring one rendered line to the target loudness (gain clamped to +/-MAX_LINE_GAIN_DB)."""
    before, method = measure(samples, rate)
    if before is None:
        return list(samples), {"before": None, "method": method, "gain_db": 0.0}
    g = max(-MAX_LINE_GAIN_DB, min(MAX_LINE_GAIN_DB, target_lufs - before))
    return gain(samples, g), {"before": before, "method": method, "gain_db": round(g, 2)}


def limit_peaks(samples, rate: int, ceiling_db: float, attack_ms: float = 5.0, release_ms: float = 60.0) -> tuple[list[float], int]:
    """Sparse look-ahead peak limiter: gain dips only around samples above the ceiling, with a linear
    attack before and release after each over. Returns (samples, number of overs)."""
    ceiling = 10 ** (ceiling_db / 20)
    overs = [i for i, s in enumerate(samples) if abs(s) > ceiling]
    if not overs:
        return list(samples), 0
    att, rel = max(1, int(attack_ms / 1000 * rate)), max(1, int(release_ms / 1000 * rate))
    g: dict[int, float] = {}
    for i in overs:
        need = ceiling / abs(samples[i])
        for j in range(max(0, i - att), min(len(samples), i + rel + 1)):
            if j <= i:
                w = need + (1 - need) * (i - j) / att
            else:
                w = need + (1 - need) * (j - i) / rel
            if w < g.get(j, 1.0):
                g[j] = w
    out = list(samples)
    for j, w in g.items():
        out[j] *= w
    return out, len(overs)


def master(samples, rate: int, target_lufs: float, true_peak_db: float, margin_db: float = 0.5, tolerance: float = 0.1) -> tuple[list[float], dict]:
    """Gain the joined episode to ``target_lufs``, limit sample peaks to ``true_peak_db - margin_db``
    (margin covers inter-sample peaks and lossy encoding), and re-measure until within ``tolerance``."""
    before = integrated_lufs(samples, rate)
    if before is None:
        return list(samples), {"before": None, "after": None, "iterations": 0}
    g, out, overs, after = target_lufs - before, list(samples), 0, before
    for it in range(1, 5):
        out, overs = limit_peaks(gain(samples, g), rate, true_peak_db - margin_db)
        after = integrated_lufs(out, rate)
        if after is None or abs(after - target_lufs) <= tolerance:
            break
        g += target_lufs - after
    peak = max(abs(s) for s in out)
    return out, {"before": before, "after": after, "gain_db": round(g, 2), "iterations": it, "limited_samples": overs,
                 "sample_peak_db": round(20 * math.log10(peak), 2) if peak else None}
