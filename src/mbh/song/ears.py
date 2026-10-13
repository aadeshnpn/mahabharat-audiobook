"""Ears-like proxies for a sung render (beyond ASR): is it actually sung, and does it have dynamics?

* ``voiced``: fraction of frames with a confident pitch in the male singing range (pYIN on a vocal-band-filtered mix).
* ``sustain_s``: total time inside held notes (pitch within +-35 cents for >= 0.6 s); ``longest_s``: the longest one.
  Speech has almost none; a sung line with held vowels has several seconds.
* ``wobble_c``: median pitch deviation (cents) inside held notes; small = stable singing (vibrato stays < ~40).
* ``lra_db``: spread of 3 s loudness (95th - 10th percentile); ``build_db``: last third minus first third (a build-up is > 0).
Mix-level proxies: accompaniment can leak into the pitch track, so compare candidates against each other, not absolutes."""
from __future__ import annotations

import numpy as np


def sung_metrics(path, sr: int = 22050, vocals=None) -> dict:
    """``vocals``: a separated vocal stem (demucs) for the pitch metrics; dynamics always come from ``path`` (the mix)."""
    import librosa, scipy.signal as ss
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    if vocals is not None:
        v = librosa.load(str(vocals), sr=sr, mono=True)[0]
    else:
        v = ss.sosfilt(ss.butter(4, [90, 1200], "bandpass", fs=sr, output="sos"), y)
    hop = 256
    f0, vflag, vprob = librosa.pyin(v, fmin=80, fmax=520, sr=sr, hop_length=hop, frame_length=2048)
    dt = hop / sr
    ok = vflag & (vprob > 0.15)
    cents = 1200 * np.log2(np.where(ok, f0, 1.0) / 55.0)
    held, wob, run = [], [], []
    def close():
        if len(run) * dt >= 0.6:
            held.append(len(run) * dt); wob.append(float(np.mean(np.abs(np.array(run) - np.median(run)))))
    for i in range(len(f0)):
        if ok[i] and run and abs(cents[i] - np.median(run[-12:])) < 35: run.append(cents[i]); continue
        close(); run = [cents[i]] if ok[i] else []
    close()
    w = int(3 * sr); rms = [20 * np.log10(np.sqrt(np.mean(y[i:i + w] ** 2)) + 1e-9) for i in range(0, max(1, len(y) - w), sr // 2)]
    rms = np.array(rms); n = len(rms)
    return dict(voiced=round(float(ok.mean()), 2), sustain_s=round(sum(held), 1), longest_s=round(max(held, default=0), 1),
                wobble_c=round(float(np.median(wob)) if wob else 0.0, 1),
                lra_db=round(float(np.percentile(rms, 95) - np.percentile(rms, 10)), 1),
                build_db=round(float(rms[-n // 3:].mean() - rms[: n // 3].mean()), 1) if n >= 3 else 0.0)
