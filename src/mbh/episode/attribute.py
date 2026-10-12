"""Turn a section paragraph into narrator and speaker lines.

The rule attributor is the default. ``LLMAttributor`` can replace it: pass a
callable ``(section, paragraph, text, lines) -> lines | None``. Returning None
keeps the rule result. No network call is made unless that callable does it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Protocol

from mbh.characters.build_extracted import GENERIC, PHRASE_SPEAKERS
from mbh.episode.cast import Cast

_VERBS = "said|replied|answered|asked|continued|rejoined|spoke|exclaimed|spake|saying"
INTRO_RE = re.compile(
    rf"\b(?P<verb>{_VERBS})"
    rf"(?:\s+(?:him|her|them|again|then|also|thereupon))*"
    rf"\s*[,:.]"
    rf"(?P<bridge>\s+[^'\"“”‘’]{{0,180}}?,)?"
    rf"\s*"
    rf"(?P<q>['\"“”‘’])",
    re.IGNORECASE,
)
_ABBR = re.compile(r"\b(?:viz|i\.e|e\.g|Mr|Mrs|Dr|Sri|St)\.$", re.IGNORECASE)
_GENITIVE = re.compile(
    r"(?:\b(?:of|to|unto|upon|addressed|addressing|beholding|seeing)\s+(?:the\s+)?|\bO\s+)$",
    re.IGNORECASE,
)
_ONE_OF = re.compile(r"\bone\s+of\s+(?:the\s+)?$", re.IGNORECASE)

# Patterns the quote-anchored pass needs beyond characters/build_extracted.PHRASE_SPEAKERS.
EXTRA_PHRASES: list[tuple[int, int, str, str]] = [
    (1, 2, r"one of the Rishis", "naimisha_rishis"),
    (100, 100, r"Apsaras and the gods", "devas_chorus"),
]


@dataclass
class RawLine:
    type: str
    speaker: str
    text: str
    section: int
    paragraph: int
    src_start: int
    src_end: int
    turn_id: int
    flags: list[str] = field(default_factory=list)


@dataclass
class QuoteState:
    speaker: str | None = None
    kind: str | None = None
    turn_id: int = 0

    @property
    def open(self) -> bool:
        return self.speaker is not None


@dataclass
class _Intro:
    verb: str
    verb_at: int
    tag_start: int
    quote_at: int
    opener: str
    speaker: str | None
    unresolved: bool


class Attributor(Protocol):
    def attribute_paragraph(
        self,
        section: int,
        paragraph: int,
        text: str,
        file_start: int,
        narrator: str,
        state: QuoteState,
    ) -> tuple[list[RawLine], QuoteState]:
        ...


class RuleAttributor:
    def __init__(self, cast: Cast):
        self.cast = cast
        self._turn = 0

    def attribute_paragraph(
        self,
        section: int,
        paragraph: int,
        text: str,
        file_start: int,
        narrator: str,
        state: QuoteState,
    ) -> tuple[list[RawLine], QuoteState]:
        lines: list[RawLine] = []
        intros = self._intros(section, text, narrator)
        if state.open and intros and intros[0].tag_start <= 1 and intros[0].speaker == narrator:
            state = QuoteState()
        cursor = 0
        if state.open:
            head_end = intros[0].tag_start if intros else len(text)
            head = _strip_leading_wrapper(text[:head_end])
            speech, trailing, closed = split_speech(head, "'")
            if speech:
                lines.extend(self._block(
                    speech, state.kind or "narration", state.speaker or narrator,
                    section, paragraph, file_start, state.turn_id, [],
                ))
            if trailing:  # text after the closing quote is still KMG text: never drop it (e.g. §1 ¶23 "'These our pupils', said they, ...")
                self._emit_narration(lines, trailing, narrator, section, paragraph, file_start)
            if closed:
                state = QuoteState()
            cursor = head_end
        for index, intro in enumerate(intros):
            if intro.tag_start > cursor:
                gap = text[cursor:intro.tag_start]
                self._emit_narration(lines, gap, narrator, section, paragraph, file_start)
            tag = text[intro.tag_start:intro.quote_at].strip().strip("\"“”").strip()
            if tag:
                lines.extend(self._block(
                    tag, "narration", narrator, section, paragraph, file_start,
                    self._next_turn(), [], src_bias=intro.tag_start,
                ))
            nxt = intros[index + 1].tag_start if index + 1 < len(intros) else len(text)
            region = text[intro.quote_at + 1:nxt]
            speech, trailing, closed = split_speech(region, intro.opener)
            speaker = intro.speaker or narrator
            flags = ["unresolved_speaker"] if intro.unresolved else []
            if speaker == narrator and index + 1 < len(intros):
                kind = "narration"
            elif speaker == narrator:
                kind = "speech" if _frame_body_is_speech(intro.verb, speech) else "narration"
            else:
                kind = "speech"
            turn = self._next_turn()
            if speech:
                lines.extend(self._block(
                    speech, kind, speaker, section, paragraph, file_start, turn, flags,
                ))
            if trailing:
                self._emit_narration(lines, trailing, narrator, section, paragraph, file_start)
            if not closed and kind == "speech":
                state = QuoteState(speaker=speaker, kind="speech", turn_id=turn)
            elif not closed and speaker == narrator:
                state = QuoteState(speaker=narrator, kind="narration", turn_id=turn)
            else:
                state = QuoteState()
            cursor = nxt
        if cursor < len(text):
            self._emit_narration(lines, text[cursor:], narrator, section, paragraph, file_start)
            if not state.open:
                state = QuoteState()
        return [line for line in lines if line.text.strip()], state

    def _emit_narration(self, lines, text, narrator, section, paragraph, file_start):
        cleaned = text.strip().strip("\"“”").strip()
        if not cleaned:
            return
        lines.extend(self._block(
            cleaned, "narration", narrator, section, paragraph, file_start, self._next_turn(), [],
        ))

    def _block(self, text, kind, speaker, section, paragraph, file_start, turn, flags, src_bias=0):
        # src_bias is unused for sentence pieces; spans cover the paragraph slice approximately.
        del src_bias
        return [RawLine(
            type=kind,
            speaker=speaker,
            text=text.strip(),
            section=section,
            paragraph=paragraph,
            src_start=file_start,
            src_end=file_start + len(text),
            turn_id=turn,
            flags=list(flags),
        )]

    def _next_turn(self) -> int:
        self._turn += 1
        return self._turn

    def _intros(self, section: int, text: str, narrator: str) -> list[_Intro]:
        found: list[_Intro] = []
        floor = 0
        prev_opener = "'"
        opened = False
        for match in INTRO_RE.finditer(text):
            verb_at = match.start("verb")
            start = _tag_start(text, verb_at, floor, prev_opener, search_closer=opened)
            sentence = text[start:verb_at]
            speaker, unresolved = resolve_speaker(self.cast, section, sentence)
            if speaker is None:
                speaker = narrator
                unresolved = True
            found.append(_Intro(
                verb=match.group("verb"),
                verb_at=verb_at,
                tag_start=start,
                quote_at=match.start("q"),
                opener=match.group("q"),
                speaker=speaker,
                unresolved=unresolved,
            ))
            floor = match.end()
            prev_opener = match.group("q")
            opened = True
        return found


class LLMAttributor:
    """Rule pass, then an optional revision hook. The hook is not called when absent."""

    def __init__(self, rules: RuleAttributor, complete: Callable[..., list[RawLine] | None] | None = None):
        self.rules = rules
        self.complete = complete

    def attribute_paragraph(
        self,
        section: int,
        paragraph: int,
        text: str,
        file_start: int,
        narrator: str,
        state: QuoteState,
    ) -> tuple[list[RawLine], QuoteState]:
        lines, state = self.rules.attribute_paragraph(
            section, paragraph, text, file_start, narrator, state,
        )
        if self.complete is None:
            return lines, state
        revised = self.complete(section, paragraph, text, lines)
        if revised is None:
            return lines, state
        for line in revised:
            line.flags = list(dict.fromkeys([*line.flags, "llm"]))
        return revised, state


def resolve_speaker(cast: Cast, section: int, sentence: str) -> tuple[str | None, bool]:
    candidates: list[tuple[int, int, str]] = []
    for lo, hi, pattern, cid in (*PHRASE_SPEAKERS, *EXTRA_PHRASES):
        if not (lo <= section <= hi):
            continue
        for match in re.finditer(pattern, sentence):
            if _genitive(sentence, match.start()):
                continue
            candidates.append((match.start(), match.end() - match.start(), cid))
    for sec, tag, cid in ((sec, tag, cid) for (sec, tag), cid in GENERIC.items()):
        if sec != section:
            continue
        window = sentence if len(tag) > 12 else sentence[-60:]
        for match in re.finditer(rf"\b{re.escape(tag)}\b", window):
            at = match.start() if len(tag) > 12 else len(sentence) - len(window) + match.start()
            if _genitive(sentence, at):
                continue
            candidates.append((at, len(tag), cid))
    for start, length, cid in cast.alias_matches(sentence):
        if _genitive(sentence, start):
            continue
        candidates.append((start, length, cid))
    if not candidates:
        return None, True
    candidates.sort(key=lambda item: (item[0], -item[1]))
    return candidates[0][2], False


def _genitive(text: str, start: int) -> bool:
    pre = text[max(0, start - 24):start]
    if _ONE_OF.search(pre):
        return False
    return _GENITIVE.search(pre) is not None


def _tag_start(text: str, verb_at: int, floor: int, opener: str, *, search_closer: bool) -> int:
    """Start of the cue that introduces this speech.

    A later intro must not reach back through the previous spoken line. If that
    line has already closed, the cue starts after the closer.
    """
    if search_closer and floor < verb_at:
        relative = _closer_index(text[floor:verb_at], opener)
        if relative is not None:
            floor = floor + relative + 1
    window = text[floor:verb_at]
    boundaries: list[int] = []
    for match in re.finditer(r"[.!?]\s+", window):
        chunk = window[: match.start() + 1]
        if _ABBR.search(chunk):
            continue
        boundaries.append(floor + match.end())
    start = boundaries[-1] if boundaries else floor
    while start < verb_at and text[start] in " \n\"“”'‘’":
        start += 1
    return start


def _closer_index(region: str, opener: str) -> int | None:
    single = set("'‘’")
    double = set('"“”')
    family = "s" if opener in single else "d"
    for index, char in enumerate(region):
        if char not in single | double or _apostrophe(region, index):
            continue
        nxt = region[index + 1] if index + 1 < len(region) else ""
        if nxt and not nxt.isspace() and nxt not in ".,;:!?)":
            continue
        same = (family == "s" and char in single) or (family == "d" and char in double)
        if same:
            return index
    return None


def _frame_body_is_speech(verb: str, body: str) -> bool:
    """A frame narrator's own quote is dialogue when they speak as 'I', and narration when they recite in the third person."""
    verb = verb.lower()
    if verb == "continued":
        return False
    if verb in {"replied", "answered", "asked"}:
        return True
    head = body.strip()
    if re.match(r"(?i)^(O king|O Bharata|O bull|O thou)\b", head):
        return False
    if re.search(r"\b(I|we|my|our)\b", body):
        return True
    if len(body.split()) > 70:
        return False
    return True


