"""Create, estimate, and edit episodes by calling the episode library.

Line edits are written to the overrides file and a rebuild reapplies them, which is
the same path ``mbh episode build`` uses. The YAML is only rewritten when the span,
title, or music settings change.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import yaml

from mbh.episode.breaks import suggest_for_spec, suggest_in_section
from mbh.episode.paths import repo_root
from mbh.episode.build import build_episode
from mbh.episode.cast import load_cast
from mbh.episode.emotion import check_emotion
from mbh.episode.markdown import render_markdown
from mbh.episode.models import PACES, EpisodeScript
from mbh.episode.music import cue_sheet, load_music_config, resolve_cues
from mbh.episode.overrides import load_overrides, parts_rejoin
from mbh.episode.spec import EpisodeSpec, load_spec
from mbh.episode.textload import load_section
from mbh.episode.timing import format_duration
from mbh.studio.paths import (
    build_dir,
    display_path,
    episode_yaml,
    episodes_dir,
    lexicon_file,
    manifest_path,
    overrides_path,
    script_json,
    script_markdown,
)

_ID = re.compile(r"[a-z][a-z0-9_]{0,40}\Z")


class StudioError(ValueError):
    pass


def list_episodes() -> list[dict]:
    found = []
    for path in sorted(episodes_dir().glob("*.yaml")):
        try:
            spec = load_spec(path)
        except Exception as exc:
            found.append({"id": path.stem, "error": str(exc), "path": display_path(path)})
            continue
        found.append(_card(spec))
    return found


def get_episode(episode_id: str) -> dict:
    spec = _spec(episode_id)
    card = _card(spec)
    card["spec"] = _spec_dict(spec)
    card["overrides"] = load_overrides(spec.overrides_path)
    return card


def create_episode(body: dict) -> dict:
    episode_id = _check_id(str(body.get("id") or ""))
    if episode_yaml(episode_id).exists():
        raise StudioError(f"episode {episode_id!r} already exists")
    _validate_segments(body.get("segments") or [])
    overrides = overrides_path(episode_id)
    if not overrides.exists():
        _write_overrides(overrides, [])
    _write_yaml(episode_id, body)
    return get_episode(episode_id)


def update_episode(episode_id: str, body: dict) -> dict:
    _spec(episode_id)
    if "segments" in body:
        _validate_segments(body["segments"])
    current = _spec_dict(_spec(episode_id))
    merged = {**current, **{k: v for k, v in body.items() if k != "id"}}
    merged["id"] = episode_id
    _write_yaml(episode_id, merged)
    return get_episode(episode_id)


def delete_episode(episode_id: str) -> dict:
    yaml_path = episode_yaml(episode_id)
    if not yaml_path.exists():
        raise FileNotFoundError(episode_id)
    for path in (
        yaml_path,
        overrides_path(episode_id),
        script_json(episode_id),
        script_markdown(episode_id),
        manifest_path(episode_id),
    ):
        if path.exists():
            path.unlink()
    playback = build_dir() / "studio" / episode_id
    if playback.exists():
        for child in playback.iterdir():
            if child.is_file():
                child.unlink()
    return {"deleted": episode_id}


def estimate(body: dict) -> dict:
    """Duration of a draft spec. Nothing is saved."""
    _validate_segments(body.get("segments") or [])
    spec = _load_draft(body)
    return _summary(build_episode(spec))


def breaks(body: dict, *, limit: int = 5) -> dict:
    """Legal endings. A draft uses the episode's own prefix; a bare section uses the clock from ``start_paragraph``."""
    if body.get("segments"):
        _validate_segments(body["segments"])
        spec = _load_draft(body)
        report = suggest_for_spec(spec, limit=limit)
        return {
            "prefix_s": report.get("prefix_s"),
            "section": report.get("section"),
            "section_target_s": report.get("section_target_s"),
            "chosen_paragraph": report.get("chosen_paragraph"),
            "suggestions": [item.to_dict() for item in report["suggestions"]],
        }
    section = body.get("section")
    target = body.get("target_seconds")
    if section is None or target is None:
        raise StudioError("pass segments, or section and target_seconds")
    suggestions = suggest_in_section(
        int(section),
        float(target),
        narrator=str(body.get("narrator") or "sauti"),
        start_paragraph=int(body.get("start_paragraph") or 1),
        limit=limit,
        strip_glosses=body.get("strip_glosses", True),
    )
    return {
        "section": int(section),
        "target_seconds": float(target),
        "suggestions": [item.to_dict() for item in suggestions],
    }


