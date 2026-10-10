"""BS.1770 loudness, line normalisation and mastering."""

import math
from pathlib import Path

import pytest

from mbh.episode import loudness as L
from mbh.episode.assemble import assemble
from mbh.episode.audioio import read_mono, write_pcm16
from mbh.episode.models import EpisodeScript, ScriptLine
from mbh.episode.render import RenderResult
from mbh.episode.timing import EngineSettings, Timing

RATE = 16000


def tone(amp, seconds, freq=1000.0, rate=RATE):
    return [amp * math.sin(2 * math.pi * freq * i / rate) for i in range(int(seconds * rate))]


def speechy(amp, seconds, rate=RATE):
    """Syllable-like bursts: 997 Hz tone gated on 180 ms / off 70 ms."""
    out = tone(amp, seconds, 997.0, rate)
    return [s if (i % int(0.25 * rate)) < int(0.18 * rate) else 0.0 for i, s in enumerate(out)]


@pytest.mark.parametrize("pure", [False, True])
def test_integrated_matches_bs1770_reference_tone(monkeypatch, pure):
    if pure:
        monkeypatch.setattr(L, "_lfilter", None)
    # A full-scale 1 kHz sine reads -3.01 LUFS (mono); amplitude 0.1 is 20 dB lower.
    assert abs(L.integrated_lufs(tone(0.1, 3.0), RATE) - (-23.01)) < 0.1
    assert abs(L.integrated_lufs(tone(0.1, 3.0, rate=48000), 48000) - (-23.01)) < 0.1
    assert L.integrated_lufs([0.0] * RATE, RATE) is None  # below the absolute gate


def test_short_fallback_agrees_with_integrated_within_a_db():
    long_v, method = L.measure(speechy(0.2, 4.0), RATE)
    short_v, short_method = L.measure(speechy(0.2, 0.9), RATE)
    assert method == "bs1770" and short_method == "short"
    assert abs(long_v - short_v) < 1.0


def test_normalize_line_and_gain_clamp():
    out, info = L.normalize_line(speechy(0.02, 3.0), RATE, -16.0)
    assert abs(L.measure(out, RATE)[0] - (-16.0)) < 0.1 and info["gain_db"] > 0
    _out, info = L.normalize_line(speechy(0.002, 3.0), RATE, -16.0)
    assert info["gain_db"] == L.MAX_LINE_GAIN_DB  # silence-ish lines are not blown up without bound


def test_limiter_and_master_hit_target_under_ceiling():
    out, overs = L.limit_peaks([0.0] * 100 + [1.0] + [0.0] * 100, RATE, -6.0)
    assert overs == 1 and max(abs(s) for s in out) <= 10 ** (-6 / 20) + 1e-9
    loud = speechy(0.05, 6.0) + [0.9 * s for s in speechy(1.0, 0.5)]  # quiet speech with one hot burst
    out, info = L.master(loud, RATE, -16.0, -1.5)
    assert abs(L.integrated_lufs(out, RATE) - (-16.0)) <= 0.1
    assert max(abs(s) for s in out) <= 10 ** (-2.0 / 20) + 1e-9  # true-peak ceiling minus 0.5 dB margin
    assert info["iterations"] >= 1


def _line(i, speaker):
    return ScriptLine(id=f"l{i}", segment_id="s", type="speech", speaker=speaker, voice_id=speaker, layer=0,
                      emotion="neutral", pace="measured", intensity=0.5, text="words", tts_text="words", turn_id=f"t{i}",
                      section=1, paragraph=1)


def test_assemble_equalises_voices_and_hits_target(tmp_path: Path):
    quiet, hot = tmp_path / "q.wav", tmp_path / "h.wav"
    write_pcm16(quiet, speechy(0.03, 3.0), RATE)
    write_pcm16(hot, speechy(0.15, 3.0), RATE)  # ~14 dB louder voice
    script = EpisodeScript(episode_id="t", title="t", book=1, target_duration_s=6, estimated_duration_s=6, timing={},
                           lines=[_line(1, "sauti"), _line(2, "bhishma")])
    results = [RenderResult("l1", "k1", "rendered", str(quiet), "sauti", "sauti"),
               RenderResult("l2", "k2", "rendered", str(hot), "bhishma", "bhishma")]
    timing = Timing(wpm=160, gap_same_speaker_s=0.25, gap_speaker_change_s=0.5, gap_paragraph_s=1.5, gap_segment_s=1.5)
    rep = assemble(script, results, timing, EngineSettings(sample_rate=RATE), tmp_path / "ep.wav")
    sp = rep["speakers"]
    assert sp["before_speaker_spread_db"] > 12 and sp["after_speaker_spread_db"] < 0.3
    assert abs(rep["measured_lufs"] - (-16.0)) <= 0.15
    assert abs(L.integrated_lufs(read_mono(tmp_path / "ep.wav")[0], RATE) - (-16.0)) <= 0.15


def test_normalize_ref_backs_up_and_hits_target(tmp_path: Path):
    from mbh.voices.normalize_refs import normalize_ref
    ref = tmp_path / "vaisampayana" / "ref.wav"
    write_pcm16(ref, speechy(0.02, 4.0), RATE)
    row = normalize_ref(ref, -20.0, -1.5)
    assert row["changed"] and row["before"] < -30 and abs(L.integrated_lufs(read_mono(ref)[0], RATE) + 20) <= 0.15
    assert len(list(ref.parent.glob("ref_replaced_*_prenorm.wav"))) == 1
    assert normalize_ref(ref, -20.0, -1.5)["changed"] is False  # already within tolerance