def split_speech(region: str, opener: str) -> tuple[str, str, bool]:
    single = set("'‘’")
    double = set('"“”')
    family = "s" if opener in single else "d"
    for index, char in enumerate(region):
        if char not in single | double or _apostrophe(region, index):
            continue
        nxt = region[index + 1] if index + 1 < len(region) else ""
        if nxt and not nxt.isspace() and nxt not in ".,;:!?)":
            continue
        same = (family == "s" and char in single) or (family == "d" and char in double)
        wrapper = char in double and region[index + 1:].strip() == ""
        if same or wrapper:
            speech = region[:index].strip()
            trailing = region[index + 1:].strip().strip("\"“”").strip()
            return speech, trailing, True
    return region.strip().strip("\"“”").strip(), "", False


def _apostrophe(text: str, index: int) -> bool:
    """Possessives (king's, years') are not quote closers. KMG closers follow punctuation."""
    if text[index] not in "'’":
        return False
    prev = text[index - 1] if index else ""
    nxt = text[index + 1] if index + 1 < len(text) else ""
    return prev.isalpha() and (not nxt or nxt.isspace() or nxt.isalpha())


def _strip_leading_wrapper(text: str) -> str:
    return re.sub(r"^[\"“”]+\s*", "", text)


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    buf = ""
    for part in parts:
        buf = f"{buf} {part}".strip() if buf else part
        if re.search(r"[.!?]$", buf) and not _ABBR.search(buf):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out or [text]


# narrative_layer is re-exported for callers that already import the attributor.
__all__ = [
    "EXTRA_PHRASES",
    "LLMAttributor",
    "QuoteState",
    "RawLine",
    "RuleAttributor",
    "resolve_speaker",
    "split_sentences",
    "split_speech",
]
