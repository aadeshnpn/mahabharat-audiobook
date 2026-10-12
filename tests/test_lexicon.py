"""Pronunciation lexicon: whole words, possessives, plurals, longer terms first."""

from mbh.episode.lexicon import Lexeme, apply_lexicon, load_lexicon
from mbh.text.krishna import speakable
from mbh.episode.textload import load_section


def test_possessive_and_plural_and_longest_match():
    lex = [
        Lexeme("Krishna", "KRISH-nuh"),
        Lexeme("Krishna-Dwaipayana", "KRISH-nuh dwy-PAH-yuh-nuh"),
        Lexeme("Sauti", "SOW-tee"),
        Lexeme("Rishi", "RISH-ee"),
    ]
    text = "Sauti's Krishna-Dwaipayana met Krishna and the Rishis."
    out = apply_lexicon(text, lex)
    # Rows without a verified spoken form fall back to a TTS-safe form (the KMG spelling), never the caps guide.
    assert out == "Sauti's Krishna Dwaipayana met Krishna and the Rishis."
    assert apply_lexicon("No names here.", lex) == "No names here."


def test_book_lexicon_has_registry_names():
    rows = {row.term: row for row in load_lexicon()}
    assert rows["Vaisampayana"].respelling == "vy-shum-PAA-yuh-nuh"
    assert rows["Sauti"].respelling == "SOW-tee"
    assert rows["Bhishma"].source == "character-registry"
    assert rows["Naimisha"].source == "curated"
    assert rows["Devavrata"].respelling == "DAY-vuh-VRAH-tuh"
    # A longer curated term must not be eaten by a shorter name.
    spoken = apply_lexicon("Krishna-Dwaipayana and Brahmarshis", list(rows.values()))
    assert spoken == "Krishna Dwaipayana and Brahmarshis"
    assert rows["Vedas"].verified == 1 and rows["Vedas"].spoken == "Vedas"
    assert rows["Rishi"].spoken == "Rishee"


def test_draupadi_krishna_is_respelt_only_after_resolution():
    raw = load_section(197).raw
    spoken = speakable(197, raw)
    assert "Kunti and Draupadi and Bhima" in spoken
    lex = load_lexicon()
    out = apply_lexicon(spoken, lex)
    draupadi = next(r for r in lex if r.term == "Draupadi")
    assert (draupadi.spoken if draupadi.verified else "Draupadi") in out  # verified spoken form (harness: 'Drowpadee')
    # The compound in the opening is Vyasa, not Draupadi.
    opening = speakable(1, load_section(1).paragraphs[3].text)
    assert "Draupadi" not in opening
    tts = apply_lexicon(opening, load_lexicon())
    assert "Draupadi" not in tts
    assert "Krishna Dwaipayana" in tts


def test_spoken_form_wins_and_guides_never_reach_tts(tmp_path):
    from mbh.episode.lexicon import sync_registry, tts_form, write_lexicon
    from mbh.episode.pronounce import is_tts_safe
    rows = [Lexeme("Vedas", "VAY-duhs", spoken="Vaydas", verified=1), Lexeme("Apsaras", "UP-suh-rahs")]
    assert apply_lexicon("the four Vedas and the Apsaras", rows).startswith("the four Vaydas and the ")
    assert is_tts_safe(tts_form(rows[1]))
    path = tmp_path / "lex.tsv"
    write_lexicon(path, rows)
    assert load_lexicon(path)[0].spoken == "Vaydas" and load_lexicon(path)[0].verified == 1
    # every row in the real lexicon yields a TTS-safe form
    assert all(is_tts_safe(tts_form(row)) for row in load_lexicon())


def test_registry_refresh_keeps_harness_results(tmp_path):
    from mbh.episode.cast import load_cast
    from mbh.episode.lexicon import registry_rows, sync_registry, write_lexicon
    cast = load_cast()
    first = registry_rows(cast)[0]
    path = tmp_path / "lex.tsv"
    write_lexicon(path, [Lexeme(first.term, first.respelling, source="character-registry", verified=1, spoken="Xyz")])
    row = {r.term: r for r in sync_registry(path, cast)}[first.term]
    assert row.spoken == "Xyz" and row.verified == 1
