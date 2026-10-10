"""Rule-of-thumb emotion and pace. Overrides replace these after a rebuild."""

from __future__ import annotations

import re

from mbh.episode.models import EMOTIONS, LineType

EMOTION_PHRASE = {
    "neutral": "calm",
    "warm": "warm",
    "solemn": "solemn",
    "solemn_resolve": "solemn and resolute",
    "joyful": "joyful",
    "angry": "angry",
    "contemptuous": "contemptuous",
    "grief": "grief-stricken",
    "fear": "afraid",
    "pleading": "pleading",
    "surprised": "surprised",
    "tender": "tender and gentle",
    "commanding": "commanding and noble",
    "mocking": "mocking",
    "awed": "full of awe",
}


def phrase(emotion: str) -> str:
    return EMOTION_PHRASE.get(emotion, emotion)


def infer(text: str, line_type: LineType, speaker: str) -> tuple[str, str, float, str | None]:
    """Return emotion, pace, intensity, and an optional performance direction."""
    low = text.lower()
    if speaker == "devas_chorus" or "the terrible" in low:
        return "awed", "slow", 0.75, "a voice from the heavens"
    if any(token in low for token in ("brahmacharya", "vow of", "sonless", "from this day i adopt")):
        return "solemn_resolve", "slow", 0.85, "a sacred vow before assembled kings"
    if re.search(r"\bo mother\b|\bo timid\b", low):
        return "tender", "gentle", 0.55, None
    if "bestow" in low or low.startswith("i bestow"):
        return "joyful", "quick", 0.7, None
    if any(token in low for token in ("stood on end", "rain down flowers", "shower")):
        return "awed", "measured", 0.65, None
    if re.search(r"\b(listen|ye kings|relinquish)\b", low):
        return "commanding", "slow", 0.7, None
    if low.startswith("om!") or "bowed down" in low:
        return "solemn", "slow", 0.6, None
    if "grief" in low or "alas" in low:
        return "grief", "slow", 0.7, None
    if "anger" in low or "wroth" in low:
        return "angry", "moderate", 0.65, None
    if "?" in text and line_type == "speech":
        return "warm", "measured", 0.5, None
    if line_type == "speech" and re.search(r"\b(sacred|purana|vedas|veda)\b", low):
        return "solemn", "measured", 0.55, None
    if line_type == "speech" and speaker in {"sauti", "vaisampayana"}:
        return "warm", "measured", 0.5, None
    if line_type == "narration":
        return "warm", "measured", 0.4, None
    if line_type == "bridge":
        return "warm", "measured", 0.45, None
    if line_type == "speech":
        return "warm", "moderate", 0.45, None
    return "neutral", "moderate", 0.45, None


def check_emotion(emotion: str) -> str:
    if emotion not in EMOTIONS:
        known = ", ".join(EMOTIONS)
        raise ValueError(f"unknown emotion {emotion!r}; expected one of: {known}")
    return emotion
