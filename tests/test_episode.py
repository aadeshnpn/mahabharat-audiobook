"""Script builder, duration model, and natural-break suggester."""

import json
import re
from pathlib import Path

from mbh.episode.attribute import LLMAttributor, QuoteState, RuleAttributor
from mbh.episode.breaks import endpoint_ok, suggest_breaks, suggest_for_spec, suggest_in_section
from mbh.episode.build import build_episode, build_section_lines
from mbh.episode.cast import load_cast
from mbh.episode.models import ScriptLine
from mbh.episode.spec import load_spec
from mbh.episode.textload import load_section
from mbh.episode.timing import Timing, apply_timing, load_timing, speech_seconds, word_count

ROOT = Path(__file__).resolve().parents[1]


def _norm(text: str) -> str:
    text = re.sub(r"[\"“”‘’']", "", text)
    return re.sub(r"\s+", " ", text).strip()


def test_section_paragraphs_round_trip():
    cast = load_cast()
    rules = RuleAttributor(cast)
    for section, narrator, numbers in ((100, "vaisampayana", (10, 11)), (1, "sauti", (1, 2, 3, 4, 5))):
        sec = load_section(section)
        state = QuoteState()
        by_para: dict[int, list] = {}
        for para in sec.paragraphs:
            if para.number > max(numbers):
                break
            lines, state = rules.attribute_paragraph(
                section, para.number, para.text, para.start, narrator, state,
            )
            by_para[para.number] = lines
        for number in numbers:
            para = next(p for p in sec.paragraphs if p.number == number)
            joined = " ".join(line.text for line in by_para[number])
            assert _norm(joined) == _norm(para.text), f"§{section} ¶{number} dropped or duplicated text"


def test_vow_and_opening_speakers():
    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    script = build_episode(spec)
    assert script.warnings == []
    speech = [(line.speaker, line.text) for line in script.lines if line.type == "speech"]

    def said(speaker, snippet):
        assert any(who == speaker and snippet in text for who, text in speech), (speaker, snippet)

    said("bhishma", "vow of Brahmacharya")
    said("dasa", "I bestow my daughter!")
    said("devas_chorus", "This one is Bhishma (the terrible).")
    said("bhishma", "O mother, ascend this chariot")
    said("naimisha_rishis", "Whence comest thou")
    said("sauti", "Krishna-Dwaipayana")
    said("naimisha_rishis", "history also called Bharata")

    vow = next(line for line in script.lines if "from this day I adopt the vow" in line.text)
    assert vow.emotion == "solemn_resolve"
    assert vow.pace == "slow"
    assert vow.attribution == "override"
    assert "Brahmacharya" in vow.tts_text  # verified spoken form (tools/pronunciation)
    assert not re.search(r"\b[A-Z]{2,}", vow.tts_text)  # no caps guide respellings reach the engine
    assert "Brahmacharya" in vow.text

    chorus = next(line for line in script.lines if "This one is Bhishma" in line.text)
    assert chorus.fx == "celestial"
    assert chorus.voice_id == "devas_chorus"
    assert chorus.tts_text == "This one is Bhishma."

    # Krishna-Dwaipayana in the opening is Vyasa's name, spoken as itself.
    dwaipayana = next(line for line in script.lines if "Krishna-Dwaipayana" in line.text)
    assert "Draupadi" not in dwaipayana.tts_text
    assert "Krishna Dwaipayana" in dwaipayana.tts_text

    bridges = [line for line in script.lines if line.non_kmg]
    assert bridges and all(line.type == "bridge" for line in bridges)
    assert all("non_kmg" in line.flags for line in bridges)
    assert all(not line.abridged for line in script.lines)
    assert any(line.excerpt for line in script.lines)
    # "X said" stays with the narrator.
    assert any(line.type == "narration" and line.text == "Sauti said," and line.speaker == "sauti" for line in script.lines)
    assert any(line.type == "narration" and line.speaker == "vaisampayana" and "son of Ganga" in line.text for line in script.lines)


def test_drop_speech_tags_keeps_real_narration():
    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    spec.speech_tags = "drop"
    spec.overrides_path = None
    script = build_episode(spec)
    texts = [line.text for line in script.lines]
    assert "Sauti said," not in texts
    assert "Vaisampayana continued," not in texts
    assert any("son of Ganga" in text and text.endswith("father,") for text in texts)
    assert any("vow of Brahmacharya" in text for text in texts)


