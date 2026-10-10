"""Human-readable episode script for review."""

from __future__ import annotations

from mbh.episode.cast import Cast, load_cast
from mbh.episode.models import EpisodeScript, ScriptLine
from mbh.episode.timing import format_duration


def render_markdown(script: EpisodeScript, cast: Cast | None = None) -> str:
    cast = cast or load_cast()
    lines: list[str] = []
    lines.append(f"# {script.title}")
    lines.append("")
    clock = format_duration(script.estimated_duration_s)
    target = format_duration(script.target_duration_s)
    wpm = script.timing.get("wpm")
    lines.append(f"Estimated duration **{clock}** ({script.estimated_duration_s:.0f} s) at {wpm} words per minute. Target {target}.")
    lines.append("")
    lines.append("Speech rate is the VoxCPM2 prototype fit (Book 1 §100 excerpt: 250 words, 99 s including assemble gaps). "
                 "Pauses: 0.25 s inside a turn, 0.50 s on a speaker change, 1.50 s at a paragraph or segment boundary.")
    lines.append("")
    if script.ending.get("reason"):
        para = script.ending.get("paragraph")
        section = script.ending.get("section")
        lines.append(f"**Where it ends:** §{section} ¶{para}. {script.ending['reason']}")
        lines.append("")
    if script.warnings:
        lines.append("## Build warnings")
        lines.append("")
        for warning in script.warnings:
            lines.append(f"- {warning}")
        lines.append("")
    current = None
    for line in script.lines:
        if line.segment_id != current:
            current = line.segment_id
            meta = next((seg for seg in script.segments if seg["id"] == current), {})
            lines.append(f"## {_heading(meta, line)}")
            lines.append("")
            if meta.get("note"):
                lines.append(meta["note"])
                lines.append("")
            if meta.get("non_kmg"):
                lines.append("*This bridge is not in the KMG text.*")
                lines.append("")
            if meta.get("excerpt"):
                lines.append("*Excerpt: the wording inside this span is unabridged KMG. The span itself is a selection.*")
                lines.append("")
            if meta.get("abridged"):
                lines.append("*Abridged. The cut is marked on the lines below.*")
                lines.append("")
        lines.append(_line_block(line, cast))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _heading(meta: dict, line: ScriptLine) -> str:
    label = meta.get("label") or line.segment_id
    if line.section:
        span = ""
        paras = meta.get("paragraphs")
        if paras:
            span = f" ¶{paras[0]}–{paras[1]}"
        return f"{label} (§{line.section}{span})"
    return label


def _line_block(line: ScriptLine, cast: Cast) -> str:
    stamp = _stamp(line.start_s)
    name = cast.display(line.speaker)
    flags = []
    if line.non_kmg:
        flags.append("non-KMG")
    if line.abridged:
        flags.append("abridged")
    if "override" in line.flags:
        flags.append("override")
    if "unresolved_speaker" in line.flags:
        flags.append("unresolved speaker")
    mark = f" · {', '.join(flags)}" if flags else ""
    head = f"**{stamp} · {name}** · {line.type} · {line.emotion} · {line.pace}{mark}"
    body = f"> {line.text}"
    if line.tts_text and line.tts_text != line.text:
        return f"{head}\n\n{body}\n\n*TTS:* {line.tts_text}"
    return f"{head}\n\n{body}"


def _stamp(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"
