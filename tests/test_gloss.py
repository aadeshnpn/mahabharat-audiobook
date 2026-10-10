"""Parenthetical glosses are removed from spoken text and kept in the script."""

from mbh.episode.gloss import is_gloss, strip_glosses


def test_named_glosses_are_removed_and_numbers_stay():
    samples = {
        "O fisherman, from this day I adopt the vow of Brahmacharya (study and meditation in celibacy).":
            "O fisherman, from this day I adopt the vow of Brahmacharya.",
        "he saluted those Munis (sages) with joined palms":
            "he saluted those Munis with joined palms",
        "what, O ye Dwijas (twice-born), shall I repeat":
            "what, O ye Dwijas, shall I repeat",
        "This one is Bhishma (the terrible).":
            "This one is Bhishma.",
        "His neck was marked with (three) lines, like a conch-shell.":
            "His neck was marked with (three) lines, like a conch-shell.",
        "Kunti and her (five) sons.":
            "Kunti and her (five) sons.",
        "This history (first) recited by Krishna.":
            "This history (first) recited by Krishna.",
        "their playing (with the Pandavas) at dice":
            "their playing at dice",
    }
    for source, spoken in samples.items():
        assert strip_glosses(source) == spoken

    assert is_gloss("the terrible")
    assert is_gloss("sages")
    assert not is_gloss("three")
    assert not is_gloss("  12 ")