def test_llm_hook_can_replace_a_speaker_and_is_idle_by_default():
    cast = load_cast()
    rules = RuleAttributor(cast)
    sec = load_section(1)
    para = sec.paragraphs[0]
    plain, _state = rules.attribute_paragraph(1, 1, para.text, para.start, "sauti", QuoteState())
    idle = LLMAttributor(RuleAttributor(cast), complete=None)
    same, _state = idle.attribute_paragraph(1, 1, para.text, para.start, "sauti", QuoteState())
    assert [line.text for line in same] == [line.text for line in plain]

    def revise(_section, _paragraph, _text, lines):
        lines[0].speaker = "janamejaya"
        return lines

    hooked = LLMAttributor(RuleAttributor(cast), complete=revise)
    changed, _state = hooked.attribute_paragraph(1, 1, para.text, para.start, "sauti", QuoteState())
    assert changed[0].speaker == "janamejaya"
    assert "llm" in changed[0].flags


def test_voice_group_shares_the_naimisha_voice():
    cast = load_cast()
    assert cast.voice_id("satasringa_rishis") == "naimisha_rishis"
    assert cast.voice_id("valakhilyas") == "naimisha_rishis"
    assert cast.voice_id("bhishma") == "bhishma"
    assert cast.display("balarama") == "Balarama"
    assert cast.display("chitraratha") == "Chitraratha"


def test_prototype_excerpt_calibrates_near_99_seconds():
    """Historical calibration: the prototype excerpt at its own fitted 160.9 wpm. The configured rate
    (138.1) is fitted on the full pilot render and is checked in test_breaks..."""
    import dataclasses
    import json
    excerpt = json.loads((ROOT / "proto" / "excerpt_100.json").read_text())
    timing, _engine = load_timing(ROOT / "configs" / "duration.yaml")
    assert timing.wpm == 138.1
    timing = dataclasses.replace(timing, wpm=160.9)
    lines = []
    for index, seg in enumerate(excerpt["segments"]):
        lines.append(ScriptLine(
            id=str(index), segment_id="excerpt", type=seg["type"], speaker=seg["speaker"],
            voice_id=seg["speaker"], layer=2, emotion=seg["emotion"], pace=seg["pace"],
            intensity=0.5, text=seg["text"], tts_text=seg["text"], turn_id=f"t{index}",
            section=100, paragraph=10,
        ))
    # The two Bhishma vow sentences were one turn in the excerpt's gap pattern:
    # the prototype counted one same-speaker gap. Give those two lines one turn
    # only if they are adjacent and the same speaker; gaps follow speaker, not turn.
    total = apply_timing(lines, timing)
    assert word_count(" ".join(seg["text"] for seg in excerpt["segments"])) == 250
    assert abs(total - 99.0) < 1.5
    assert timing.wpm == 160.9


def test_wpm_is_configurable():
    timing = Timing(wpm=120, gap_same_speaker_s=0, gap_speaker_change_s=0, gap_paragraph_s=0, gap_segment_s=0)
    assert abs(speech_seconds("one two three four five", timing) - 2.5) < 1e-9
    fast = Timing(wpm=240, gap_same_speaker_s=0, gap_speaker_change_s=0, gap_paragraph_s=0, gap_segment_s=0)
    assert speech_seconds("one two three four five", fast) == speech_seconds("one two three four five", timing) / 2


def test_breaks_never_cut_a_turn_and_offer_the_rishi_question():
    lines = build_section_lines(100, narrator="vaisampayana", paragraphs=(10, 11))
    vow = [line for line in lines if line.speaker == "bhishma" and line.paragraph == 10]
    assert len(vow) >= 2
    assert endpoint_ok(vow[0], vow[1]) == (False, "same speaker's turn continues")
    last_vow = vow[-1]
    nxt = lines[lines.index(last_vow) + 1]
    assert endpoint_ok(last_vow, nxt)[0] is True

    suggestions = suggest_in_section(1, target_s=220, narrator="sauti", start_paragraph=1, limit=5)
    assert suggestions
    assert all(endpoint_ok(
        # rebuild is unnecessary: the suggestion text must be a finished sentence
        ScriptLine(
            id="x", segment_id="s", type="speech", speaker="sauti", voice_id="sauti",
            layer=1, emotion="warm", pace="measured", intensity=0.4,
            text=item.text, tts_text=item.text, turn_id="solo",
        ),
        None,
    )[0] for item in suggestions)
    assert any(item.paragraph == 5 and item.text.rstrip().endswith("?") for item in suggestions)

    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    report = suggest_for_spec(spec, limit=4)
    paragraphs = [item.paragraph for item in report["suggestions"]]
    assert 4 in paragraphs and 5 in paragraphs
    # ¶5 is a legal ending of the pilot; its clock matches the built episode.
    para5 = next(item for item in report["suggestions"] if item.paragraph == 5)
    built = build_episode(spec)
    assert abs(para5.at_s - built.estimated_duration_s) < 2.0
    assert built.ending["section"] == 1
    assert built.ending["paragraph"] == 5
    # At 138.1 wpm (fitted on the full render) the estimate is 337.9 s; the render measured 337.9 s.
    assert 330 < built.estimated_duration_s < 345