def build_saved(episode_id: str) -> dict:
    spec = _spec(episode_id)
    script = build_episode(spec)
    _write_script(script)
    return script_view(episode_id, script=script, spec=spec)


def script_view(episode_id: str, *, script: EpisodeScript | None = None, spec: EpisodeSpec | None = None) -> dict:
    spec = spec or _spec(episode_id)
    if script is None:
        path = script_json(episode_id)
        if path.exists():
            script = _read_script(path)
        else:
            script = build_episode(spec)
            _write_script(script)
    cues = _cues(spec, script)
    audio = _audio_index(episode_id)
    lines = []
    for line in script.lines:
        row = line.to_dict()
        cue = cues.get(line.id) or {}
        row["cue"] = cue.get("cue")
        row["cue_source"] = cue.get("source")
        row["cue_intensity"] = cue.get("intensity")
        row["cue_kind"] = cue.get("kind")
        clip = audio.get(line.id)
        row["audio_status"] = clip.get("status") if clip else None
        row["has_audio"] = bool(clip and clip.get("path") and clip.get("status") not in {"missing_voice", "would_render"})
        lines.append(row)
    summary = _summary(script)
    summary["lines"] = lines
    summary["music"] = bool(spec.music)
    summary["music_preset"] = spec.music_preset
    return summary


def edit_line(episode_id: str, line_id: str, fields: dict) -> dict:
    spec = _spec(episode_id)
    script = build_episode(spec)
    line = _line(script, line_id)
    clean = _clean_fields(fields)
    rows = load_overrides(spec.overrides_path)
    target = _field_row_index(rows, line)
    if not clean and target is None:
        raise StudioError("no fields to change")
    if target is None:
        row = _identity(line, script)
        rows.append(row)
        target = len(rows) - 1
    row = rows[target]
    for key, value in clean.items():
        if value is None:
            row.pop(key, None)
        else:
            row[key] = value
    _write_overrides(spec.overrides_path, rows)
    return build_saved(episode_id)


def split_line(episode_id: str, line_id: str, parts: list[dict]) -> dict:
    spec = _spec(episode_id)
    script = build_episode(spec)
    line = _line(script, line_id)
    texts = [str(part.get("text") or "").strip() for part in parts]
    if len(texts) < 2 or not all(texts):
        raise StudioError("a split needs at least two non-empty parts")
    if not parts_rejoin(line.text, texts):
        raise StudioError("split parts do not re-join to the KMG text")
    built = []
    for part, text in zip(parts, texts):
        piece = {"text": text}
        for key in ("speaker", "type", "emotion", "pace", "direction", "tts_text"):
            if part.get(key) not in (None, ""):
                piece[key] = part[key]
        if "emotion" in piece:
            piece["emotion"] = check_emotion(piece["emotion"])
        if "pace" in piece and piece["pace"] not in PACES:
            raise StudioError(f"unknown pace {piece['pace']!r}")
        if "speaker" in piece:
            _check_speaker(piece["speaker"])
        built.append(piece)
    rows = [row for row in load_overrides(spec.overrides_path) if not _structural_hit(row, line)]
    rows.append({**_identity(line, script), "split": built})
    _write_overrides(spec.overrides_path, rows)
    return build_saved(episode_id)


def merge_line(episode_id: str, line_id: str) -> dict:
    spec = _spec(episode_id)
    script = build_episode(spec)
    line = _line(script, line_id)
    index = script.lines.index(line)
    if index + 1 >= len(script.lines):
        raise StudioError("the last line has nothing to merge with")
    rows = [row for row in load_overrides(spec.overrides_path) if not _structural_hit(row, line)]
    rows.append({**_identity(line, script), "merge_next": True})
    _write_overrides(spec.overrides_path, rows)
    return build_saved(episode_id)


def clear_line_override(episode_id: str, line_id: str) -> dict:
    spec = _spec(episode_id)
    script = build_episode(spec)
    line = _line(script, line_id)
    rows = [row for row in load_overrides(spec.overrides_path) if not _row_targets(row, line)]
    _write_overrides(spec.overrides_path, rows)
    return build_saved(episode_id)


def cast_options() -> list[dict]:
    cast = load_cast()
    return [
        {"id": char.id, "name": char.name, "voice_id": char.voice_id, "kind": char.kind}
        for char in sorted(cast.by_id.values(), key=lambda item: item.name.casefold())
    ]


