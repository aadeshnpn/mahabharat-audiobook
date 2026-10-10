"""Pronunciation lexicon: whole-word respelling of TTS text only.

The KMG line stays in ``text``. ``tts_text`` is what the engine sees, after
Krishna→Draupadi resolution and this substitution. Possessives and a trailing
plural -s travel with the spoken form. Longer terms win over shorter ones
(Krishna-Dwaipayana before Krishna).

Two forms per row. ``respelling`` is the human pronunciation guide (stress in caps,
syllables hyphenated). VoxCPM2 must never see it: it reads "VAY-duhs" as letters.
``spoken`` is the form the engine gets, verified by the pronunciation harness
(tools/pronunciation). Rows without one fall back to ``fallback_form``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from mbh.episode.cast import Cast, clean_alias, load_cast, primary_respelling
from mbh.episode.paths import repo_root
from mbh.episode.pronounce import is_tts_safe, speakable_respelling

COLUMNS = ("term", "respelling", "ipa", "source", "verified", "notes", "spoken")


@dataclass(frozen=True)
class Lexeme:
    term: str
    respelling: str
    ipa: str = ""
    source: str = ""
    verified: int = 0
    notes: str = ""
    spoken: str = ""


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
        term, respelling, ipa, source, verified, notes, spoken = parts[:7]
        if not term.strip() or not respelling.strip():
            continue
        try:
            flag = int(verified or "0")
        except ValueError as exc:
            raise ValueError(f"{file}:{line_no}: verified must be 0 or 1") from exc
        rows.append(Lexeme(term.strip(), respelling.strip(), ipa.strip(), source.strip(), flag, notes.strip(), spoken.strip()))
    return rows


def write_lexicon(path: Path, rows: list[Lexeme]) -> None:
    lines = ["# term, respelling (human guide), ipa, source, verified (harness), notes, spoken (what TTS reads) — TTS text only",
             "\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join([
            row.term, row.respelling, row.ipa, row.source, str(row.verified), row.notes.replace("\t", " "), row.spoken,
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
    """Keep curated/hand rows, refresh character-registry rows, write the TSV.

    A refreshed registry row keeps its harness result (spoken, verified, ipa) while its
    respelling is unchanged; a changed respelling resets it to unverified."""
    existing = load_lexicon(path) if path.exists() else []
    kept = [row for row in existing if row.source != "character-registry"]
    old = {row.term.casefold(): row for row in existing if row.source == "character-registry"}
    have = {row.term.casefold() for row in kept}
    generated = []
    for row in registry_rows(cast):
        if row.term.casefold() in have:
            continue
        prev = old.get(row.term.casefold())
        if prev and prev.respelling == row.respelling:
            row = Lexeme(row.term, row.respelling, prev.ipa, row.source, prev.verified, row.notes, prev.spoken)
        generated.append(row)
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
        return tts_form(row) + suffix

    return pattern.sub(repl, text)


FALLBACK = "term"  # unverified rows: "term" (KMG spelling) or "auto" (speakable_respelling); see tools/pronunciation/REPORT.md


def fallback_form(row: Lexeme) -> str:
    if FALLBACK == "auto":
        return speakable_respelling(row.respelling)
    return row.term.replace("-", " ")


def tts_form(row: Lexeme) -> str:
    """What the engine reads: the verified spoken form, else the fallback. Never a caps/hyphen guide."""
    if row.spoken:
        return row.spoken
    form = row.respelling if is_tts_safe(row.respelling) else fallback_form(row)
    return form


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
