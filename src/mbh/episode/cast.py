"""Character registry lookup: aliases, voice groups, narrative layer."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from mbh.characters.build_extracted import AMBIG
from mbh.episode.paths import repo_root

_PAREN = re.compile(r"\s*\([^)]*\)")


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    aliases: tuple[str, ...]
    respelling: str
    voice_group: str
    gender: str
    kind: str

    @property
    def voice_id(self) -> str:
        return self.voice_group or self.id


def narrative_layer(speaker: str) -> int:
    if speaker == "sauti":
        return 1
    if speaker == "vaisampayana":
        return 2
    return 3


class Cast:
    def __init__(self, characters: list[Character]):
        self.by_id = {c.id: c for c in characters}
        seen: dict[str, tuple[str, str]] = {}
        conflict: set[str] = set()
        for char in characters:
            for alias in (char.name, *char.aliases):
                cleaned = clean_alias(alias)
                if not cleaned:
                    continue
                key = cleaned.casefold()
                prev = seen.get(key)
                if prev is None:
                    seen[key] = (cleaned, char.id)
                elif prev[1] != char.id:
                    conflict.add(key)
        self._aliases = [
            (surface, cid) for key, (surface, cid) in seen.items() if key not in conflict
        ]
        self._aliases.sort(key=lambda item: len(item[0]), reverse=True)

    def get(self, character_id: str) -> Character | None:
        return self.by_id.get(character_id)

    def display(self, character_id: str) -> str:
        char = self.by_id.get(character_id)
        return char.name if char else character_id

    def voice_id(self, character_id: str) -> str:
        char = self.by_id.get(character_id)
        return char.voice_id if char else character_id

    def alias_matches(self, sentence: str) -> list[tuple[int, int, str]]:
        """Non-overlapping-unaware matches: (start, length, character id), longest aliases first."""
        found: list[tuple[int, int, str]] = []
        occupied: list[tuple[int, int]] = []
        for surface, cid in self._aliases:
            for match in re.finditer(rf"\b{re.escape(surface)}\b", sentence, flags=re.IGNORECASE):
                span = (match.start(), match.end())
                if any(not (span[1] <= a or span[0] >= b) for a, b in occupied):
                    continue
                occupied.append(span)
                found.append((match.start(), match.end() - match.start(), cid))
        return found


def clean_alias(alias: str) -> str | None:
    if ";" in alias or "(as " in alias.lower():
        return None
    cleaned = _PAREN.sub("", alias).strip()
    if len(cleaned) < 3:
        return None
    if " " not in cleaned and cleaned in AMBIG:
        return None
    if not re.search(r"[A-Za-z]", cleaned):
        return None
    return cleaned


def load_cast(path: Path | None = None) -> Cast:
    file = path or (repo_root() / "characters" / "book01.json")
    data = json.loads(file.read_text(encoding="utf-8"))
    characters = [
        Character(
            id=row["id"],
            name=row["name"],
            aliases=tuple(row.get("aliases") or []),
            respelling=(row.get("respelling") or "").strip(),
            voice_group=(row.get("voice_group") or "").strip(),
            gender=row.get("gender") or "",
            kind=row.get("kind") or "",
        )
        for row in data["characters"]
    ]
    return Cast(characters)


def primary_respelling(field: str) -> str:
    """Speakable respelling. Parenthetical alias hints are not read aloud."""
    field = field.strip()
    field = re.sub(r"\s*\(.*\)\s*$", "", field).strip()
    return field