def _card(spec: EpisodeSpec) -> dict:
    script_path = script_json(spec.id)
    estimated = None
    line_count = None
    non_kmg = None
    if script_path.exists():
        data = json.loads(script_path.read_text(encoding="utf-8"))
        estimated = data.get("estimated_duration_s")
        line_count = len(data.get("lines") or [])
        non_kmg = sum(1 for line in data.get("lines") or [] if line.get("non_kmg"))
    playback = build_dir() / "studio" / spec.id
    return {
        "id": spec.id,
        "title": spec.title,
        "book": spec.book,
        "target_duration_s": spec.target_duration_s,
        "estimated_duration_s": estimated,
        "duration_label": format_duration(estimated) if estimated else None,
        "line_count": line_count,
        "non_kmg_lines": non_kmg,
        "music": bool(spec.music),
        "music_preset": spec.music_preset,
        "has_script": script_path.exists(),
        "has_wav": (playback / "episode.wav").exists(),
        "has_mp3": (playback / "episode.mp3").exists(),
        "path": display_path(spec.path),
    }


def _spec_dict(spec: EpisodeSpec) -> dict:
    return {
        "id": spec.id,
        "title": spec.title,
        "book": spec.book,
        "target_duration_s": spec.target_duration_s,
        "speech_tags": spec.speech_tags,
        "narrator_default": spec.narrator_default,
        "strip_glosses": True if spec.strip_glosses is None else spec.strip_glosses,
        "music": True if spec.music is None else (spec.music if isinstance(spec.music, bool) else display_path(spec.music)),
        "music_preset": spec.music_preset,
        "music_rules": list(spec.music_rules),
        "summary": spec.summary,
        "end_reason": spec.end_reason,
        "notes": list(spec.notes),
        "segments": [_segment_dict(seg) for seg in spec.segments],
    }


def _segment_dict(seg) -> dict:
    payload = {
        "id": seg.id,
        "kind": seg.kind,
        "label": seg.label,
        "note": seg.note,
        "section": seg.section,
        "paragraphs": list(seg.paragraphs) if seg.paragraphs else None,
        "narrator": seg.narrator,
        "excerpt": seg.excerpt,
        "speaker": seg.speaker,
        "emotion": seg.emotion,
        "pace": seg.pace,
        "text": seg.text,
        "non_kmg": seg.non_kmg,
    }
    return {key: value for key, value in payload.items() if value not in (None, "", False, [])}


def _summary(script: EpisodeScript) -> dict:
    grouped: dict[str, list] = {}
    for line in script.lines:
        grouped.setdefault(line.segment_id, []).append(line)
    segments = []
    for seg in script.segments:
        lines = grouped.get(seg["id"], [])
        seconds = 0.0
        if lines:
            seconds = (lines[-1].start_s + lines[-1].duration_s) - lines[0].start_s
        segments.append({**seg, "seconds": round(seconds, 1)})
    return {
        "episode_id": script.episode_id,
        "title": script.title,
        "book": script.book,
        "target_duration_s": script.target_duration_s,
        "estimated_duration_s": round(script.estimated_duration_s, 3),
        "duration_label": format_duration(script.estimated_duration_s),
        "line_count": len(script.lines),
        "non_kmg_lines": sum(1 for line in script.lines if line.non_kmg),
        "warnings": list(script.warnings),
        "ending": script.ending,
        "segments": segments,
    }


def _write_yaml(episode_id: str, body: dict) -> Path:
    doc = {
        "id": episode_id,
        "title": str(body.get("title") or episode_id),
        "book": int(body.get("book") or 1),
        "target_duration_s": float(body.get("target_duration_s") or 1050),
        "speech_tags": body.get("speech_tags") or "keep",
        "narrator_default": body.get("narrator_default") or "sauti",
        "timing": "configs/duration.yaml",
        "lexicon": display_path(lexicon_file()),
        "overrides": display_path(overrides_path(episode_id)),
        "strip_glosses": bool(body.get("strip_glosses", True)),
        "music": _music_value(body.get("music", True)),
        "segments": [_segment_payload(seg, index) for index, seg in enumerate(body.get("segments") or [])],
    }
    if body.get("music_preset"):
        doc["music_preset"] = str(body["music_preset"])
    if body.get("music_rules"):
        doc["music_rules"] = list(body["music_rules"])
    if str(body.get("summary") or "").strip():
        doc["summary"] = str(body["summary"]).strip()
    if str(body.get("end_reason") or "").strip():
        doc["end_reason"] = str(body["end_reason"]).strip()
    if body.get("notes"):
        doc["notes"] = [str(item) for item in body["notes"]]
    if doc["speech_tags"] not in ("keep", "drop"):
        raise StudioError("speech_tags must be keep or drop")
    _check_preset(doc.get("music_preset"))
    path = episode_yaml(episode_id)
    text = (
        "# Episode spec. Line edits live in the overrides file and survive rebuilds.\n"
        + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)
    )
    path.write_text(text, encoding="utf-8")
    return path


