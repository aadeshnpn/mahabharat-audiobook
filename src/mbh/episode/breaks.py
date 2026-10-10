"""Propose natural episode endings near a target duration.

A legal break is the end of a sentence, never a dangling "X said," tag, and
never the middle of one speaker's turn (the next line must not continue the
same speech turn).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from mbh.episode.build import build_episode, build_section_lines, resolve_strip
from mbh.episode.cast import Cast, load_cast
from mbh.episode.models import ScriptLine
from mbh.episode.spec import EpisodeSpec
from mbh.episode.textload import load_section
from mbh.episode.timing import Timing, load_timing, word_count

_TAG_END = re.compile(
    r"\b(?:said|replied|answered|asked|continued|rejoined|spoke|exclaimed|spake)[,.]?$",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.!?]$")


@dataclass(frozen=True)
class BreakSuggestion:
    line_index: int
    line_id: str
    section: int | None
    paragraph: int | None
    at_s: float
    delta_s: float
    score: float
    reasons: tuple[str, ...]
    text: str

    def to_dict(self) -> dict:
        return {
            "line_index": self.line_index,
            "line_id": self.line_id,
            "section": self.section,
            "paragraph": self.paragraph,
            "at_s": round(self.at_s, 1),
            "delta_s": round(self.delta_s, 1),
            "score": round(self.score, 1),
            "reasons": list(self.reasons),
            "text": self.text,
        }


def endpoint_ok(line: ScriptLine, nxt: ScriptLine | None) -> tuple[bool, str]:
    text = line.text.rstrip().rstrip("\"“”‘’")
    if not _SENTENCE_END.search(text):
        return False, "sentence is still open"
    if _TAG_END.search(text):
        return False, "speech tag with the spoken line still ahead"
    if nxt and nxt.turn_id == line.turn_id and nxt.type == "speech" and line.type == "speech":
        return False, "same speaker's turn continues"
    return True, "complete sentence"


def suggest_breaks(lines: list[ScriptLine], target_s: float, *, limit: int = 5) -> list[BreakSuggestion]:
    found: list[BreakSuggestion] = []
    for index, line in enumerate(lines):
        nxt = lines[index + 1] if index + 1 < len(lines) else None
        ok, _why = endpoint_ok(line, nxt)
        if not ok:
            continue
        at = line.start_s + line.duration_s
        reasons = _reasons(line, nxt, at, target_s)
        score = _score(line, nxt, at, target_s)
        found.append(BreakSuggestion(
            line_index=index,
            line_id=line.id,
            section=line.section,
            paragraph=line.paragraph,
            at_s=at,
            delta_s=at - target_s,
            score=score,
            reasons=tuple(reasons),
            text=line.text,
        ))
    found.sort(key=lambda item: item.score, reverse=True)
    return found[:limit]


def suggest_in_section(
    section: int,
    target_s: float,
    *,
    narrator: str,
    start_paragraph: int = 1,
    cast: Cast | None = None,
    timing: Timing | None = None,
    limit: int = 5,
    strip_glosses: bool | None = None,
) -> list[BreakSuggestion]:
    cast = cast or load_cast()
    timing = timing or load_timing()[0]
    end = _horizon(section, start_paragraph, target_s, timing)
    lines = build_section_lines(
        section, narrator=narrator, paragraphs=(start_paragraph, end), cast=cast, timing=timing,
        strip_glosses=strip_glosses,
    )
    return suggest_breaks(lines, target_s, limit=limit)


def suggest_for_spec(spec: EpisodeSpec, *, limit: int = 5) -> dict:
    """Where the last section segment could end so the episode lands on its target."""
    last = next((seg for seg in reversed(spec.segments) if seg.kind == "section"), None)
    if last is None or last.section is None:
        return {"prefix_s": 0.0, "section_target_s": spec.target_duration_s, "suggestions": []}
    prefix_spec = _without_last_section(spec, last.id)
    timing, _engine = load_timing(spec.timing_path)
    prefix_s = 0.0
    if prefix_spec.segments:
        prefix_s = build_episode(prefix_spec).estimated_duration_s
    # The episode clock inserts a segment gap between the prefix and this section.
    seam = timing.gap_segment_s if prefix_s else 0.0
    section_target = max(5.0, spec.target_duration_s - prefix_s - seam)
    start = last.paragraphs[0] if last.paragraphs else 1
    narrator = last.narrator or spec.narrator_default
    local = suggest_in_section(
        last.section, section_target, narrator=narrator, start_paragraph=start,
        timing=timing, limit=limit, strip_glosses=resolve_strip(spec, last),
    )
    # Shift the clock so times include the cold open and bridges already counted.
    shifted = [
        BreakSuggestion(
            line_index=item.line_index,
            line_id=item.line_id,
            section=item.section,
            paragraph=item.paragraph,
            at_s=item.at_s + prefix_s + seam,
            delta_s=(item.at_s + prefix_s + seam) - spec.target_duration_s,
            score=item.score,
            reasons=item.reasons,
            text=item.text,
        )
        for item in local
    ]
    return {
        "prefix_s": round(prefix_s, 1),
        "section": last.section,
        "section_target_s": round(section_target, 1),
        "chosen_paragraph": last.paragraphs[1] if last.paragraphs else None,
        "suggestions": shifted,
    }


def _horizon(section: int, start_paragraph: int, target_s: float, timing: Timing) -> int:
    text = load_section(section)
    # Speech seconds ignore gaps; overshoot so the suggester can see the next scene.
    budget_words = target_s / 60.0 * timing.wpm * 1.45 + 80
    words = 0
    end = start_paragraph
    for para in text.paragraphs:
        if para.number < start_paragraph:
            continue
        words += word_count(para.text)
        end = para.number
        if words >= budget_words and para.number > start_paragraph:
            break
    return end


def _reasons(line: ScriptLine, nxt: ScriptLine | None, at: float, target: float) -> list[str]:
    reasons = ["sentence is complete"]
    text = line.text.rstrip()
    if text.endswith("?"):
        reasons.append("ends on a question, a small cliffhanger")
    if nxt is None or nxt.paragraph != line.paragraph:
        reasons.append("paragraph boundary")
    if line.type == "speech" and (nxt is None or nxt.type != "speech" or nxt.speaker != line.speaker):
        reasons.append("speech turn is finished")
    if line.type == "narration" and (nxt is None or nxt.type == "narration"):
        reasons.append("lands in narration, between scenes")
    gap = abs(at - target)
    if gap <= target * 0.08:
        reasons.append("close to the target duration")
    elif at > target:
        reasons.append("past the target")
    else:
        reasons.append("short of the target")
    return reasons


def _score(line: ScriptLine, nxt: ScriptLine | None, at: float, target: float) -> float:
    gap = abs(at - target)
    score = 1000.0 - gap
    text = line.text.rstrip()
    if text.endswith("?"):
        score += 30
    if nxt is None or nxt.paragraph != line.paragraph:
        score += 25
    if line.type == "speech" and text.endswith("?"):
        score += 15
    if line.type == "speech" and nxt and nxt.type == "narration":
        score += 12
    if at > target * 1.25:
        score -= (at - target)
    return score


def _without_last_section(spec: EpisodeSpec, drop_id: str) -> EpisodeSpec:
    segments = [seg for seg in spec.segments if seg.id != drop_id]
    return replace(spec, segments=segments)
