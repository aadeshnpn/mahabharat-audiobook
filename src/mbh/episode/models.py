"""Shared data types for an episode script."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Never

LineType = Literal["narration", "speech", "bridge"]
SegmentKind = Literal["section", "bridge"]
Attribution = Literal["rule", "llm", "override"]

EMOTIONS = (
    "neutral",
    "warm",
    "solemn",
    "solemn_resolve",
    "joyful",
    "angry",
    "contemptuous",
    "grief",
    "fear",
    "pleading",
    "surprised",
    "tender",
    "commanding",
    "mocking",
    "awed",
)

PACES = ("slow", "measured", "moderate", "gentle", "quick")


def assert_never(value: Never) -> Never:
    raise RuntimeError(f"unhandled value: {value!r}")


@dataclass
class ScriptLine:
    id: str
    segment_id: str
    type: LineType
    speaker: str
    voice_id: str
    layer: int
    emotion: str
    pace: str
    intensity: float
    text: str
    tts_text: str
    turn_id: str
    non_kmg: bool = False
    abridged: bool = False
    excerpt: bool = False
    attribution: Attribution = "rule"
    section: int | None = None
    paragraph: int | None = None
    src_span: tuple[int, int] | None = None
    addressee: str | None = None
    direction: str | None = None
    fx: str | None = None
    flags: list[str] = field(default_factory=list)
    start_s: float = 0.0
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "segment_id": self.segment_id,
            "type": self.type,
            "speaker": self.speaker,
            "voice_id": self.voice_id,
            "layer": self.layer,
            "emotion": self.emotion,
            "pace": self.pace,
            "intensity": self.intensity,
            "text": self.text,
            "tts_text": self.tts_text,
            "turn_id": self.turn_id,
            "non_kmg": self.non_kmg,
            "abridged": self.abridged,
            "excerpt": self.excerpt,
            "attribution": self.attribution,
            "section": self.section,
            "paragraph": self.paragraph,
            "src_span": list(self.src_span) if self.src_span else None,
            "addressee": self.addressee,
            "direction": self.direction,
            "fx": self.fx,
            "flags": list(self.flags),
            "start_s": round(self.start_s, 3),
            "duration_s": round(self.duration_s, 3),
        }


@dataclass
class EpisodeScript:
    episode_id: str
    title: str
    book: int
    target_duration_s: float
    estimated_duration_s: float
    timing: dict
    lines: list[ScriptLine]
    warnings: list[str] = field(default_factory=list)
    ending: dict = field(default_factory=dict)
    generated_at: str = ""
    segments: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "title": self.title,
            "book": self.book,
            "target_duration_s": self.target_duration_s,
            "estimated_duration_s": round(self.estimated_duration_s, 3),
            "timing": self.timing,
            "generated_at": self.generated_at,
            "ending": self.ending,
            "segments": self.segments,
            "warnings": list(self.warnings),
            "lines": [ln.to_dict() for ln in self.lines],
        }