def test_parenthetical_glosses_are_omitted_from_tts_only(tmp_path: Path):
    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    script = build_episode(spec)
    glosses = (
        "(study and meditation in celibacy)",
        "(sages)",
        "(twice-born)",
        "(the terrible)",
    )
    for gloss in glosses:
        hits = [line for line in script.lines if gloss in line.text]
        assert hits, gloss
        for line in hits:
            assert gloss not in line.tts_text
            assert gloss in line.text
            assert "gloss_stripped" in line.flags
    vow = next(line for line in script.lines if "from this day I adopt the vow" in line.text)
    assert vow.tts_text.endswith("Brahmacharya.")

    # The global default and the episode flag both strip. Clearing the episode flag still strips.
    spec.strip_glosses = None
    assert "(sages)" not in next(line.tts_text for line in build_episode(spec).lines if "(sages)" in line.text)

    # Episode off: the gloss is spoken.
    spec.strip_glosses = False
    kept = build_episode(spec)
    assert "(sages)" in next(line.tts_text for line in kept.lines if "(sages)" in line.text)

    # Segment off keeps the opening glosses and still strips the cold open.
    spec.strip_glosses = True
    for segment in spec.segments:
        if segment.id == "opening":
            segment.strip_glosses = False
    mixed = build_episode(spec)
    assert "(sages)" in next(line.tts_text for line in mixed.lines if "(sages)" in line.text)
    assert "(the terrible)" not in next(line.tts_text for line in mixed.lines if "(the terrible)" in line.text)

    # A line override keeps one gloss. An explicit tts_text replaces the spoken line.
    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    rows = json.loads(spec.overrides_path.read_text())
    rows["overrides"].append({
        "section": 1,
        "paragraph": 2,
        "contains": "Munis",
        "strip_glosses": False,
    })
    rows["overrides"].append({
        "section": 100,
        "paragraph": 10,
        "contains": "from this day I adopt the vow",
        "tts_text": "Custom spoken vow.",
    })
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    spec.overrides_path = path
    edited = build_episode(spec)
    munis = next(line for line in edited.lines if "Munis" in line.text)
    assert "(sages)" in munis.tts_text
    assert "gloss_stripped" not in munis.flags
    custom = next(line for line in edited.lines if "from this day I adopt the vow" in line.text)
    assert custom.tts_text == "Custom spoken vow."
    assert "gloss_stripped" not in custom.flags
    assert "(study and meditation in celibacy)" in custom.text
    still = next(line for line in edited.lines if "(the terrible)" in line.text)
    assert "(the terrible)" not in still.tts_text


def test_committed_pilot_matches_the_builder():
    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    fresh = build_episode(spec)
    committed = json.loads((ROOT / "episodes" / "ep00_pilot.script.json").read_text())
    def sig(rows):
        return [(row["speaker"], row["type"], row["emotion"], row["text"], row["tts_text"], row["non_kmg"]) for row in rows]
    assert sig(line.to_dict() for line in fresh.lines) == sig(committed["lines"])
    assert abs(fresh.estimated_duration_s - committed["estimated_duration_s"]) < 0.05


def test_split_and_merge_overrides_keep_kmg_text(tmp_path):
    from mbh.episode.build import build_episode
    from mbh.episode.spec import load_spec
    spec = load_spec(ROOT / "episodes" / "ep01.yaml")
    script = build_episode(spec)
    by_text = {l.text: l for l in script.lines}
    g = by_text["I will become the writer of thy work, provided my pen do not for a moment cease writing."]
    assert g.speaker == "ganesa" and g.type == "speech" and "split" in g.flags
    assert by_text["Wherever there be anything thou dost not comprehend, cease to continue writing."].speaker == "vyasa"
    assert by_text["And Vyasa said unto that divinity,"].speaker == "sauti"
    merged = [l for l in script.lines if l.text.startswith("Ganesa having signified his assent")]
    assert len(merged) == 1 and "proceeded to write" in merged[0].text and "Om," in merged[0].tts_text
    assert not any("speaker unresolved" in w for w in script.warnings)
    ids = [l.id for l in script.lines]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)


