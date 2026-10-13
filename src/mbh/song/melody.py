"""Swara notation -> frequencies and note events (pure Python, no numpy).

Notation (Bhatkhande-like, ASCII): S r R g G m M P d D n N
  r g d n = komal (flat), M = tivra ma (sharp 4th), m = shuddha ma.
  suffix "." = lower octave (mandra), "'" = upper octave (taar); may repeat ("S''").
  "-" is a rest.
Ratios are just-intonation, the usual choice for drone-based music.
"""
from __future__ import annotations

from dataclasses import dataclass

RATIOS = {
    "S": 1.0, "r": 16 / 15, "R": 9 / 8, "g": 6 / 5, "G": 5 / 4, "m": 4 / 3, "M": 45 / 32,
    "P": 3 / 2, "d": 8 / 5, "D": 5 / 3, "n": 9 / 5, "N": 15 / 8,
}

# common raga scales (allowed swaras), used to validate a melody against its raga
RAGAS = {
    "yaman": set("SRGMPDN"),
    "bhupali": set("SRGPD"),
    "kalyan": set("SRGMPDN"),
    "bhairav": set("SrGmPdN"),
    "khamaj": set("SRGmPDNn"),
    "durga": set("SRmPD"),
}


def parse_swara(token: str) -> tuple[str, int]:
    """'N.' -> ('N', -1); "S'" -> ('S', 1)."""
    token = token.strip()
    if not token or token[0] not in RATIOS:
        raise ValueError(f"bad swara {token!r}")
    rest = token[1:]
    if any(ch not in ".'" for ch in rest):
        raise ValueError(f"bad octave mark in {token!r}")
    return token[0], rest.count("'") - rest.count(".")


def swara_hz(token: str, sa_hz: float) -> float:
    name, octave = parse_swara(token)
    return sa_hz * RATIOS[name] * (2.0 ** octave)


@dataclass
class Note:
    swara: str          # e.g. "G", "N.", "-" for rest
    beats: float
    syllable: int       # index into the line's syllables (-1 for a rest)
    start_beat: float = 0.0

    @property
    def is_rest(self) -> bool:
        return self.swara == "-"


def parse_line_melody(melody: list, syllables: list[str]) -> list[Note]:
    """``melody`` has one entry per syllable: "G:1" (one note), "N.:0.5 R:1" (melisma), or "-:1" rests in between
    written as their own entry ``{"rest": 1}``. Returns notes with start beats."""
    notes: list[Note] = []
    beat = 0.0
    syl = 0
    for entry in melody:
        if isinstance(entry, dict) and "rest" in entry:
            notes.append(Note("-", float(entry["rest"]), -1, beat))
            beat += float(entry["rest"])
            continue
        if syl >= len(syllables):
            raise ValueError(f"melody has more entries than the {len(syllables)} syllables")
        for part in str(entry).split():
            swara, _, dur = part.partition(":")
            parse_swara(swara)
            d = float(dur or 1)
            if d <= 0:
                raise ValueError(f"note length must be positive in {part!r}")
            notes.append(Note(swara, d, syl, beat))
            beat += d
        syl += 1
    if syl != len(syllables):
        raise ValueError(f"melody covers {syl} syllables, the line has {len(syllables)}")
    return notes


def check_raga(notes: list[Note], raga: str | None) -> list[str]:
    """Swaras outside the raga's scale (empty list = fine)."""
    if not raga or raga.lower() not in RAGAS:
        return []
    allowed = RAGAS[raga.lower()]
    return sorted({n.swara for n in notes if not n.is_rest and parse_swara(n.swara)[0] not in allowed})
