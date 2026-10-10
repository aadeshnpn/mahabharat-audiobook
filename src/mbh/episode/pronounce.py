"""Speakable respellings and the scoring helpers of the pronunciation harness.

VoxCPM2 reads ALL-CAPS hyphenated syllables ("VAY-duhs", "UP-suh-rahs") as letters or garbles
them, so TTS text must carry names as ordinary-looking words. ``spoken`` in the lexicon holds the
verified form; ``speakable_respelling`` turns a stress-marked guide respelling into the fallback
form for unverified rows. The rest of this module scores harness clips (no models imported here).
"""

from __future__ import annotations

import re

# ---------- respelling format ----------

def speakable_respelling(respelling: str) -> str:
    """'vy-shum-PAA-yuh-nuh' -> 'Vyshumpaayuhnuh'; 'KRISH-nuh dwy-PAH-yuh-nuh' -> 'Krishnuh Dwypahyuhnuh'.

    Lowercase (caps read as letters), hyphens joined (hyphen chunks read as separate words with odd
    prosody), each space-separated word capitalised like a proper noun. Apostrophe-s and plural s
    stay attached by the caller.
    """
    words = []
    for word in respelling.split():
        joined = re.sub(r"[-\u00ad\u2010\u2011]", "", word).lower()
        if joined:
            words.append(joined[0].upper() + joined[1:])
    return " ".join(words)


def is_tts_safe(form: str) -> bool:
    """True when a TTS form has no shouted syllables or hyphen chunks that VoxCPM2 spells out."""
    if re.search(r"\b[A-Z]{2,}", form):
        return False
    return "-" not in form


# ---------- scoring ----------

CARRIER = "Then {word} spoke again, softly."

_VOWEL_CLASS = {"AA": "A", "AH": "A", "AO": "A", "AE": "A", "IY": "I", "IH": "I", "UW": "U", "UH": "U",
                "EY": "E", "EH": "E", "ER": "AR", "OW": "O", "AW": "AW", "AY": "AY", "OY": "OY"}
_CONS_CLASS = {"Z": "S", "DH": "D", "TH": "T", "W": "V", "ZH": "SH"}


def phone_classes(phones: list[str] | str) -> list[str]:
    """Collapse ARPAbet to coarse classes: stress dropped, near vowels merged (an Indian-English
    'a' may be heard as AA, AH or AE), voicing-only and v/w contrasts merged."""
    if isinstance(phones, str):
        phones = phones.split()
    out = []
    for p in phones:
        p = re.sub(r"\d", "", p.upper())
        if not p:
            continue
        p = _VOWEL_CLASS.get(p, _CONS_CLASS.get(p, p))
        if p == "AR":
            out += ["A", "R"]
        else:
            out.append(p)
    return out


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def phoneme_similarity(heard: list[str] | str, intended: list[str] | str) -> float:
    """1 - normalised edit distance over coarse phone classes (1.0 = same sounds)."""
    a, b = phone_classes(heard), phone_classes(intended)
    if not a and not b:
        return 1.0
    return round(1 - edit_distance(a, b) / max(len(a), len(b)), 3)


_LETTERS = re.compile(r"\b(?:[A-Za-z]\.\s*){2,}|\b(?:[A-Z]\s){2,}[A-Z]\b|\b[A-Z]{2,}\b")


def looks_spelled_out(asr_text: str) -> bool:
    """ASR evidence that the engine read letters ('V.A.Y. does', 'S.O.T.', 'V A Y')."""
    return bool(_LETTERS.search(asr_text))


def extract_target(asr_text: str, before: str = "then", after: str = "spoke") -> tuple[str, bool]:
    """Words the ASR heard between the carrier's anchors. Returns (target, carrier_ok)."""
    toks = re.findall(r"[A-Za-z][A-Za-z.']*", asr_text)
    low = [t.lower().strip(".'") for t in toks]
    try:
        i = low.index(before)
        j = low.index(after, i + 1)
    except ValueError:
        return " ".join(toks), False
    tail_ok = "again" in low[j:] and "softly" in low[j:]
    return " ".join(toks[i + 1:j]), tail_ok


_DIGRAPHS = [("aa", "a"), ("ee", "i"), ("oo", "u"), ("ai", "y"), ("ay", "e"), ("au", "w"), ("ow", "w"), ("bh", "b"),
             ("dh", "d"), ("th", "t"), ("kh", "k"), ("gh", "g"), ("ph", "p"), ("ch", "c"), ("sh", "s"), ("ck", "k")]


def roman_key(text: str) -> str:
    """Coarse sound key for romanised Sanskrit / English spellings: aspiration and vowel length
    dropped, a/u (schwa) merged, w=v, z=s, doubled letters collapsed."""
    t = re.sub(r"[^a-z]", "", text.lower())
    for a, b in _DIGRAPHS:
        t = t.replace(a, b)
    t = t.translate(str.maketrans({"u": "a", "o": "a", "w": "v", "z": "s", "q": "k", "x": "k"}))
    t = re.sub(r"(.)\1+", r"\1", t)
    return t


def key_similarity(heard: str, intended_spelling: str) -> float:
    a, b = list(roman_key(heard)), list(roman_key(intended_spelling))
    if not a and not b:
        return 1.0
    return round(1 - edit_distance(a, b) / max(len(a), len(b)), 3)


def extract_between(asr_text: str, before: str = "then", after: str = "spoke") -> str | None:
    """Target words between the anchors, or None when the carrier itself was not rendered."""
    toks = re.findall(r"[A-Za-z][A-Za-z.']*", asr_text)
    low = [t.lower().strip(".'") for t in toks]
    if before not in low:
        return None
    i = low.index(before)
    if after in low[i + 1:]:
        return " ".join(toks[i + 1:low.index(after, i + 1)])
    tail = [k for k, w in enumerate(low[i + 1:], i + 1) if w in ("again", "softly")]
    return " ".join(toks[i + 1:tail[0]]) if tail else None