def _segment_payload(seg: dict, index: int) -> dict:
    kind = seg.get("kind")
    payload: dict = {"id": str(seg.get("id") or f"seg{index + 1}"), "kind": kind}
    if seg.get("label"):
        payload["label"] = str(seg["label"])
    if seg.get("note"):
        payload["note"] = str(seg["note"])
    if kind == "section":
        payload["section"] = int(seg["section"])
        paragraphs = seg.get("paragraphs") or [1, 1]
        payload["paragraphs"] = [int(paragraphs[0]), int(paragraphs[1])]
        payload["narrator"] = str(seg.get("narrator") or "sauti")
        if seg.get("excerpt"):
            payload["excerpt"] = True
    elif kind == "bridge":
        payload["speaker"] = str(seg.get("speaker") or "sauti")
        payload["text"] = str(seg.get("text") or "").strip()
        payload["non_kmg"] = True
        if seg.get("emotion"):
            payload["emotion"] = check_emotion(str(seg["emotion"]))
        if seg.get("pace"):
            payload["pace"] = str(seg["pace"])
    return payload


def _validate_segments(segments: list) -> None:
    if not segments:
        raise StudioError("an episode needs at least one segment")
    for seg in segments:
        kind = seg.get("kind")
        if kind == "section":
            if not seg.get("section"):
                raise StudioError("a section segment needs a section number")
            text = load_section(int(seg["section"]))
            count = len(text.paragraphs)
            paragraphs = seg.get("paragraphs") or [1, count]
            if len(paragraphs) != 2:
                raise StudioError("paragraphs must be [start, end]")
            start, end = int(paragraphs[0]), int(paragraphs[1])
            if start < 1 or end < start or end > count:
                raise StudioError(f"§{seg['section']} has {count} paragraphs; {start}–{end} is outside that")
        elif kind == "bridge":
            if not str(seg.get("text") or "").strip():
                raise StudioError("a bridge needs text")
            if not str(seg.get("speaker") or "").strip():
                raise StudioError("a bridge needs a speaker")
            if seg.get("non_kmg") is False:
                raise StudioError("bridge text is not in KMG; non_kmg must stay true")
            _check_speaker(str(seg.get("speaker")))
        else:
            raise StudioError("segment kind must be section or bridge")


def _load_draft(body: dict) -> EpisodeSpec:
    episode_id = _check_id(str(body.get("id") or "draft"))
    folder = build_dir() / "studio" / "drafts"
    folder.mkdir(parents=True, exist_ok=True)
    empty = folder / "empty-overrides.json"
    if not empty.exists():
        empty.write_text('{"overrides": []}\n', encoding="utf-8")
    # A saved episode's overrides apply when the draft id matches one on disk.
    overrides = overrides_path(episode_id)
    handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", prefix=f"{episode_id}-", dir=folder, delete=False, encoding="utf-8")
    handle.close()
    path = Path(handle.name)
    draft = dict(body)
    draft["id"] = episode_id
    saved = _write_yaml_to(path, draft, overrides if overrides.exists() else empty)
    del saved
    try:
        return load_spec(path)
    finally:
        path.unlink(missing_ok=True)


