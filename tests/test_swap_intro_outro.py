import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))

from mbh.episode.assemble import _append_outro, _prepend_intro  # noqa: E402
import swap_intro_outro as sw  # noqa: E402


def _assemble(intro, body, outro, xf_s, gain):
    mixed, _ = _append_outro(body, outro, sw.RATE, xf_s)
    mixed, _ = _prepend_intro(intro, mixed, sw.RATE, xf_s)
    return np.asarray(mixed) * gain


def test_swap_matches_direct_assembly():
    rng = np.random.default_rng(0); R = sw.RATE
    body = rng.normal(0, 0.1, 20 * R)
    old_in, new_in = rng.normal(0, 0.2, 6 * R), rng.normal(0, 0.2, 7 * R)
    old_out, new_out = rng.normal(0, 0.2, 5 * R), rng.normal(0, 0.2, 4 * R)
    episode = _assemble(old_in, body, old_out, 2.5, 1.3)
    mixed, info = sw.swap(episode, old_in, new_in, old_out, new_out, 2.5, 2.5)
    want = _assemble(new_in, body, new_out, 2.5, 1.0)
    assert len(mixed) == len(want)
    assert np.max(np.abs(mixed - want)) < 1e-9
    assert info["old_intro"]["episode_starts_s"] == 3.5 and info["new_episode_starts_s"] == 4.5
    assert abs(info["old_intro"]["gain_db"] - 20 * np.log10(1.3)) < 0.01
