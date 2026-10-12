import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mbh.song.melody import check_raga, parse_line_melody, parse_swara, swara_hz  # noqa: E402
from mbh.song.spec import load_song  # noqa: E402


def test_swara_parsing_and_frequencies():
    assert parse_swara("N.") == ("N", -1)
    assert parse_swara("S''") == ("S", 2)
    assert swara_hz("S", 100) == 100
    assert swara_hz("P", 100) == pytest.approx(150)
    assert swara_hz("S'", 100) == pytest.approx(200)
    assert swara_hz("M", 128) == pytest.approx(180)   # tivra ma, 45/32
    with pytest.raises(ValueError):
        parse_swara("X")
    with pytest.raises(ValueError):
        parse_swara("G#")


def test_melody_maps_notes_to_syllables_with_rests():
    notes = parse_line_melody(["S:1", "R:0.5 G:0.5", {"rest": 1}, "P:2"], ["a", "b", "c"])
    assert [(n.swara, n.syllable, n.start_beat) for n in notes] == [
        ("S", 0, 0.0), ("R", 1, 1.0), ("G", 1, 1.5), ("-", -1, 2.0), ("P", 2, 3.0)]
    with pytest.raises(ValueError):
        parse_line_melody(["S:1"], ["a", "b"])        # too few entries
    with pytest.raises(ValueError):
        parse_line_melody(["S:1", "R:1"], ["a"])      # too many


def test_raga_check():
    notes = parse_line_melody(["S:1", "M:1", "m:1"], ["a", "b", "c"])
    assert check_raga(notes, "yaman") == ["m"]        # shuddha ma is outside Yaman
    assert check_raga(notes, None) == []


def test_title_song_config_is_valid():
    spec = load_song(ROOT / "configs/songs/title_song.yaml")
    assert spec.raga == "yaman"
    for line in spec.lines:
        assert len({n.syllable for n in line.notes if not n.is_rest}) == len(line.syllables)
        assert "।" in line.text
    assert spec.beat_s == pytest.approx(60 / spec.tempo_bpm)


def test_translit_for_aligner():
    from mbh.song.translit import to_ascii
    assert [to_ascii(s) for s in "ध्या य तो पुं सः षू स्मृ".split()] == ["dhyaa", "ya", "to", "pum", "sah", "shuu", "smri"]
    assert set("".join(to_ascii(s) for s in "क्रोधाद्भवति सम्मोहः".split())) <= set("abcdefghijklmnopqrstuvwxyz")


def test_asr_similarity_metric():
    from mbh.song.asr import best_window_similarity, char_similarity, normalize
    assert normalize("ध्यायतो, विषयान्।") == "ध्यायतोविषयान्"
    assert char_similarity("abc", "abc") == 1.0
    ref = "ध्यायतो विषयान्पुंसः"
    assert best_window_similarity("ध्यायतो विषयान्पुंसः", ref) == 1.0
    assert best_window_similarity("ला ला ला ध्यायतो विषयान्पुंसः ला ला ला ला", ref) > 0.9


def test_world_singing_smoke():
    np = pytest.importorskip("numpy")
    pytest.importorskip("pyworld")
    from mbh.song.sing import sing_line
    sr = 16000
    t = np.arange(int(1.2 * sr)) / sr
    # three 'syllables': voiced bursts separated by short gaps
    y = np.sin(2 * np.pi * 140 * t) * (np.sin(2 * np.pi * 1.25 * t) ** 2) * 0.3
    notes = parse_line_melody(["S:1", "R:1", "G:2"], ["a", "b", "c"])
    audio, info = sing_line(y, sr, notes, 3, 146.83, 0.5, {"octave": 0}, lead_s=0.3)
    assert info["align"] == "energy" and len(info["segments"]) == 3
    assert abs(len(audio) / sr - (0.3 + 4 * 0.5 + 0.8)) < 0.1
