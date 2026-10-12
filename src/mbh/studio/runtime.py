"""Heavy-synthesis switch. Tests and the UI smoke server set the mock backend.

The mock writes a short tone instead of loading VoxCPM2, Whisper, or the voice-design
model. Production leaves this off; jobs then call the same tools as the CLI.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from mbh.episode.audioio import write_pcm16

_mock = False
_backend_factory = None


def use_mock(on: bool = True) -> None:
    global _mock
    _mock = on


def set_backend_factory(factory) -> None:
    """Replace the synthesis backend. Pass None to restore the default."""
    global _backend_factory
    _backend_factory = factory


def mock_enabled() -> bool:
    return _mock or os.environ.get("MBH_STUDIO_MOCK") == "1"


class ToneBackend:
    """A SynthesisBackend that writes a short tone. Cache keys still match the real renderer."""

    engine = "mock"

    def synthesize(self, *, text: str, instruction: str, reference_wav: Path, out_wav: Path, params: dict) -> None:
        del text, instruction, reference_wav, params
        write_pcm16(out_wav, tone(), 16000)


def tone(seconds: float = 0.35, rate: int = 16000, freq: float = 220.0, amp: float = 0.15) -> list[float]:
    count = int(seconds * rate)
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(count)]


def backend():
    if _backend_factory is not None:
        return _backend_factory()
    if mock_enabled():
        return ToneBackend()
    from mbh.episode.render import VoxCPM2Backend

    return VoxCPM2Backend()
