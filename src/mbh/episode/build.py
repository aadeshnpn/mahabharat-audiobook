"""Build a line-level episode script from a spec."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from mbh.episode.attribute import LLMAttributor, QuoteState, RawLine, RuleAttributor, split_sentences
from mbh.episode.cast import Cast, load_cast, narrative_layer
from mbh.episode.emotion import check_emotion, infer
from mbh.episode.gloss import glosses_removed, strip_glosses
from mbh.episode.lexicon import apply_lexicon, load_lexicon
from mbh.episode.models import EpisodeScript, LineType, ScriptLine, assert_never
from mbh.episode.overrides import apply_overrides, load_overrides
from mbh.episode.spec import EpisodeSpec, SegmentSpec
from mbh.episode.textload import Paragraph, SectionText, load_section
from mbh.episode.timing import Timing, apply_timing, global_strip_glosses, load_timing
from mbh.text.krishna import speakable

_SHORT_TAG = re.compile(
    r"^(?:And |Then |Thereupon )?[A-Z][\w' .-]{0,40}\s"
    r"(?:said|replied|answered|asked|continued|rejoined|spoke|exclaimed|spake)[,.]?$",
    re.IGNORECASE,
)


def build_episode(
    spec: EpisodeSpec,
    cast: Cast | None = None,
    attributor: LLMAttributor | RuleAttributor | None = None,
) -> EpisodeScript:
    cast = cast or load_cast()
    timing, _engine = load_timing(spec.timing_path)
    lexemes = load_lexicon(spec.lexicon_path)
    rules = RuleAttributor(cast)
    attributer = attributor or rules
    lines: list[ScriptLine] = []
    warnings: list[str] = []
    segment_meta: list[dict] = []
    for segment in spec.segments:
        before = len(lines)
        made, warn = _segment_lines(spec, segment, cast, attributer, lexemes)
        warnings.extend(warn)
        lines.extend(made)
        segment_meta.append({
            "id": segment.id,
            "kind": segment.kind,
            "label": segment.label,
            "section": segment.section,
            "paragraphs": list(segment.paragraphs) if segment.paragraphs else None,
            "excerpt": segment.excerpt,
            "abridged": segment.abridged,
            "non_kmg": segment.non_kmg,
            "note": segment.note,
            "line_count": len(lines) - before,
        })
    if spec.speech_tags == "drop":
        lines = [line for line in lines if not _drop_tag(line)]

    def respeak(line: ScriptLine, strip: bool) -> str:
        tts, removed = _tts(line.text, line.section, lexemes, strip)
        _set_gloss_flag(line, removed)
        return tts

    warnings.extend(apply_overrides(lines, load_overrides(spec.overrides_path), cast, respeak))
    # an override that assigned a speaker resolves the attribution warning for that text
    fixed = [line.text for line in lines if line.attribution == "override" and line.speaker != spec.narrator_default]
    warnings = [w for w in warnings if not ("speaker unresolved" in w and any(t.startswith(w.rsplit(": ", 1)[-1].strip()[:40]) for t in fixed))]
    _renumber(spec.id, lines)
    total = apply_timing(lines, timing)
    ending = _ending(spec, lines)
    return EpisodeScript(
        episode_id=spec.id,
        title=spec.title,
        book=spec.book,
        target_duration_s=spec.target_duration_s,
        estimated_duration_s=total,
        timing=timing.to_dict(),
        lines=lines,
        warnings=warnings,
        ending=ending,
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        segments=segment_meta,
    )


def build_section_lines(
    section: int,
    *,
    narrator: str,
    paragraphs: tuple[int, int] | None = None,
    cast: Cast | None = None,
    timing: Timing | None = None,
    strip_glosses: bool | None = None,
) -> list[ScriptLine]:
    """Attribute a section (or a paragraph span) without an episode spec. Used by the break suggester."""
    cast = cast or load_cast()
    timing = timing or load_timing()[0]
    lexemes = load_lexicon()
    strip = global_strip_glosses() if strip_glosses is None else strip_glosses
    section_text = load_section(section)
    chosen = _select_paragraphs(section_text, paragraphs)
    raws, _warnings = _attribute_section(section_text, chosen, narrator, RuleAttributor(cast))
    lines = [
        _finish_raw(raw, "section", False, False, False, cast, lexemes, section, strip)
        for raw in _explode(raws)
    ]
    apply_timing(lines, timing)
    return lines


def resolve_strip(spec: EpisodeSpec, segment: SegmentSpec | None = None) -> bool:
    """Episode value wins over the global default. A segment wins over the episode."""
    if segment is not None and segment.strip_glosses is not None:
        return segment.strip_glosses
    if spec.strip_glosses is not None:
        return spec.strip_glosses
    return global_strip_glosses(spec.timing_path)


def _segment_lines(spec, segment, cast, attributer, lexemes):
    kind = segment.kind
    strip = resolve_strip(spec, segment)
    if kind == "bridge":
        return _bridge_lines(segment, cast, lexemes, strip), []
    if kind == "section":
        narrator = segment.narrator or spec.narrator_default
        section_text = load_section(segment.section)
        chosen = _select_paragraphs(section_text, segment.paragraphs)
        raws, warnings = _attribute_section(section_text, chosen, narrator, attributer)
        lines = [
            _finish_raw(
                raw, segment.id, segment.excerpt, segment.abridged, False,
                cast, lexemes, segment.section, strip,
            )
            for raw in _explode(raws)
        ]
        return lines, warnings
    assert_never(kind)


def _bridge_lines(segment: SegmentSpec, cast: Cast, lexemes, strip: bool) -> list[ScriptLine]:
    speaker = segment.speaker or "sauti"
    emotion, pace, intensity, direction = infer(segment.text, "bridge", speaker)
    if segment.emotion:
        emotion = check_emotion(segment.emotion)
    if segment.pace:
        pace = segment.pace
    lines = []
    for piece in split_sentences(segment.text):
        tts, removed = _tts(piece, None, lexemes, strip)
        flags = ["non_kmg"]
        if removed:
            flags.append("gloss_stripped")
        lines.append(ScriptLine(
            id="",
            segment_id=segment.id,
            type="bridge",
            speaker=speaker,
            voice_id=cast.voice_id(speaker),
            layer=narrative_layer(speaker),
            emotion=emotion,
            pace=pace,
            intensity=intensity,
            text=piece,
            tts_text=tts,
            turn_id=f"{segment.id}-bridge",
            non_kmg=True,
            direction=direction,
            flags=flags,
        ))
    return lines


def _attribute_section(section_text: SectionText, paragraphs: list[Paragraph], narrator: str, attributer):
    state = QuoteState()
    raws: list[RawLine] = []
    warnings: list[str] = []
    for para in paragraphs:
        lines, state = attributer.attribute_paragraph(
            section_text.section, para.number, para.text, para.start, narrator, state,
        )
        raws.extend(lines)
        for line in lines:
            if "unresolved_speaker" in line.flags:
                warnings.append(
                    f"§{section_text.section} ¶{para.number}: speaker unresolved, kept as {line.speaker}: {line.text[:80]}"
                )
    return raws, warnings


def _explode(raws: list[RawLine]) -> list[RawLine]:
    out: list[RawLine] = []
    for raw in raws:
        parts = split_sentences(raw.text)
        if len(parts) <= 1 or _norm(" ".join(parts)) != _norm(raw.text):
            out.append(raw)
            continue
        for part in parts:
            out.append(RawLine(
                type=raw.type, speaker=raw.speaker, text=part, section=raw.section,
                paragraph=raw.paragraph, src_start=raw.src_start, src_end=raw.src_end,
                turn_id=raw.turn_id, flags=list(raw.flags),
            ))
    return out


def _finish_raw(raw: RawLine, segment_id: str, excerpt: bool, abridged: bool, non_kmg: bool,
                cast: Cast, lexemes, section: int, strip: bool) -> ScriptLine:
    kind: LineType = raw.type if raw.type in ("narration", "speech", "bridge") else "narration"
    emotion, pace, intensity, direction = infer(raw.text, kind, raw.speaker)
    tts, removed = _tts(raw.text, section, lexemes, strip)
    flags = list(raw.flags)
    if removed and "gloss_stripped" not in flags:
        flags.append("gloss_stripped")
    if excerpt and "excerpt" not in flags:
        flags.append("excerpt")
    if abridged and "abridged" not in flags:
        flags.append("abridged")
    fx = "celestial" if raw.speaker == "devas_chorus" else None
    attribution = "llm" if "llm" in flags else "rule"
    return ScriptLine(
        id="",
        segment_id=segment_id,
        type=kind,
        speaker=raw.speaker,
        voice_id=cast.voice_id(raw.speaker),
        layer=narrative_layer(raw.speaker),
        emotion=emotion,
        pace=pace,
        intensity=intensity,
        text=raw.text,
        tts_text=tts,
        turn_id=f"t{raw.turn_id}",
        non_kmg=non_kmg,
        abridged=abridged,
        excerpt=excerpt,
        attribution=attribution,
        section=raw.section,
        paragraph=raw.paragraph,
        src_span=(raw.src_start, raw.src_end),
        direction=direction,
        fx=fx,
        flags=flags,
    )


def _tts(text: str, section: int | None, lexemes, strip: bool) -> tuple[str, bool]:
    resolved = speakable(section, text) if section else text
    spoken = strip_glosses(resolved) if strip else resolved
    return apply_lexicon(spoken, lexemes), glosses_removed(resolved, spoken)


def _set_gloss_flag(line: ScriptLine, removed: bool) -> None:
    if removed:
        if "gloss_stripped" not in line.flags:
            line.flags.append("gloss_stripped")
        return
    line.flags = [flag for flag in line.flags if flag != "gloss_stripped"]


def _select_paragraphs(section_text: SectionText, span: tuple[int, int] | None) -> list[Paragraph]:
    if span is None:
        return list(section_text.paragraphs)
    start, end = span
    chosen = [para for para in section_text.paragraphs if start <= para.number <= end]
    if not chosen:
        raise ValueError(f"§{section_text.section} has no paragraphs in {start}–{end}")
    return chosen


def _drop_tag(line: ScriptLine) -> bool:
    return line.type == "narration" and len(line.text.split()) <= 8 and _SHORT_TAG.match(line.text.strip()) is not None


def _renumber(episode_id: str, lines: list[ScriptLine]) -> None:
    for index, line in enumerate(lines, start=1):
        line.id = f"{episode_id}-{index:04d}"


def _ending(spec: EpisodeSpec, lines: list[ScriptLine]) -> dict:
    last = lines[-1] if lines else None
    return {
        "section": last.section if last else None,
        "paragraph": last.paragraph if last else None,
        "line_id": last.id if last else None,
        "reason": spec.end_reason,
    }


def _norm(text: str) -> str:
    text = re.sub(r"[\"“”‘’]", "", text)
    return re.sub(r"\s+", " ", text).strip()
