"""Master any (stereo or mono) audio to a loudness target with a true-peak ceiling, optional trim and fades."""
from __future__ import annotations

from pathlib import Path

import numpy as np


def master_file(src: Path, out: Path, lufs: float = -16.0, true_peak_db: float = -2.0, start_s: float = 0.0,
                end_s: float | None = None, fade_in_s: float = 1.0, fade_out_s: float = 3.0) -> dict:
    import soundfile as sf

    from mbh.episode import loudness

    y, sr = sf.read(src, always_2d=True)
    y = y[int(start_s * sr):int(end_s * sr) if end_s else None].astype(float)
    n = len(y)
    if fade_in_s > 0:
        k = min(n, int(fade_in_s * sr)); y[:k] *= (np.linspace(0, 1, k) ** 2)[:, None]
    if fade_out_s > 0:
        k = min(n, int(fade_out_s * sr)); y[n - k:] *= (np.linspace(1, 0, k) ** 2)[:, None]
    mid = y.mean(axis=1)
    before, _ = loudness.measure(mid, sr)
    # loudness of a stereo programme ~ sum of channel powers; measure on each channel and combine (BS.1770)
    ch = [loudness.measure(y[:, c], sr)[0] for c in range(y.shape[1])]
    prog = 10 * np.log10(sum(10 ** (c / 10) for c in ch if c is not None)) if any(c is not None for c in ch) else before
    info = {}
    for _ in range(4):
        y = y * 10 ** ((lufs - prog) / 20)
        peak_ceiling = 10 ** ((true_peak_db - 0.5) / 20)
        over = np.abs(y).max()
        if over > peak_ceiling:  # shared-gain limiter (keeps the stereo image): soft clip only the peaks
            env = np.maximum(np.abs(y).max(axis=1), 1e-9)
            g = np.minimum(1.0, peak_ceiling / env)
            k = int(0.005 * sr)
            g = np.convolve(np.pad(g, (k, k), mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
            g = np.minimum(g, 1.0)
            y = y * g[:, None]
        ch = [loudness.measure(y[:, c], sr)[0] for c in range(y.shape[1])]
        prog = 10 * np.log10(sum(10 ** (c / 10) for c in ch))
        info = {"lufs": round(prog, 2), "sample_peak_db": round(20 * np.log10(np.abs(y).max()), 2)}
        if abs(prog - lufs) < 0.1:
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, y, sr, subtype="PCM_16")
    return {"out": str(out), "seconds": round(n / sr, 2), **info}
