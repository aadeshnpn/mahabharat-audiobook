"""Manual line edits that survive a rebuild.

An override matches one line by section, paragraph, and a unique substring of
the KMG text. ``apply_all`` is required when the substring hits more than one line.
"""

from __future__ import annotations

import json
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
    for row in overrides:
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
