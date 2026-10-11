from mbh.episode.pronounce import (extract_target, is_tts_safe, looks_spelled_out, phoneme_similarity,
                                   speakable_respelling)


def test_speakable_respelling_has_no_caps_or_hyphens():
    assert speakable_respelling("vy-shum-PAA-yuh-nuh") == "Vyshumpaayuhnuh"
    assert speakable_respelling("KRISH-nuh dwy-PAH-yuh-nuh") == "Krishnuh Dwypahyuhnuh"
    assert is_tts_safe(speakable_respelling("VAY-duhs"))
    assert not is_tts_safe("VAY-duhs") and not is_tts_safe("vay-duhs")


def test_spelled_out_detection():
    assert looks_spelled_out("the sense of the 4 V A Y does.")
    assert looks_spelled_out("the four V.I.Y. does")
    assert looks_spelled_out("O lotus-eyed S.O.T., And")
    assert not looks_spelled_out("Then Vedas spoke again, softly.")


def test_extract_target_and_phoneme_similarity():
    assert extract_target("Then, Bhishma spoke again, softly.") == ("Bhishma", True)
    assert extract_target("Then the Vay does spoke again softly")[0] == "the Vay does"
    assert extract_target("Bhishma said something")[1] is False
    assert phoneme_similarity("V EY1 D AH0 Z", "V EY D AH Z") == 1.0
    assert phoneme_similarity("V IY1 D AH0 Z", "V EY D AH Z") == 0.8
    assert phoneme_similarity("B IH1 SH M AH0", "B IY SH M AH") == 1.0


def test_roman_key_and_between_anchors():
    from mbh.episode.pronounce import extract_between, key_similarity, roman_key
    assert roman_key("Bheeshma") == roman_key("Bhishma") == "bisma"
    assert key_similarity("Upsuras", "Apsaras") == 1.0
    assert key_similarity("Vaishampaayana", "Vaisampayana") >= 0.9
    assert extract_between("Then Vaisampayana spoke again") == "Vaisampayana"
    assert extract_between("then brahmacarya softly") == "brahmacarya"
    assert extract_between("again, softly.") is None and extract_between("Then V") is None


def test_blank_respelling_never_drops_the_name():
    from mbh.episode.lexicon import Lexeme, tts_form
    assert tts_form(Lexeme(term="Mahadivya", respelling="")) == "Mahadivya"
    assert tts_form(Lexeme(term="Sata-jyoti", respelling="  ")) == "Sata jyoti"
