import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mbh.episode.assemble import _append_outro, _prepend_intro
from mbh.episode.spec import _intro


def test_named_intro_resolves_from_config(tmp_path: Path):
    path, xf = _intro({"intro": "title_song"}, tmp_path / "ep.yaml")
    assert path is not None and path.name.startswith("title_song_v")
    assert xf == 2.5
    assert _intro({"intro": "title_song", "intro_crossfade_s": 1}, tmp_path / "ep.yaml")[1] == 1.0
    assert _intro({}, tmp_path / "ep.yaml") == (None, 0.0)


def test_prepend_intro_crossfades():
    rate = 100
    out, start = _prepend_intro([1.0]*300, [0.5]*500, rate, 1.0)
    assert len(out) == 700 and start == 2.0
    assert out[0] == 1.0 and abs(out[-1] - 0.5) < 1e-9
    out, start = _prepend_intro([1.0]*300, [1.0]*500, rate, 0.0)
    assert len(out) == 800 and start == 3.0


def test_named_outro_resolves_from_config(tmp_path: Path):
    path, xf = _intro({"outro": "ending_song"}, tmp_path / "ep.yaml", "outro")
    assert path is not None and path.parent.name == "outro" and xf == 2.5
    assert _intro({"intro": "title_song"}, tmp_path / "ep.yaml", "outro") == (None, 0.0)


def test_append_outro_crossfades():
    out, at = _append_outro([0.5]*500, [1.0]*300, 100, 1.0)
    assert len(out) == 700 and at == 4.0
    assert out[0] == 0.5 and out[-1] == 1.0
