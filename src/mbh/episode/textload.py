"""Load Book section text and the section index."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from mbh.episode.paths import repo_root


@dataclass(frozen=True)
class Paragraph:
    number: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class SectionText:
    book: int
    section: int
    sub_parva: str
    source_url: str
    paragraphs: tuple[Paragraph, ...]
    raw: str


def text_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "data" / "text" / "book01"


def load_index(root: Path | None = None) -> list[dict]:
    path = text_dir(root) / "index.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_section(section: int, root: Path | None = None) -> SectionText:
    meta = next(row for row in load_index(root) if row["section"] == section)
    raw = (text_dir(root) / f"{section:03d}.txt").read_text(encoding="utf-8")
    paragraphs = tuple(_paragraphs(raw))
    return SectionText(
        book=int(meta["book"]),
        section=section,
        sub_parva=meta.get("sub_parva", ""),
        source_url=meta.get("source_url", ""),
        paragraphs=paragraphs,
        raw=raw,
    )


def _paragraphs(raw: str) -> list[Paragraph]:
    out: list[Paragraph] = []
    number = 0
    for match in re.finditer(r"[^\n].*?(?:\n(?=\n)|\Z)", raw, flags=re.S):
        chunk = match.group(0).strip()
        if not chunk:
            continue
        number += 1
        # Offsets cover the stripped paragraph inside the file.
        local = match.group(0)
        lead = len(local) - len(local.lstrip())
        start = match.start() + lead
        end = start + len(chunk)
        out.append(Paragraph(number=number, text=chunk, start=start, end=end))
    return out
