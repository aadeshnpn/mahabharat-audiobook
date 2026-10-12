"""Devanagari -> plain lowercase ASCII (for the MMS forced aligner, whose alphabet is a-z and ')."""
from __future__ import annotations

CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "ny",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
VOWELS = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au"}
SIGNS = {"ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au"}
VIRAMA, ANUSVARA, VISARGA, CANDRA = "्", "ं", "ः", "ँ"
VOWEL_LETTERS = set("aeiou")


def to_ascii(text: str) -> str:
    out: list[str] = []
    chars = list(text)
    for i, ch in enumerate(chars):
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if ch in CONS:
            out.append(CONS[ch])
            if nxt not in SIGNS and nxt != VIRAMA and nxt != "़":
                out.append("a")
        elif ch in SIGNS:
            out.append(SIGNS[ch])
        elif ch in VOWELS:
            out.append(VOWELS[ch])
        elif ch in (ANUSVARA, CANDRA):
            out.append("m")
        elif ch == VISARGA:
            out.append("h")
        elif ch == "़" and out:
            continue
    return "".join(out)
