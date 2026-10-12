"""Episode Studio API and the single-worker job queue. Synthesis is mocked."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="mbh-studio-"))
os.environ["MBH_EPISODES"] = str(TMP / "episodes")
os.environ["MBH_LEXICON"] = str(TMP / "lexicon.tsv")
os.environ["MBH_BUILD"] = str(TMP / "build")
os.environ["MBH_STUDIO_MOCK"] = "1"
os.environ.setdefault("MBH_DB", str(TMP / "studio.sqlite3"))
(TMP / "episodes").mkdir()
shutil.copy(ROOT / "lexicon" / "book01.tsv", TMP / "lexicon.tsv")
_EP01 = (ROOT / "episodes" / "ep01.yaml").read_bytes()
_LEX = (ROOT / "lexicon" / "book01.tsv").read_bytes()

from fastapi.testclient import TestClient

from mbh.episode.audioio import write_pcm16
from mbh.studio import runtime
from mbh.webapp import app as appmod
from mbh.webapp import jobs as jobq

c = TestClient(appmod.app)


@pytest.fixture(autouse=True)
def _mock_backend():
    runtime.use_mock(True)
    runtime.set_backend_factory(None)
    yield
    runtime.set_backend_factory(None)
    jobq.resume_worker()


def _span(episode_id="ep_studio", paragraphs=(1, 2), bridge=None, music=False):
    segments = [{
        "id": "main", "kind": "section", "section": 1, "paragraphs": list(paragraphs),
        "narrator": "sauti", "label": "opening",
    }]
    if bridge:
        segments.append({"id": "bridge", "kind": "bridge", "speaker": "sauti", "text": bridge, "non_kmg": True})
    return {
        "id": episode_id,
        "title": "Studio test",
        "target_duration_s": 300,
        "music": music,
        "music_preset": "A",
        "speech_tags": "keep",
        "narrator_default": "sauti",
        "strip_glosses": True,
        "segments": segments,
        "end_reason": "test ending",
    }


def _wait(jid, timeout=15):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = c.get(f"/api/jobs/{jid}").json()
        if last["status"] in {"done", "failed", "cancelled"}:
            return last
        time.sleep(0.05)
    raise AssertionError(last)


def test_repo_files_stay_untouched():
    assert (ROOT / "episodes" / "ep01.yaml").read_bytes() == _EP01
    assert (ROOT / "lexicon" / "book01.tsv").read_bytes() == _LEX


def test_meta_sections_and_openapi():
    meta = c.get("/api/studio/meta").json()
    assert meta["auth"] == "none" and meta["bind_default"] == "127.0.0.1"
    assert "solemn_resolve" in meta["emotions"] and "A" in meta["music"]["presets"]
    section = c.get("/api/studio/sections/1").json()
    assert section["paragraphs"][0]["number"] == 1 and section["paragraphs"][0]["text"]
    spec = c.get("/openapi.json").json()
    assert "/api/studio/episodes" in spec["paths"]
    assert "/api/studio/episodes/{episode_id}/render" in spec["paths"]
    assert c.get("/docs").status_code == 200


def test_estimate_breaks_create_and_bridge_flag():
    body = _span("ep_create", bridge="This sentence is not in the translation.")
    est = c.post("/api/studio/estimate", json=body)
    assert est.status_code == 200, est.text
    assert est.json()["estimated_duration_s"] > 0 and est.json()["line_count"] > 1
    breaks = c.post("/api/studio/breaks", json={**body, "limit": 4})
    assert breaks.status_code == 200, breaks.text
    assert breaks.json()["suggestions"]
    made = c.post("/api/studio/episodes", json=body)
    assert made.status_code == 201, made.text
    script = c.get("/api/studio/episodes/ep_create/script").json()
    flagged = [line for line in script["lines"] if line["non_kmg"]]
    assert flagged and all("non_kmg" in line["flags"] for line in flagged)
    assert "not in the translation" in flagged[0]["text"]
    assert c.get("/api/studio/episodes/ep_create/script.md").status_code == 200
    assert c.post("/api/studio/episodes", json=body).status_code == 422


def test_override_survives_rebuild_split_and_merge():
    body = _span("ep_edit")
    assert c.post("/api/studio/episodes", json=body).status_code == 201
    script = c.get("/api/studio/episodes/ep_edit/script").json()
    line = next(row for row in script["lines"] if len(row["text"].split()) >= 6)
    edited = c.post(f"/api/studio/episodes/ep_edit/lines/{line['id']}", json={"emotion": "commanding", "tts_text": line["tts_text"]})
    assert edited.status_code == 200, edited.text
    again = c.post("/api/studio/episodes/ep_edit/build").json()
    found = next(row for row in again["lines"] if row["text"] == line["text"])
    assert found["emotion"] == "commanding" and "override" in found["flags"]
    saved = json.loads((TMP / "episodes" / "overrides" / "ep_edit.json").read_text())
    assert any(row.get("emotion") == "commanding" for row in saved["overrides"])
    assert c.post(f"/api/studio/episodes/ep_edit/lines/{found['id']}", json={"emotion": "not-an-emotion"}).status_code == 422
    words = found["text"].split()
    assert len(words) >= 2
    mid = max(1, len(words) // 2)
    parts = [" ".join(words[:mid]), " ".join(words[mid:])]
    split = c.post(f"/api/studio/episodes/ep_edit/lines/{found['id']}/split", json={"parts": [{"text": parts[0]}, {"text": parts[1], "speaker": "sauti"}]})
    assert split.status_code == 200, split.text
    assert split.json()["line_count"] == again["line_count"] + 1
    bad = c.post(f"/api/studio/episodes/ep_edit/lines/{split.json()['lines'][0]['id']}/split", json={"parts": [{"text": "nope"}, {"text": "still nope"}]})
    assert bad.status_code == 422
    merged = c.post(f"/api/studio/episodes/ep_edit/lines/{split.json()['lines'][0]['id']}/merge")
    assert merged.status_code == 200, merged.text
    assert merged.json()["line_count"] == split.json()["line_count"] - 1


def test_render_assemble_playback_and_qa():
    assert c.post("/api/studio/episodes", json=_span("ep_play")).status_code == 201
    job = _wait(c.post("/api/studio/episodes/ep_play/render", json={}).json()["id"])
    assert job["status"] == "done", job
    counts = json.loads(job["output"])["counts"]
    assert counts.get("rendered", 0) + counts.get("cached", 0) >= 1
    script = c.get("/api/studio/episodes/ep_play/script").json()
    audible = next(line for line in script["lines"] if line["has_audio"])
    audio = c.get(f"/api/studio/episodes/ep_play/lines/{audible['id']}/audio")
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    # second render of one line is a cache hit
    again = _wait(c.post("/api/studio/episodes/ep_play/render", json={"only": [audible["id"]]}).json()["id"])
    assert json.loads(again["output"])["counts"].get("cached") == 1
    assembled = _wait(c.post("/api/studio/episodes/ep_play/assemble", json={"music": False}).json()["id"])
    assert assembled["status"] == "done", assembled
    wav = c.get("/api/studio/episodes/ep_play/episode.wav")
    assert wav.status_code == 200 and wav.content[:4] == b"RIFF"
    wave = c.get("/api/studio/episodes/ep_play/waveform").json()
    assert wave["peaks"] and wave["seconds"] > 0 and wave["timeline"]
    qa = _wait(c.post("/api/studio/episodes/ep_play/qa", json={}).json()["id"])
    assert qa["status"] == "done", qa
    report = c.get("/api/studio/episodes/ep_play/qa").json()
    assert report["status"] == "ready" and audible["id"] in report["lines"]
    assert report["lines"][audible["id"]]["flags"] == []


def test_one_heavy_job_at_a_time_and_cancel():
    assert c.post("/api/studio/episodes", json=_span("ep_gate", paragraphs=(1, 3))).status_code == 201
    gate = _Gate()
    runtime.set_backend_factory(lambda: gate)
    first = c.post("/api/studio/episodes/ep_gate/render", json={}).json()["id"]
    second = c.post("/api/studio/episodes/ep_gate/render", json={}).json()["id"]
    assert gate.entered.wait(5)
    assert gate.max_inside == 1
    assert c.get(f"/api/jobs/{second}").json()["status"] == "queued"
    gate.release.set()
    assert _wait(first)["status"] == "done"
    assert _wait(second)["status"] == "done"
    assert gate.max_inside == 1

    runtime.set_backend_factory(lambda: _Gate(block=False, engine="cancelgate"))
    assert c.post("/api/studio/episodes", json=_span("ep_cancel", paragraphs=(1, 3))).status_code == 201
    blocker = _Gate()
    blocker.engine = "cancelgate"
    runtime.set_backend_factory(lambda: blocker)
    jid = c.post("/api/studio/episodes/ep_cancel/render", json={}).json()["id"]
    assert blocker.entered.wait(5)
    assert c.post(f"/api/jobs/{jid}/cancel").status_code == 200
    blocker.release.set()
    cancelled = _wait(jid)
    assert cancelled["status"] == "cancelled", cancelled
    assert 0 < blocker.calls < c.get("/api/studio/episodes/ep_cancel/script").json()["line_count"]


def test_restart_requeues_and_cache_resumes():
    assert c.post("/api/studio/episodes", json=_span("ep_resume")).status_code == 201
    assert _wait(c.post("/api/studio/episodes/ep_resume/render", json={}).json()["id"])["status"] == "done"
    jobq.pause_worker()
    time.sleep(0.4)
    jid = c.post("/api/studio/episodes/ep_resume/render", json={}).json()["id"]
    appmod.store.update_job(jid, status="running", message="crashed")
    assert appmod.store.recover_jobs() == 1
    assert c.get(f"/api/jobs/{jid}").json()["status"] == "queued"
    jobq.resume_worker()
    done = _wait(jid)
    assert done["status"] == "done", done
    assert json.loads(done["output"])["counts"].get("cached", 0) >= 1
    assert json.loads(done["output"])["counts"].get("rendered", 0) in (None, 0)


def test_lexicon_edit_and_pronunciation_job():
    before = (ROOT / "lexicon" / "book01.tsv").read_bytes()
    saved = c.put("/api/studio/lexicon", json={
        "term": "StudioName", "respelling": "STOO-dee-oh", "spoken": "Studioh", "verified": 1, "notes": "test",
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["verified"] == 1 and saved.json()["spoken"] == "Studioh"
    assert c.put("/api/studio/lexicon", json={"term": "NoSpoken", "respelling": "NO", "verified": 1}).status_code == 422
    found = c.get("/api/studio/lexicon?q=StudioName").json()
    assert found and found[0]["term"] == "StudioName"
    job = _wait(c.post("/api/studio/lexicon/test", json={"term": "StudioName", "voices": ["sauti"], "formats": ["orig"]}).json()["id"])
    assert job["status"] == "done", job
    clip = json.loads(job["output"])["clips"][0]
    assert clip["relative"]
    audio = c.get("/api/studio/media", params={"path": clip["relative"]})
    assert audio.status_code == 200 and audio.content[:4] == b"RIFF"
    assert c.get("/api/studio/media", params={"path": "../etc/passwd"}).status_code == 404
    assert (ROOT / "lexicon" / "book01.tsv").read_bytes() == before


def test_voice_design_job_and_select():
    assert c.post("/api/characters", json={"name": "Studio Voice", "voice_brief": "A clear aged sage, Indian English accent", "sample_line": "Hear this voice."}).status_code == 201
    job = _wait(c.post("/api/studio/voices/studio_voice/design", json={"n": 2}).json()["id"])
    assert job["status"] == "done", job
    files = json.loads(job["output"])["files"]
    assert len(files) == 2
    listed = c.get("/api/characters/studio_voice/voice/candidates").json()
    assert len(listed) == 2
    chosen = c.post("/api/characters/studio_voice/voice/select", json={"file": files[0]})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["voice_clip"].endswith("ref.wav")
    assert c.get("/voices/studio_voice/ref.wav").status_code == 200
    c.delete("/api/characters/studio_voice?delete_voice_files=true")


def test_partial_wav_is_not_a_cache_hit(tmp_path):
    from mbh.episode.models import EpisodeScript, ScriptLine
    from mbh.episode.render import render_script
    from mbh.episode.timing import EngineSettings

    ref = tmp_path / "voices" / "sauti"
    ref.mkdir(parents=True)
    write_pcm16(ref / "ref.wav", [0.1, -0.1], 8000)
    line = ScriptLine(
        id="ep-0001", segment_id="s", type="narration", speaker="sauti", voice_id="sauti",
        layer=1, emotion="warm", pace="measured", intensity=0.4, text="Hello there.", tts_text="Hello there.",
        turn_id="t", section=1, paragraph=1,
    )
    script = EpisodeScript("ep", "t", 1, 30, 1, {}, [line])

    class Boom:
        engine = "boom"
        def synthesize(self, **kwargs):
            write_pcm16(kwargs["out_wav"], [0.2], 8000)
            raise RuntimeError("killed mid write")

    with pytest.raises(RuntimeError):
        render_script(script, Boom(), EngineSettings(), cache_dir=tmp_path / "cache", voices_dir=tmp_path / "voices")
    assert not list((tmp_path / "cache").glob("*.wav"))
    assert list((tmp_path / "cache").glob("*.partial.wav")) == []


class _Gate:
    def __init__(self, block=True, engine="gate"):
        self.engine = engine
        self.block = block
        self.calls = 0
        self.inside = 0
        self.max_inside = 0
        self.entered = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()

    def synthesize(self, *, text, instruction, reference_wav, out_wav, params):
        del text, instruction, reference_wav, params
        with self.lock:
            self.inside += 1
            self.calls += 1
            self.max_inside = max(self.max_inside, self.inside)
            first = self.calls == 1
        if first and self.block:
            self.entered.set()
            assert self.release.wait(5)
        with self.lock:
            self.inside -= 1
        write_pcm16(out_wav, runtime.tone(), 16000)
