"""Drop KMG parenthetical glosses from text that will be spoken.

Ganguli explains a term in parentheses and leaves the term in the sentence:
"Brahmacharya (study and meditation in celibacy)", "Munis (sages)",
"Dwijas (twice-born)", "Bhishma (the terrible)". The script keeps that
wording. The engine does not say the parenthesis.

A parenthesis whose whole content is a number or an ordinal is kept.
"marked with (three) lines" is the word "three", not a translation.
Anything else in parentheses is a gloss and is removed. A line override
can turn stripping off, or replace ``tts_text`` outright.
"""

from __future__ import annotations

import re

_PAREN = re.compile(r"[ \t]*\(([^()]*)\)")
_NUMBER = re.compile(
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)",
    re.IGNORECASE,
)
_SPACE = re.compile(r"[ \t]{2,}")
_BEFORE_PUNCT = re.compile(r"[ \t]+([,.;:!?])")


def is_gloss(inner: str) -> bool:
    text = inner.strip()
    if not text:
        return False
    return _NUMBER.fullmatch(text) is None


def strip_glosses(text: str) -> str:
    """Return ``text`` with translator glosses removed. The input is not modified."""

    def replace(match: re.Match[str]) -> str:
        if is_gloss(match.group(1)):
            return ""
        return match.group(0)

    cleaned = _PAREN.sub(replace, text)
    cleaned = _SPACE.sub(" ", cleaned)
    cleaned = _BEFORE_PUNCT.sub(r"\1", cleaned)
    return cleaned.strip()


def glosses_removed(before: str, after: str) -> bool:
    return before != after
