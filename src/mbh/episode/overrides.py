"""Manual line edits that survive a rebuild.

An override matches one line by section, paragraph, and a unique substring of
the KMG text. ``apply_all`` is required when the substring hits more than one line.

Two structural edits run first, in file order, before the field edits:
- ``"merge_next": true`` joins the matched line with the following line (e.g. a sentence the
  splitter broke at "Om!").
- ``"split": [{"text": ..., "speaker": ..., ...}, ...]`` replaces the matched line with several
  lines (e.g. a quotation nested inside narration). The parts must re-join to the original
  KMG text (quote marks and whitespace ignored), so the source wording cannot drift; each part may
  carry the usual field edits.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

from collections.abc import Callable

from mbh.episode.cast import Cast, narrative_layer
from mbh.episode.emotion import check_emotion
from mbh.episode.models import PACES, ScriptLine

Respeak = Callable[[ScriptLine, bool], str]


def load_overrides(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("overrides", data if isinstance(data, list) else [])
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected a list under 'overrides'")
    return rows


def apply_overrides(
    lines: list[ScriptLine],
    overrides: list[dict],
    cast: Cast,
    respeak: Respeak | None = None,
) -> list[str]:
    warnings: list[str] = []
    field_rows = []
    for row in overrides:
        if "split" in row or row.get("merge_next"):
            warnings.extend(_structural(lines, row, cast, respeak))
            rest = {k: v for k, v in row.items() if k not in ("split", "merge_next")}
            if row.get("merge_next") and set(rest) - {"section", "paragraph", "segment_id", "contains", "match"}:
                field_rows.append(rest)  # field edits on a merged line apply to the merged line
        else:
            field_rows.append(row)
    for row in field_rows:
        matches = [line for line in lines if _matches(line, row)]
        label = row.get("contains") or row.get("match") or "?"
        if not matches:
            warnings.append(f"override did not match any line: {label!r}")
            continue
        if len(matches) > 1 and not row.get("apply_all"):
            warnings.append(f"override matched {len(matches)} lines and was not applied: {label!r}")
            continue
        for line in matches:
            _apply_one(line, row, cast, respeak)
    return warnings


def _norm(text: str) -> str:
    return re.sub(r"[\s\"'\u201c\u201d\u2018\u2019]", "", text)


def parts_rejoin(original: str, parts: list[str]) -> bool:
    """True when split parts reproduce the KMG line (quotes and whitespace ignored)."""
    return _norm("".join(parts)) == _norm(original)


def _structural(lines: list[ScriptLine], row: dict, cast: Cast, respeak: Respeak | None) -> list[str]:
    label = row.get("contains") or row.get("match") or "?"
    idx = [i for i, line in enumerate(lines) if _matches(line, row)]
    if len(idx) != 1:
        return [f"structural override matched {len(idx)} lines and was not applied: {label!r}"]
    i = idx[0]
    line = lines[i]
    if row.get("merge_next"):
        if i + 1 >= len(lines):
            return [f"merge_next on the last line: {label!r}"]
        nxt = lines[i + 1]
        line.text = f"{line.text} {nxt.text}"
        line.tts_text = f"{line.tts_text} {nxt.tts_text}"
        line.flags = sorted(set(line.flags) | set(nxt.flags) | {"override", "merged"})
        line.attribution = "override"
        del lines[i + 1]
        return []
    parts = row["split"]
    if _norm("".join(p["text"] for p in parts)) != _norm(line.text):
        return [f"split parts do not re-join to the KMG text, not applied: {label!r}"]
    strip = "gloss_stripped" in line.flags or bool(row.get("strip_glosses", True))
    new = []
    for k, part in enumerate(parts):
        piece = dataclasses.replace(line, text=part["text"].strip(), flags=[f for f in line.flags if f != "gloss_stripped"])
        piece.turn_id = f"{line.turn_id}.{k}"
        piece.tts_text = respeak(piece, strip) if respeak else piece.text
        _apply_one(piece, {key: v for key, v in part.items() if key != "text"}, cast, respeak)
        if "split" not in piece.flags:
            piece.flags.append("split")
        new.append(piece)
    lines[i:i + 1] = new
    return []


def _matches(line: ScriptLine, row: dict) -> bool:
    if "section" in row and line.section != row["section"]:
        return False
    if "paragraph" in row and line.paragraph != row["paragraph"]:
        return False
    if "segment_id" in row and line.segment_id != row["segment_id"]:
        return False
    if "type" in row and line.type != row["type"]:
        return False
    needle = row.get("contains") or row.get("match")
    if needle and needle not in line.text:
        return False
    return needle is not None or "section" in row


def _apply_one(line: ScriptLine, row: dict, cast: Cast, respeak: Respeak | None) -> None:
    if "speaker" in row:
        line.speaker = row["speaker"]
        line.voice_id = cast.voice_id(line.speaker)
        line.layer = narrative_layer(line.speaker)
    if "emotion" in row:
        line.emotion = check_emotion(row["emotion"])
    if "pace" in row:
        if row["pace"] not in PACES:
            raise ValueError(f"unknown pace {row['pace']!r}")
        line.pace = row["pace"]
    if "intensity" in row:
        line.intensity = float(row["intensity"])
    if "direction" in row:
        line.direction = row["direction"]
    if "fx" in row:
        line.fx = row["fx"]
    if "music" in row:
        line.music = row["music"]
    if "take" in row:
        line.take = int(row["take"])
    if "strip_glosses" in row and respeak is not None:
        line.tts_text = respeak(line, bool(row["strip_glosses"]))
    if "tts_text" in row:
        line.tts_text = row["tts_text"]
        line.flags = [flag for flag in line.flags if flag != "gloss_stripped"]
    if "addressee" in row:
        line.addressee = row["addressee"]
    if "type" in row:
        line.type = row["type"]
    for flag in row.get("flags_add") or []:
        if flag not in line.flags:
            line.flags.append(flag)
    line.attribution = "override"
    if "override" not in line.flags:
        line.flags.append("override")
