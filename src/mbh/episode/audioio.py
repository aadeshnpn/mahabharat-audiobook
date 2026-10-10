"""Read and write mono WAV without extra dependencies. PCM 16-bit is the cache format."""

from __future__ import annotations

import struct
import wave
from pathlib import Path


def write_pcm16(path: Path, samples: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for sample in samples:
        clamped = max(-1.0, min(1.0, sample))
        frames += struct.pack("<h", int(clamped * 32767))
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)


def read_mono(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), "r") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError(f"{path} is not 16-bit PCM; the cache writer stores PCM 16-bit")
    count = len(frames) // 2
    ints = struct.unpack("<" + "h" * count, frames)
    if channels == 1:
        return [sample / 32767.0 for sample in ints], rate
    mono = []
    for index in range(0, len(ints), channels):
        mono.append(sum(ints[index:index + channels]) / channels / 32767.0)
    return mono, rate


def resample(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
    if src_rate == dst_rate or not samples:
        return list(samples)
    duration = len(samples) / src_rate
    out_len = max(1, int(round(duration * dst_rate)))
    out: list[float] = []
    for index in range(out_len):
        pos = index * src_rate / dst_rate
        left = int(pos)
        frac = pos - left
        right = min(left + 1, len(samples) - 1)
        out.append(samples[left] * (1 - frac) + samples[right] * frac)
    return out
