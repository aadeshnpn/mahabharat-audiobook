"""Duration model. Speech rate is calibrated from the VoxCPM2 prototype excerpt."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from mbh.episode.models import ScriptLine
from mbh.episode.paths import repo_root

# proto/excerpt_100.json: 250 words, 99 s of audio, 5.75 s of assemble gaps
# (one 0.25 s same-speaker gap and eleven 0.50 s speaker changes).
# 250 / ((99 - 5.75) / 60) = 160.9 wpm.
PROTOTYPE_WPM = 160.9
PROTOTYPE_AUDIO_S = 99.0


@dataclass(frozen=True)
class Timing:
    wpm: float = PROTOTYPE_WPM
    gap_same_speaker_s: float = 0.25
    gap_speaker_change_s: float = 0.50
    gap_paragraph_s: float = 1.50
    gap_segment_s: float = 1.50

    def to_dict(self) -> dict:
        return {
            "wpm": self.wpm,
            "gaps": {
                "same_speaker_s": self.gap_same_speaker_s,
                "speaker_change_s": self.gap_speaker_change_s,
                "paragraph_s": self.gap_paragraph_s,
                "segment_s": self.gap_segment_s,
            },
        }


@dataclass(frozen=True)
class EngineSettings:
    name: str = "voxcpm2"
    steps: int = 10
    cfg_value: float = 2.0
    sample_rate: int = 48000
    loudness_lufs: float = -16.0
    true_peak_db: float = -1.5


def load_timing_data(path: Path | None = None) -> dict:
    file = path or (repo_root() / "configs" / "duration.yaml")
    data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{file} is not a mapping")
    return data


def global_strip_glosses(path: Path | None = None) -> bool:
    """Default for the gloss rule. Missing key means strip."""
    return bool(load_timing_data(path).get("strip_glosses", True))


def load_timing(path: Path | None = None) -> tuple[Timing, EngineSettings]:
    data = load_timing_data(path)
    gaps = data.get("gaps") or {}
    engine = data.get("engine") or {}
    loud = data.get("loudness") or {}
    timing = Timing(
        wpm=float(data.get("wpm", PROTOTYPE_WPM)),
        gap_same_speaker_s=float(gaps.get("same_speaker_s", 0.25)),
        gap_speaker_change_s=float(gaps.get("speaker_change_s", 0.50)),
        gap_paragraph_s=float(gaps.get("paragraph_s", 1.50)),
        gap_segment_s=float(gaps.get("segment_s", 1.50)),
    )
    settings = EngineSettings(
        name=str(engine.get("name", "voxcpm2")),
        steps=int(engine.get("steps", 10)),
        cfg_value=float(engine.get("cfg_value", 2.0)),
        sample_rate=int(engine.get("sample_rate", 48000)),
        loudness_lufs=float(loud.get("integrated_lufs", -16)),
        true_peak_db=float(loud.get("true_peak_db", -1.5)),
    )
    return timing, settings


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def speech_seconds(text: str, timing: Timing) -> float:
    words = word_count(text)
    if timing.wpm <= 0:
        raise ValueError("wpm must be positive")
    return words / timing.wpm * 60.0


def gap_before(curr: ScriptLine, prev: ScriptLine | None, timing: Timing) -> float:
    if prev is None:
        return 0.0
    if curr.segment_id != prev.segment_id:
        return timing.gap_segment_s
    if curr.section != prev.section or curr.paragraph != prev.paragraph:
        return timing.gap_paragraph_s
    if curr.speaker != prev.speaker:
        return timing.gap_speaker_change_s
    return timing.gap_same_speaker_s


def apply_timing(lines: list[ScriptLine], timing: Timing) -> float:
    """Fill start_s and duration_s. Return the total duration in seconds."""
    prev: ScriptLine | None = None
    cursor = 0.0
    for line in lines:
        cursor += gap_before(line, prev, timing)
        line.start_s = cursor
        line.duration_s = speech_seconds(line.tts_text or line.text, timing)
        cursor += line.duration_s
        prev = line
    return cursor


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"
