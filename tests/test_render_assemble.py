"""Cache keys, resumable render, and assembly gaps. No TTS model required."""

from pathlib import Path

import pytest

from mbh.episode.assemble import assemble
from mbh.episode.audioio import read_mono, write_pcm16
from mbh.episode.models import EpisodeScript, ScriptLine
from mbh.episode.render import RenderResult, cache_key, render_script, voice_version
from mbh.episode.timing import EngineSettings, Timing


class _FakeEngine:
    engine = "fake"

    def __init__(self):
        self.calls = 0

    def synthesize(self, *, text, instruction, reference_wav, out_wav, params):
        self.calls += 1
        write_pcm16(out_wav, [0.2, -0.2, 0.2, -0.2], 8000)


def _line(text="Hello there.", tts=None, speaker="sauti", voice="sauti", paragraph=1) -> ScriptLine:
    return ScriptLine(
        id="ep-0001", segment_id="opening", type="narration", speaker=speaker, voice_id=voice,
        layer=1, emotion="warm", pace="measured", intensity=0.4,
        text=text, tts_text=tts or text, turn_id="t1", section=1, paragraph=paragraph,
    )


def _script(*lines: ScriptLine) -> EpisodeScript:
    return EpisodeScript(
        episode_id="ep", title="t", book=1, target_duration_s=30,
        estimated_duration_s=1, timing={}, lines=list(lines),
    )


def test_cache_key_changes_with_tts_text_and_voice(tmp_path: Path):
    ref = tmp_path / "ref.wav"
    write_pcm16(ref, [0.0, 0.1], 8000)
    line = _line()
    params = {"steps": 10, "cfg_value": 2.0}
    version = voice_version(ref)
    first = cache_key(line, voice_version=version, engine="fake", params=params)
    line.tts_text = "Hello there, friend."
    second = cache_key(line, voice_version=version, engine="fake", params=params)
    assert first != second
    assert cache_key(line, voice_version="other", engine="fake", params=params) != second


def test_render_skips_cached_lines_and_reports_missing_voices(tmp_path: Path):
    voices = tmp_path / "voices"
    ref = voices / "sauti" / "ref.wav"
    write_pcm16(ref, [0.1, -0.1], 8000)
    cache = tmp_path / "cache"
    engine = _FakeEngine()
    settings = EngineSettings(name="fake", steps=5, cfg_value=1.5, sample_rate=8000)
    script = _script(_line())
    first = render_script(script, engine, settings, cache_dir=cache, voices_dir=voices)
    assert first[0].status == "rendered"
    assert engine.calls == 1
    second = render_script(script, engine, settings, cache_dir=cache, voices_dir=voices)
    assert second[0].status == "cached"
    assert engine.calls == 1

    script.lines[0].tts_text = "A changed line."
    script.lines[0].id = "ep-0002"
    third = render_script(script, engine, settings, cache_dir=cache, voices_dir=voices)
    assert third[0].status == "rendered"
    assert engine.calls == 2

    missing = _script(_line(speaker="nobody", voice="nobody"))
    result = render_script(missing, engine, settings, cache_dir=cache, voices_dir=voices)
    assert result[0].status == "missing_voice"
    assert engine.calls == 2

    dry = render_script(
        _script(_line(text="Brand new", tts="Brand new")), engine, settings,
        cache_dir=cache, voices_dir=voices, dry_run=True,
    )
    assert dry[0].status == "would_render"
    assert engine.calls == 2


def test_assemble_inserts_the_configured_gap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rate = 8000
    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    write_pcm16(a, [0.5] * rate, rate)  # 1.0 s
    write_pcm16(b, [0.25] * (rate // 2), rate)  # 0.5 s
    first = _line(text="alpha words", speaker="sauti")
    first.id = "a"
    second = _line(text="beta words", speaker="bhishma", voice="bhishma")
    second.id = "b"
    second.turn_id = "t2"
    timing = Timing(wpm=160, gap_same_speaker_s=0.25, gap_speaker_change_s=0.50, gap_paragraph_s=1.5, gap_segment_s=1.5)
    script = _script(first, second)
    results = [
        RenderResult("a", "k1", "rendered", str(a), "sauti", "sauti"),
        RenderResult("b", "k2", "rendered", str(b), "bhishma", "bhishma"),
    ]
    out = tmp_path / "ep.wav"
    report = assemble(script, results, timing, EngineSettings(sample_rate=rate, true_peak_db=-1.5), out)
    assert report["loudness"] == "bs1770"
    samples, got_rate = read_mono(out)
    assert got_rate == rate
    # 1.0 s + 0.50 s speaker-change gap + 0.5 s
    assert abs(len(samples) / rate - 2.0) < 0.02


def test_voice_version_is_content_based(tmp_path: Path):
    import os
    ref = tmp_path / "ref.wav"
    write_pcm16(ref, [0.1, -0.1] * 100, 8000)
    before = voice_version(ref)
    os.utime(ref, (1, 1))                      # a checkout/copy changes mtime only
    assert voice_version(ref) == before
    write_pcm16(ref, [0.2, -0.2] * 100, 8000)
    assert voice_version(ref) != before