def test_split_must_rejoin_to_source(tmp_path):
    from mbh.episode.overrides import apply_overrides
    from mbh.episode.models import ScriptLine
    line = ScriptLine(id="", segment_id="s", type="narration", speaker="sauti", voice_id="sauti", layer=1, emotion="warm",
                      pace="measured", intensity=0.4, text="He said, 'Go now.'", tts_text="He said, 'Go now.'", turn_id="t", section=1, paragraph=1)
    class FakeCast:
        def voice_id(self, s): return s
    lines = [line]
    warn = apply_overrides(lines, [{"section": 1, "paragraph": 1, "contains": "Go now", "split": [{"text": "He said,"}, {"text": "Go later."}]}], FakeCast())
    assert warn and len(lines) == 1
    warn = apply_overrides(lines, [{"section": 1, "paragraph": 1, "contains": "Go now", "split": [{"text": "He said,"}, {"text": "Go now.", "speaker": "x"}]}], FakeCast())
    assert not warn and [l.speaker for l in lines] == ["sauti", "x"]


def _section_spec(tmp_path: Path, section: int, paragraphs=None) -> Path:
    import yaml
    seg = {"id": "s", "kind": "section", "section": section, "narrator": "sauti"}
    if paragraphs:
        seg["paragraphs"] = list(paragraphs)
    spec = {"id": "t", "title": "t", "book": 1, "target_duration_s": 60, "speech_tags": "keep", "narrator_default": "sauti",
            "timing": str(ROOT / "configs" / "duration.yaml"), "lexicon": str(ROOT / "lexicon" / "book01.tsv"),
            "strip_glosses": True, "segments": [seg]}
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(spec))
    return p


def test_quote_closed_inside_an_open_paragraph_keeps_the_rest(tmp_path: Path):
    # §1 ¶23 opens inside Sauti's long quotation; "'These our pupils', said they, ..." once silently dropped the rest.
    script = build_episode(load_spec(_section_spec(tmp_path, 1, (23, 23))))
    joined = " ".join(line.text for line in script.lines)
    assert "Saying this, the Munis disappeared." in joined
    assert "are as your sons, your brothers, and your friends" in joined
    assert not [w for w in script.warnings if "TEXT LOST" in w]


def test_coverage_warning_fires_when_a_line_is_lost(tmp_path: Path, monkeypatch):
    import mbh.episode.build as build_mod
    real = build_mod._segment_lines

    def lossy(*args, **kwargs):
        made, warn = real(*args, **kwargs)
        return made[:-1], warn

    monkeypatch.setattr(build_mod, "_segment_lines", lossy)
    script = build_episode(load_spec(_section_spec(tmp_path, 1, (23, 23))))
    assert any("TEXT LOST" in w and "¶23" in w for w in script.warnings)


def test_set_type_and_confirmed_narrator_overrides(tmp_path: Path):
    import json as _json
    ov = tmp_path / "o.json"
    ov.write_text(_json.dumps({"overrides": [
        {"section": 1, "paragraph": 31, "apply_all": True, "speaker": "dhritarashtra", "set_type": "speech"},
        {"section": 1, "paragraph": 24, "contains": "They are on all accounts welcome!", "speaker": "sauti"},
        {"section": 1, "paragraph": 24, "contains": "Through divine Providence", "speaker": "sauti"},
        {"section": 1, "paragraph": 24, "contains": "Let their welcome be proclaimed!", "speaker": "sauti"},
    ]}))
    p = _section_spec(tmp_path, 1, (24, 31))
    import yaml
    d = yaml.safe_load(p.read_text()); d["overrides"] = str(ov); p.write_text(yaml.safe_dump(d))
    script = build_episode(load_spec(p))
    p31 = [l for l in script.lines if l.paragraph == 31]
    assert p31 and all(l.speaker == "dhritarashtra" and l.type == "speech" for l in p31)
    assert not [w for w in script.warnings if "unresolved" in w or "did not match" in w]
