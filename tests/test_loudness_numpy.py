"""The numpy fast path (used for whole episodes) must agree with the pure-Python reference path."""
import math
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from mbh.episode import audioio, loudness


def _signal(rate=24000, seconds=3.0):
    n = int(rate * seconds)
    return [0.3 * math.sin(2 * math.pi * 220 * i / rate) * (0.5 + 0.5 * math.sin(2 * math.pi * 0.7 * i / rate)) for i in range(n)]


def test_numpy_and_pure_paths_agree(monkeypatch, tmp_path: Path):
    x, rate = _signal(), 24000
    fast = (loudness.measure(x, rate), loudness.master(x, rate, -16.0, -1.0)[1]["after"])
    assert isinstance(loudness.gain(x, 1.0), np.ndarray)
    audioio.write_pcm16(tmp_path / "a.wav", np.asarray(x), rate)
    y_fast, _ = audioio.read_mono(tmp_path / "a.wav")
    monkeypatch.setattr(loudness, "_np", None); monkeypatch.setattr(loudness, "_lfilter", None); monkeypatch.setattr(audioio, "_np", None)
    slow = (loudness.measure(x, rate), loudness.master(x, rate, -16.0, -1.0)[1]["after"])
    assert fast == slow
    audioio.write_pcm16(tmp_path / "b.wav", x, rate)
    y_slow, _ = audioio.read_mono(tmp_path / "b.wav")
    assert (tmp_path / "a.wav").read_bytes() == (tmp_path / "b.wav").read_bytes()
    assert max(abs(a - b) for a, b in zip(y_fast, y_slow)) == 0
