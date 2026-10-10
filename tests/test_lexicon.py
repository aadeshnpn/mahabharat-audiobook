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
    assert out == "SOW-tee's KRISH-nuh dwy-PAH-yuh-nuh met KRISH-nuh and the RISH-ees."
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
    assert spoken.startswith("KRISH-nuh dwy-PAH-yuh-nuh")
    assert "brah-MAR-sheez" in spoken
    assert "BRUH-muh" not in spoken.split("and")[0]


def test_draupadi_krishna_is_respelt_only_after_resolution():
    raw = load_section(197).raw
    spoken = speakable(197, raw)
    assert "Kunti and Draupadi and Bhima" in spoken
    out = apply_lexicon(spoken, load_lexicon())
    assert "DROW-puh-dee" in out
    # The compound in the opening is Vyasa, not Draupadi.
    opening = speakable(1, load_section(1).paragraphs[3].text)
    assert "Draupadi" not in opening
    tts = apply_lexicon(opening, load_lexicon())
    assert "Draupadi" not in tts
    assert "KRISH-nuh dwy-PAH-yuh-nuh" in tts
