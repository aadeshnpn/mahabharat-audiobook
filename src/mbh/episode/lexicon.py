"""Pronunciation lexicon: whole-word respelling of TTS text only.

The KMG line stays in ``text``. ``tts_text`` is what the engine sees, after
Krishna→Draupadi resolution and this substitution. Possessives and a trailing
plural -s travel with the respelling. Longer terms win over shorter ones
(Krishna-Dwaipayana before Krishna).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mbh.episode.cast import Cast, clean_alias, load_cast, primary_respelling
from mbh.episode.paths import repo_root

COLUMNS = ("term", "respelling", "ipa", "source", "verified", "notes")


@dataclass(frozen=True)
class Lexeme:
    term: str
    respelling: str
    ipa: str = ""
    source: str = ""
    verified: int = 0
    notes: str = ""


def load_lexicon(path: Path | None = None) -> list[Lexeme]:
    file = path or (repo_root() / "lexicon" / "book01.tsv")
    rows: list[Lexeme] = []
    for line_no, raw in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip() or raw.startswith("#") or raw.startswith("term\t"):
            continue
        parts = raw.split("\t")
        if len(parts) < 2:
            raise ValueError(f"{file}:{line_no}: expected term and respelling")
        while len(parts) < len(COLUMNS):
            parts.append("")
        term, respelling, ipa, source, verified, notes = parts[:6]
        if not term.strip() or not respelling.strip():
            continue
        try:
            flag = int(verified or "0")
        except ValueError as exc:
            raise ValueError(f"{file}:{line_no}: verified must be 0 or 1") from exc
        rows.append(Lexeme(term.strip(), respelling.strip(), ipa.strip(), source.strip(), flag, notes.strip()))
    return rows


def write_lexicon(path: Path, rows: list[Lexeme]) -> None:
    lines = ["# term, respelling, ipa, source, verified, notes — applied to TTS text only",
             "\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join([
            row.term, row.respelling, row.ipa, row.source, str(row.verified), row.notes.replace("\t", " "),
        ]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def registry_rows(cast: Cast) -> list[Lexeme]:
    """One row per single-token character name, using the registry respelling."""
    rows: list[Lexeme] = []
    for char in cast.by_id.values():
        spoken = primary_respelling(char.respelling)
        name = clean_alias(char.name)
        if not name or not spoken or " " in name:
            continue
        rows.append(Lexeme(
            term=name,
            respelling=spoken,
            source="character-registry",
            notes=char.respelling if char.respelling != spoken else "",
        ))
    rows.sort(key=lambda row: row.term.casefold())
    return rows


def sync_registry(path: Path, cast: Cast) -> list[Lexeme]:
    """Keep curated/hand rows, refresh character-registry rows, write the TSV."""
    existing = load_lexicon(path) if path.exists() else []
    kept = [row for row in existing if row.source != "character-registry"]
    have = {row.term.casefold() for row in kept}
    generated = [row for row in registry_rows(cast) if row.term.casefold() not in have]
    rows = kept + generated
    write_lexicon(path, rows)
    return rows


def apply_lexicon(text: str, lexemes: list[Lexeme]) -> str:
    if not text or not lexemes:
        return text
    by_fold: dict[str, Lexeme] = {}
    for row in lexemes:
        by_fold.setdefault(row.term.casefold(), row)
    ordered = sorted(by_fold.values(), key=lambda row: len(row.term), reverse=True)
    alternation = "|".join(re.escape(row.term) for row in ordered)
    pattern = re.compile(rf"\b(?:{alternation})(?:'s|s)?\b", re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        base, suffix = _split_suffix(word, by_fold)
        row = by_fold.get(base.casefold())
        if row is None:
            return word
        return row.respelling + suffix

    return pattern.sub(repl, text)


def main() -> None:
    """Refresh character-registry rows in lexicon/book01.tsv. Curated rows stay."""
    path = repo_root() / "lexicon" / "book01.tsv"
    rows = sync_registry(path, load_cast())
    print(f"wrote {len(rows)} rows to {path}")


def _split_suffix(word: str, by_fold: dict[str, Lexeme]) -> tuple[str, str]:
    folded = word.casefold()
    if folded.endswith("'s"):
        stem = word[:-2]
        if stem.casefold() in by_fold and folded not in by_fold:
            return stem, word[-2:]
    if folded.endswith("s") and folded not in by_fold:
        stem = word[:-1]
        if stem.casefold() in by_fold:
            return stem, word[-1]
    return word, ""


if __name__ == "__main__":
    main()
