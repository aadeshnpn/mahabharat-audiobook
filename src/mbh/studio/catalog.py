"""Section list, music presets, and the fixed emotion/pace vocabulary."""

from __future__ import annotations

from mbh.episode.models import EMOTIONS, PACES
from mbh.episode.music import load_music_config
from mbh.episode.textload import load_index, load_section
from mbh.episode.timing import word_count

_sections: list[dict] | None = None


def music_meta() -> dict:
    cfg = load_music_config()
    cues = [
        {"id": name, "kind": row.get("kind", "bed"), "note": row.get("note", "")}
        for name, row in cfg.get("cues", {}).items()
    ]
    return {
        "preset": cfg.get("preset"),
        "presets": sorted((cfg.get("presets") or {}).keys()),
        "cues": cues,
    }


def emotions() -> list[str]:
    return list(EMOTIONS)


def paces() -> list[str]:
    return list(PACES)


def list_sections() -> list[dict]:
    global _sections
    if _sections is None:
        rows = []
        for meta in load_index():
            text = load_section(int(meta["section"]))
            rows.append({
                "section": int(meta["section"]),
                "sub_parva": meta.get("sub_parva", ""),
                "paragraphs": len(text.paragraphs),
                "title": meta.get("title") or "",
            })
        _sections = rows
    return _sections


def section_detail(section: int) -> dict:
    text = load_section(section)
    return {
        "section": text.section,
        "sub_parva": text.sub_parva,
        "source_url": text.source_url,
        "paragraphs": [
            {"number": para.number, "words": word_count(para.text), "text": para.text}
            for para in text.paragraphs
        ],
    }
