"""Line-driven music: cue resolution is data-driven, overrides win, and music never covers dialogue."""
import copy
import json
import math
from pathlib import Path

import pytest

from mbh.cli import load_script
from mbh.episode import music
from mbh.episode.models import EpisodeScript, ScriptLine

ROOT = Path(__file__).resolve().parents[1]
CFG = music.load_music_config()


def _pilot():
    return load_script(ROOT / "episodes" / "ep00_pilot.script.json").lines


def _by_id(lines, cues):
    return {l.id[-4:]: c for l, c in zip(lines, cues)}


def test_pilot_cues_follow_each_situation():
    lines = _pilot()
    c = _by_id(lines, music.resolve_cues(lines, CFG))
    assert c["0005"].cue == c["0006"].cue == "grave_drone"           # Bhishma's vow
    assert c["0009"].cue == "bright_lift" and c["0009"].kind == "sting"  # fisherman's joy
    assert c["0009"].bed == c["0008"].cue                           # the bed under a sting continues
    assert c["0010"].cue == c["0011"].cue == "celestial_swell"      # flowers rain / 'This one is Bhishma'
    assert c["0011"].intensity == 1.0
    assert c["0013"].cue == "tender_resolve"                        # 'O mother, ascend this chariot'
    assert c["0016"].cue == "sacred_invocation"                     # Om
    assert c["0018"].cue == "forest_ashram"                         # Sauti arrives at Naimisha
    for k in ("0030", "0031", "0034"):                              # the Rishis' request builds to the end
        assert c[k].cue == "reverent_anticipation" and c[k].build_to_end
    assert c["0030"].source.startswith("inherit:")                  # 'The Rishi replied,' joins the next cue
    assert c["0026"].source.startswith("inherit:")


def test_emotion_table_covers_new_episodes_and_overrides_win():
    lines = copy.deepcopy(_pilot()[:3])
    for l in lines:
        l.segment_id, l.paragraph, l.fx = "elsewhere", 99, None
    lines[0].text, lines[0].emotion = "Long narration about grief in a far country here.", "grief"
    lines[1].music = "none"
    lines[2].music = {"cue": "celestial_swell", "intensity": 0.3}
    cues = music.resolve_cues(lines, CFG)
    assert (cues[0].cue, cues[0].source) == ("grave_drone", "emotion:grief")
    assert (cues[1].cue, cues[1].source) == ("none", "override")
    assert (cues[2].cue, cues[2].intensity) == ("celestial_swell", 0.3)
    lines[1].music = "no_such_cue"
    with pytest.raises(ValueError):
        music.resolve_cues(lines, CFG)


def test_rules_are_data(tmp_path: Path):
    cfg = copy.deepcopy(CFG)
    cfg["rules"].insert(0, {"name": "all_tender", "match": {"speaker": "bhishma"}, "cue": "tender_resolve", "intensity": 0.2})
    lines = _pilot()
    c = _by_id(lines, music.resolve_cues(lines, cfg))
    assert c["0005"].cue == "tender_resolve" and c["0005"].source == "rule:all_tender"


def test_plan_regions_tile_the_episode_and_stings_sit_in_pauses():
    lines = _pilot()
    cues = music.resolve_cues(lines, CFG)
    t, iv = 0.0, []
    for l in lines:
        iv.append((l.id, t, t + 3.0)); t += 3.8
    regions, stings = music.plan(cues, iv, t + 4, CFG)
    assert regions[0].start_s == 0 and regions[-1].end_s == t + 4
    assert all(abs(a.end_s - b.start_s) < 1e-9 for a, b in zip(regions, regions[1:]))
    assert all(a.cue != b.cue for a, b in zip(regions, regions[1:]))
    ends = {lid: e for lid, _s, e in iv}
    assert [s["line_id"][-4:] for s in stings] == ["0009"] and stings[0]["at_s"] > ends[stings[0]["line_id"]]


def test_ducking_and_birds_stay_out_of_speech():
    np = pytest.importorskip("numpy"); pytest.importorskip("scipy")
    rate = 16000
    cfg = copy.deepcopy(CFG)
    speech = [(1.0, 3.0), (4.0, 6.0)]
    regions = [music.Region("forest_ashram", 0.0, 8.0, 1.0)]
    bus = music.render_music(regions, [], speech, 8.0, rate, cfg)
    free = music.render_music(regions, [], [], 8.0, rate, cfg)       # same bed, nobody speaking
    def rms(x, a, b):
        x = x[int(a * rate):int(b * rate)]
        return 20 * math.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-12)
    assert rms(bus, 1.5, 2.8) - rms(free, 1.5, 2.8) < -cfg["duck_db"] + 1.5   # fully ducked under speech
    assert abs(rms(bus, 3.45, 3.55) - rms(free, 3.45, 3.55)) < cfg["duck_db"]  # recovering in the pause
    from scipy.signal import butter, sosfilt
    hi = sosfilt(butter(4, 2200, "high", fs=rate, output="sos"), bus)
    under = float(np.sqrt(np.mean(hi[int(1.2 * rate):int(2.9 * rate)] ** 2)))
    assert under < 1e-3                                           # no chirps while anyone speaks


def test_assemble_with_music_keeps_speech_on_top(tmp_path: Path):
    np = pytest.importorskip("numpy"); pytest.importorskip("scipy")
    from mbh.episode.assemble import assemble
    from mbh.episode.audioio import write_pcm16
    from mbh.episode.render import RenderResult
    from mbh.episode.timing import EngineSettings, Timing
    rate = 16000
    lines, results = [], []
    for i, (emo, spk) in enumerate([("solemn_resolve", "bhishma"), ("joyful", "dasa"), ("awed", "vaisampayana")]):
        p = tmp_path / f"{i}.wav"
        t = np.arange(int(2.5 * rate)) / rate
        write_pcm16(p, (0.3 * np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))).tolist(), rate)
        lines.append(ScriptLine(id=f"l{i}", segment_id="s", type="speech", speaker=spk, voice_id=spk, layer=1, emotion=emo,
                                pace="measured", intensity=0.5, text="words here now ok", tts_text="words here now ok",
                                turn_id=f"t{i}", section=1, paragraph=1))
        results.append(RenderResult(f"l{i}", f"k{i}", "rendered", str(p), spk, spk))
    script = EpisodeScript(episode_id="ep", title="t", book=1, target_duration_s=10, estimated_duration_s=8, timing={}, lines=lines)
    timing = Timing(wpm=160, gap_same_speaker_s=0.25, gap_speaker_change_s=0.5, gap_paragraph_s=1.5, gap_segment_s=1.5)
    rep = assemble(script, results, timing, EngineSettings(sample_rate=rate, true_peak_db=-1.5), tmp_path / "o.wav", music_cfg=CFG)
    m = rep["music"]
    assert [r["cue"] for r in m["regions"]] == ["grave_drone", "celestial_swell"]
    assert m["stings"][0]["cue"] == "bright_lift"
    assert m["min_speech_to_music_db"] >= 18
    assert abs(rep["measured_lufs"] - rep["target_lufs"]) < 0.6
    assert rep["seconds"] > 8.5 + CFG["tail_s"] - 0.1