def _write_yaml_to(path: Path, body: dict, overrides: Path) -> Path:
    """Write a spec whose lexicon and overrides paths are absolute, for a temp draft."""
    episode_id = body["id"]
    doc = {
        "id": episode_id,
        "title": str(body.get("title") or episode_id),
        "book": int(body.get("book") or 1),
        "target_duration_s": float(body.get("target_duration_s") or 1050),
        "speech_tags": body.get("speech_tags") or "keep",
        "narrator_default": body.get("narrator_default") or "sauti",
        "timing": str(repo_root() / "configs" / "duration.yaml"),
        "lexicon": str(lexicon_file().resolve()),
        "overrides": str(overrides.resolve()),
        "strip_glosses": bool(body.get("strip_glosses", True)),
        "music": _music_value(body.get("music", True)),
        "segments": [_segment_payload(seg, index) for index, seg in enumerate(body.get("segments") or [])],
    }
    if body.get("music_preset"):
        doc["music_preset"] = str(body["music_preset"])
    if body.get("music_rules"):
        doc["music_rules"] = list(body["music_rules"])
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _write_script(script: EpisodeScript) -> None:
    script_json(script.episode_id).write_text(
        json.dumps(script.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    script_markdown(script.episode_id).write_text(render_markdown(script), encoding="utf-8")


def _read_script(path: Path) -> EpisodeScript:
    from mbh.cli import load_script

    return load_script(path)


def _cues(spec: EpisodeSpec, script: EpisodeScript) -> dict[str, dict]:
    try:
        music_path = spec.music if isinstance(spec.music, Path) else None
        cfg = load_music_config(music_path, spec.music_preset, spec.music_rules)
        return {row["line_id"]: row for row in cue_sheet(script.lines, resolve_cues(script.lines, cfg))}
    except Exception:
        return {}


def _audio_index(episode_id: str) -> dict[str, dict]:
    path = manifest_path(episode_id)
    if not path.exists():
        return {}
    return {row["line_id"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


def _clean_fields(fields: dict) -> dict:
    allowed = ("speaker", "emotion", "pace", "tts_text", "music", "take", "direction", "intensity", "fx", "addressee", "type")
    unknown = set(fields) - set(allowed)
    if unknown:
        raise StudioError(f"unknown line fields: {', '.join(sorted(unknown))}")
    out = {}
    for key, value in fields.items():
        if key == "emotion" and value is not None:
            value = check_emotion(str(value))
        if key == "pace" and value is not None and value not in PACES:
            raise StudioError(f"unknown pace {value!r}")
        if key == "speaker" and value is not None:
            _check_speaker(str(value))
        if key == "take" and value is not None:
            value = int(value)
            if value < 0:
                raise StudioError("take must be >= 0")
            if value == 0:
                value = None
        if key == "music" and value is not None:
            _check_music(value)
        if key == "intensity" and value is not None:
            value = float(value)
        out[key] = value
    return out


def _check_speaker(speaker: str) -> None:
    cast = load_cast()
    if speaker not in cast.by_id:
        raise StudioError(f"unknown speaker {speaker!r}")


def _check_preset(name: str | None) -> None:
    if not name:
        return
    cfg = load_music_config()
    if name not in (cfg.get("presets") or {}):
        raise StudioError(f"unknown music preset {name!r}")


def _check_music(value) -> None:
    cfg = load_music_config()
    cue = value.get("cue") if isinstance(value, dict) else value
    if cue not in cfg.get("cues", {}):
        raise StudioError(f"unknown music cue {cue!r}")


def _music_value(music):
    if isinstance(music, str) and music not in {"true", "false"}:
        return music
    if isinstance(music, str):
        return music == "true"
    return bool(music)


def _check_id(episode_id: str) -> str:
    if not _ID.fullmatch(episode_id):
        raise StudioError("episode id must be lowercase letters, digits, and underscores, starting with a letter")
    return episode_id


def _spec(episode_id: str) -> EpisodeSpec:
    _check_id(episode_id)
    path = episode_yaml(episode_id)
    if not path.exists():
        raise FileNotFoundError(episode_id)
    return load_spec(path)


def _line(script: EpisodeScript, line_id: str):
    for line in script.lines:
        if line.id == line_id:
            return line
    raise StudioError(f"no line {line_id}")


def _identity(line, script: EpisodeScript) -> dict:
    return {
        "section": line.section,
        "paragraph": line.paragraph,
        "contains": _unique_contains(line, script.lines),
    }


def _unique_contains(line, lines) -> str:
    text = line.text.strip()
    step = 12
    for size in range(24, len(text) + step, step):
        needle = text[:size]
        hits = [other for other in lines if _same_place(other, line) and needle in other.text]
        if len(hits) == 1:
            return needle
    return text


def _same_place(left, right) -> bool:
    return left.section == right.section and left.paragraph == right.paragraph


def _row_targets(row: dict, line) -> bool:
    if row.get("section") not in (None, line.section) and "section" in row and row["section"] != line.section:
        return False
    if "section" in row and row["section"] != line.section:
        return False
    if "paragraph" in row and row["paragraph"] != line.paragraph:
        return False
    needle = row.get("contains") or row.get("match")
    if needle and needle not in line.text:
        return False
    return bool(needle) or "section" in row


def _field_row_index(rows: list[dict], line) -> int | None:
    hits = [index for index, row in enumerate(rows) if "split" not in row and not row.get("merge_next") and _row_targets(row, line)]
    if not hits:
        return None
    return max(hits, key=lambda index: len(str(rows[index].get("contains") or "")))


def _structural_hit(row: dict, line) -> bool:
    return ("split" in row or bool(row.get("merge_next"))) and _row_targets(row, line)


def _write_overrides(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"overrides": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
