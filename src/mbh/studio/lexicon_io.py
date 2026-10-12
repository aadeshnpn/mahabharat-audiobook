"""Read and write lexicon/book01.tsv. TTS still goes through mbh.episode.lexicon."""

from __future__ import annotations

from mbh.episode.lexicon import COLUMNS, Lexeme, load_lexicon, write_lexicon
from mbh.studio.paths import lexicon_file


class LexiconError(ValueError):
    pass


def rows() -> list[dict]:
    path = lexicon_file()
    if not path.exists():
        return []
    return [_public(row) for row in load_lexicon(path)]


def upsert(body: dict) -> dict:
    term = str(body.get("term") or "").strip()
    respelling = str(body.get("respelling") or "").strip()
    if not term or "/" in term or "\\" in term:
        raise LexiconError("term is required")
    if not respelling:
        raise LexiconError("respelling is required (the human pronunciation guide)")
    spoken = str(body.get("spoken") or "").strip()
    verified = 1 if body.get("verified") in (1, True, "1") else 0
    if verified and not spoken:
        raise LexiconError("a verified row needs a spoken form; the engine never reads the caps guide")
    path = lexicon_file()
    current = load_lexicon(path) if path.exists() else []
    updated = Lexeme(
        term=term,
        respelling=respelling,
        ipa=str(body.get("ipa") or "").strip(),
        source=str(body.get("source") or "studio").strip() or "studio",
        verified=verified,
        notes=str(body.get("notes") or "").strip(),
        spoken=spoken,
    )
    found = False
    out: list[Lexeme] = []
    for row in current:
        if row.term.casefold() == term.casefold():
            out.append(updated)
            found = True
        else:
            out.append(row)
    if not found:
        out.append(updated)
    out.sort(key=lambda row: row.term.casefold())
    write_lexicon(path, out)
    return _public(updated)


def _public(row: Lexeme) -> dict:
    return {column: getattr(row, column) for column in COLUMNS}
