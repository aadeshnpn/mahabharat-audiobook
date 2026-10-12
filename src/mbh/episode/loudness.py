"""ITU-R BS.1770-4 loudness, per-line normalisation and episode mastering. No required dependencies.

K-weighting and gating follow libebur128 (shelf + high-pass biquads re-derived for any sample rate,
400 ms blocks with 75 % overlap, -70 LUFS absolute gate, -10 LU relative gate). numpy/scipy, when
present, keep whole episodes as float arrays (a 17 min episode as Python lists needs several GB) and accelerate
the filters; results match the pure-Python path to rounding. Lines too short to gate reliably (< ``SHORT_S``) use the same gating on
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
        return y * y
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


def _gate(power, block: int, step: int):
    """Mean-square of each gating block (absolute gate applied); None when nothing passes."""
    if _np is not None:
        pre = _np.concatenate(([0.0], _np.cumsum(_np.asarray(power, dtype=float))))
        starts = _np.arange(0, len(power) - block + 1, step)
        z = (pre[starts + block] - pre[starts]) / block
        z = z[z > 10 ** ((_FLOOR + 0.691) / 10)]
        if not len(z):
            return None
        rel = _lufs(float(z.mean())) - 10
        gated = z[z > 10 ** ((rel + 0.691) / 10)]
        return float(gated.mean())
    pre = _prefix(power)
    z = [(pre[s + block] - pre[s]) / block for s in range(0, len(power) - block + 1, step)]
    z = [v for v in z if _lufs(v) > _FLOOR]
    if not z:
        return None
    rel = _lufs(sum(z) / len(z)) - 10
    gated = [v for v in z if _lufs(v) > rel]
    return sum(gated) / len(gated)


def _lufs(ms: float) -> float:
    return -0.691 + 10 * math.log10(ms) if ms > 0 else float("-inf")


def integrated_lufs(samples, rate: int, power: list[float] | None = None) -> float | None:
    """Gated integrated loudness (LUFS), or None when there is no block above the absolute gate."""
    power = power if power is not None else k_weighted_power(samples, rate)
    block, step = int(0.4 * rate), int(0.1 * rate)
    if len(power) < block:
        return None
    ms = _gate(power, block, step)
    return None if ms is None else round(_lufs(ms), 2)


SHORT_OFFSET_DB = -0.9  # calibrated on 26 rendered speech clips >= 2 s: short gating reads 0.92 dB above BS.1770


def short_lufs(samples, rate: int, power: list[float] | None = None) -> float | None:
    """Short-clip fallback: BS.1770 gating on 100 ms blocks (25 ms hop), calibrated to integrated."""
    power = power if power is not None else k_weighted_power(samples, rate)
    block, step = max(1, int(0.1 * rate)), max(1, int(0.025 * rate))
    if len(power) < block:
        block = step = len(power)
    if not len(power):
        return None
    ms = _gate(power, block, step)
    return None if ms is None else round(_lufs(ms) + SHORT_OFFSET_DB, 2)


def measure(samples, rate: int) -> tuple[float | None, str]:
    """(loudness, method). Integrated BS.1770 for lines >= SHORT_S, calibrated short gating otherwise."""
    power = k_weighted_power(samples, rate)
    if len(samples) >= SHORT_S * rate:
        value = integrated_lufs(samples, rate, power)
        if value is not None:
            return value, "bs1770"
    return short_lufs(samples, rate, power), "short"


def gain(samples, db: float):
    g = 10 ** (db / 20)
    if _np is not None:
        return _np.asarray(samples, dtype=float) * g
    return [s * g for s in samples]


def normalize_line(samples, rate: int, target_lufs: float) -> tuple[list[float], dict]:
    """Bring one rendered line to the target loudness (gain clamped to +/-MAX_LINE_GAIN_DB)."""
    before, method = measure(samples, rate)
    if before is None:
        return _copy(samples), {"before": None, "method": method, "gain_db": 0.0}
    g = max(-MAX_LINE_GAIN_DB, min(MAX_LINE_GAIN_DB, target_lufs - before))
    return gain(samples, g), {"before": before, "method": method, "gain_db": round(g, 2)}


def _copy(samples):
    return _np.array(samples, dtype=float) if _np is not None else list(samples)


def limit_peaks(samples, rate: int, ceiling_db: float, attack_ms: float = 5.0, release_ms: float = 60.0) -> tuple[list[float], int]:
    """Sparse look-ahead peak limiter: gain dips only around samples above the ceiling, with a linear
    attack before and release after each over. Returns (samples, number of overs)."""
    ceiling = 10 ** (ceiling_db / 20)
    if _np is not None:
        x = _np.asarray(samples, dtype=float)
        idx = _np.flatnonzero(_np.abs(x) > ceiling)
        if not len(idx):
            return x.copy(), 0
        att, rel = max(1, int(attack_ms / 1000 * rate)), max(1, int(release_ms / 1000 * rate))
        g = _np.ones(len(x))
        for i in idx:
            need = ceiling / abs(x[i])
            j0, j1 = max(0, i - att), min(len(x), i + rel + 1)
            j = _np.arange(j0, j1)
            w = _np.where(j <= i, need + (1 - need) * (i - j) / att, need + (1 - need) * (j - i) / rel)
            g[j0:j1] = _np.minimum(g[j0:j1], w)
        return x * g, int(len(idx))
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
        return _copy(samples), {"before": None, "after": None, "iterations": 0}
    g, out, overs, after = target_lufs - before, _copy(samples), 0, before
    for it in range(1, 5):
        out, overs = limit_peaks(gain(samples, g), rate, true_peak_db - margin_db)
        after = integrated_lufs(out, rate)
        if after is None or abs(after - target_lufs) <= tolerance:
            break
        g += target_lufs - after
    peak = float(_np.max(_np.abs(out))) if _np is not None and len(out) else max((abs(s) for s in out), default=0.0)
    return out, {"before": before, "after": after, "gain_db": round(g, 2), "iterations": it, "limited_samples": overs,
                 "sample_peak_db": round(20 * math.log10(peak), 2) if peak else None}
