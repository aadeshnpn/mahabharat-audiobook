"""Episode spec (YAML): which sections, bridges, and target length."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from mbh.episode.models import SegmentKind, assert_never
from mbh.episode.paths import repo_root


@dataclass
class SegmentSpec:
    id: str
    kind: SegmentKind
    label: str = ""
    section: int | None = None
    paragraphs: tuple[int, int] | None = None
    narrator: str | None = None
    excerpt: bool = False
    abridged: bool = False
    note: str = ""
    speaker: str | None = None
    emotion: str | None = None
    pace: str | None = None
    text: str = ""
    non_kmg: bool = False
    strip_glosses: bool | None = None


@dataclass
class EpisodeSpec:
    id: str
    title: str
    book: int
    target_duration_s: float
    segments: list[SegmentSpec]
    path: Path
    speech_tags: Literal["keep", "drop"] = "keep"
    narrator_default: str = "sauti"
    timing_path: Path | None = None
    overrides_path: Path | None = None
    lexicon_path: Path | None = None
    end_reason: str = ""
    summary: str = ""
    intro: Path | None = None
    # seconds the intro's tail overlaps the first line (named intros in configs/intros.yaml set it)
    intro_crossfade_s: float = 0.0
    outro: Path | None = None
    # seconds the episode tail (music fade) overlaps the outro start (named outros in configs/outros.yaml set it)
    outro_crossfade_s: float = 0.0
    notes: list[str] = field(default_factory=list)
    # None follows configs/duration.yaml. True/False is this episode's choice.
    strip_glosses: bool | None = None
    # music bed: None/False = off, True = configs/music.yaml, or a path to another cue config
    music: bool | Path | None = None
    music_preset: str | None = None
    music_rules: list[dict] = field(default_factory=list)


def load_spec(path: Path) -> EpisodeSpec:
    path = path.resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not an episode mapping")
    segments = [_segment(row, index) for index, row in enumerate(data.get("segments") or [])]
    if not segments:
        raise ValueError(f"{path} has no segments")
    speech_tags = data.get("speech_tags", "keep")
    if speech_tags not in ("keep", "drop"):
        raise ValueError("speech_tags must be keep or drop")
    return EpisodeSpec(
        id=str(data["id"]),
        title=str(data.get("title") or data["id"]),
        book=int(data.get("book", 1)),
        target_duration_s=float(data.get("target_duration_s", 300)),
        segments=segments,
        path=path,
        speech_tags=speech_tags,
        narrator_default=str(data.get("narrator_default", "sauti")),
        timing_path=_opt_path(data.get("timing"), path),
        overrides_path=_opt_path(data.get("overrides"), path),
        lexicon_path=_opt_path(data.get("lexicon"), path),
        end_reason=str(data.get("end_reason") or "").strip(),
        summary=str(data.get("summary") or "").strip(),
        intro=_intro(data, path)[0],
        intro_crossfade_s=_intro(data, path)[1],
        outro=_intro(data, path, "outro")[0],
        outro_crossfade_s=_intro(data, path, "outro")[1],
        notes=[str(item) for item in (data.get("notes") or [])],
        strip_glosses=_opt_bool(data, "strip_glosses"),
        music_rules=list(data.get("music_rules") or []),
        music_preset=(str(data["music_preset"]) if data.get("music_preset") else None),
        music=(data.get("music") if isinstance(data.get("music"), bool) or data.get("music") is None else _opt_path(data.get("music"), path)),
    )


def _segment(row: dict, index: int) -> SegmentSpec:
    kind = row.get("kind")
    if kind not in ("section", "bridge"):
        raise ValueError(f"segment {index} kind must be section or bridge")
    paragraphs = None
    if row.get("paragraphs"):
        start, end = row["paragraphs"]
        paragraphs = (int(start), int(end))
        if end < start:
            raise ValueError(f"segment {row.get('id', index)} paragraph range is reversed")
    spec = SegmentSpec(
        id=str(row.get("id") or f"seg{index+1}"),
        kind=kind,
        label=str(row.get("label") or ""),
        section=int(row["section"]) if row.get("section") else None,
        paragraphs=paragraphs,
        narrator=row.get("narrator"),
        excerpt=bool(row.get("excerpt", False)),
        abridged=bool(row.get("abridged", False)),
        note=str(row.get("note") or "").strip(),
        speaker=row.get("speaker"),
        emotion=row.get("emotion"),
        pace=row.get("pace"),
        text=str(row.get("text") or "").strip(),
        non_kmg=bool(row.get("non_kmg", kind == "bridge")),
        strip_glosses=_opt_bool(row, "strip_glosses"),
    )
    if kind == "section" and spec.section is None:
        raise ValueError(f"segment {spec.id} needs a section number")
    if kind == "bridge" and not spec.text:
        raise ValueError(f"segment {spec.id} bridge needs text")
    if kind == "bridge" and not spec.speaker:
        raise ValueError(f"segment {spec.id} bridge needs a speaker")
    _check_kind(spec)
    return spec


def _check_kind(spec: SegmentSpec) -> None:
    kind: SegmentKind = spec.kind
    if kind == "section" or kind == "bridge":
        return
    assert_never(kind)


def _opt_bool(data: dict, key: str) -> bool | None:
    if key not in data or data[key] is None:
        return None
    return bool(data[key])


def _opt_path(value: str | None, spec_path: Path) -> Path | None:
    if not value:
        return None
    raw = Path(value)
    if raw.is_absolute():
        return raw
    beside = spec_path.parent / raw
    if beside.exists():
        return beside
    rooted = repo_root() / raw
    return rooted


def _intro(data: dict, spec_path: Path, key: str = "intro") -> tuple[Path | None, float]:
    """``intro:``/``outro:`` is a path, or a name from configs/intros.yaml / configs/outros.yaml (``intro: title_song``)."""
    value = data.get(key)
    xf = data.get(f"{key}_crossfade_s")
    if not value:
        return None, 0.0
    import yaml

    named = repo_root() / "configs" / f"{key}s.yaml"
    table = (yaml.safe_load(named.read_text(encoding="utf-8")) or {}) if named.exists() else {}
    if str(value) in table:
        row = table[str(value)]
        return repo_root() / row["path"], float(xf if xf is not None else row.get("crossfade_s", 0.0))
    return _opt_path(str(value), spec_path), float(xf or 0.0)
