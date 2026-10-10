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
    assert "BRAH-muh-CHAR-yuh" in vow.tts_text
    assert "Brahmacharya" in vow.text

    chorus = next(line for line in script.lines if "This one is Bhishma" in line.text)
    assert chorus.fx == "celestial"
    assert chorus.voice_id == "devas_chorus"
    assert "BHEESH-muh" in chorus.tts_text

    # Krishna-Dwaipayana in the opening is Vyasa's name, spoken as itself.
    dwaipayana = next(line for line in script.lines if "Krishna-Dwaipayana" in line.text)
    assert "Draupadi" not in dwaipayana.tts_text
    assert "KRISH-nuh dwy-PAH-yuh-nuh" in dwaipayana.tts_text

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
    import json
    excerpt = json.loads((ROOT / "proto" / "excerpt_100.json").read_text())
    timing, _engine = load_timing(ROOT / "configs" / "duration.yaml")
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
    assert 330 < built.estimated_duration_s < 360


def test_committed_pilot_matches_the_builder():
    spec = load_spec(ROOT / "episodes" / "ep00_pilot.yaml")
    fresh = build_episode(spec)
    committed = json.loads((ROOT / "episodes" / "ep00_pilot.script.json").read_text())
    def sig(rows):
        return [(row["speaker"], row["type"], row["emotion"], row["text"], row["tts_text"], row["non_kmg"]) for row in rows]
    assert sig(line.to_dict() for line in fresh.lines) == sig(committed["lines"])
    assert abs(fresh.estimated_duration_s - committed["estimated_duration_s"]) < 0.05
