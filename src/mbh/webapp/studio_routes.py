"""REST API for Episode Studio. The same operations the UI calls.

OpenAPI: ``/docs``. A full curl walkthrough lives in ``docs/STUDIO.md``.
There is no authentication. The process should listen on localhost.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from mbh.studio import catalog, episodes, lexicon_io, playback
from mbh.studio.episodes import StudioError
from mbh.studio.lexicon_io import LexiconError
from mbh.studio.paths import overrides_path, script_markdown
from mbh.studio.runtime import mock_enabled
from mbh.webapp import jobs
from mbh.webapp.db import ROOT

router = APIRouter(prefix="/api/studio", tags=["studio"])
job_router = APIRouter(tags=["jobs"])


class SegmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    kind: Literal["section", "bridge"]
    label: str = ""
    note: str = ""
    section: int | None = None
    paragraphs: list[int] | None = Field(default=None, description="Inclusive paragraph range, [start, end].")
    narrator: str | None = None
    excerpt: bool = False
    speaker: str | None = None
    emotion: str | None = None
    pace: str | None = None
    text: str = ""
    non_kmg: bool | None = Field(default=None, description="Bridges are not in KMG and must stay true.")


class EpisodeIn(BaseModel):
    """A new episode, or a draft sent to estimate/breaks before it is saved."""

    model_config = ConfigDict(extra="forbid")
    id: str | None = Field(default=None, description="Lowercase id, e.g. ep02. Required when creating.")
    title: str = ""
    book: int = 1
    target_duration_s: float = 1050
    speech_tags: Literal["keep", "drop"] = "keep"
    narrator_default: str = "sauti"
    strip_glosses: bool = True
    music: bool | str = True
    music_preset: str | None = "A"
    music_rules: list[dict] = []
    summary: str = ""
    end_reason: str = ""
    notes: list[str] = []
    segments: list[SegmentIn]


class EpisodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    book: int | None = None
    target_duration_s: float | None = None
    speech_tags: Literal["keep", "drop"] | None = None
    narrator_default: str | None = None
    strip_glosses: bool | None = None
    music: bool | str | None = None
    music_preset: str | None = None
    music_rules: list[dict] | None = None
    summary: str | None = None
    end_reason: str | None = None
    notes: list[str] | None = None
    segments: list[SegmentIn] | None = None


class BreaksIn(BaseModel):
    """Either a draft episode (segments) or one section and a target.

    A draft may carry the same fields as EpisodeIn so the create form can
    send one body to estimate and to breaks.
    """

    model_config = ConfigDict(extra="forbid")
    id: str | None = None
    title: str = "draft"
    book: int = 1
    segments: list[SegmentIn] | None = None
    target_duration_s: float | None = None
    speech_tags: Literal["keep", "drop"] = "keep"
    narrator_default: str = "sauti"
    strip_glosses: bool = True
    music: bool | str = True
    music_preset: str | None = None
    music_rules: list[dict] = []
    summary: str = ""
    end_reason: str = ""
    notes: list[str] = []
    section: int | None = None
    target_seconds: float | None = None
    start_paragraph: int = 1
    narrator: str = "sauti"
    limit: int = 5


class LineEdit(BaseModel):
    """Fields written into the overrides file. Null clears a field. Omitted fields stay as they are."""

    model_config = ConfigDict(extra="forbid")
    speaker: str | None = None
    emotion: str | None = None
    pace: str | None = None
    tts_text: str | None = None
    music: str | dict | None = None
    take: int | None = None
    direction: str | None = None
    intensity: float | None = None
    fx: str | None = None
    addressee: str | None = None
    type: str | None = None


class SplitPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    speaker: str | None = None
    type: str | None = None
    emotion: str | None = None
    pace: str | None = None
    direction: str | None = None
    tts_text: str | None = None


class SplitIn(BaseModel):
    parts: list[SplitPart]


class OverridesIn(BaseModel):
    overrides: list[dict]


class RenderIn(BaseModel):
    only: list[str] | None = Field(default=None, description="Line ids to re-render. Omit to render every line; cached lines are skipped.")
    limit: int | None = None
    dry_run: bool = False


class AssembleIn(BaseModel):
    music: bool | None = Field(default=None, description="Null follows the episode YAML.")
    music_preset: str | None = None


class QaIn(BaseModel):
    only: list[str] | None = None


class LexiconIn(BaseModel):
    term: str
    respelling: str = Field(description="Human guide. Capitals mark stress. Never sent to the TTS engine.")
    spoken: str = ""
    ipa: str = ""
    source: str = "studio"
    verified: int = 0
    notes: str = ""


class PronounceIn(BaseModel):
    term: str
    voices: list[str] = ["sauti"]
    formats: list[str] = ["orig"]
    extra: list[str] = Field(default_factory=list, description="Extra spoken forms to try, in addition to formats.")


class DesignIn(BaseModel):
    n: int = Field(default=1, ge=1, le=8)
    steps: int = Field(default=10, ge=1, le=30)
    prompt: str | None = None
    text: str | None = None


def _store():
    # Imported lazily: this router is loaded by mbh.webapp.app, which owns the Store.
    from mbh.webapp.app import store
    return store


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc) or "not found") from exc
    except (StudioError, LexiconError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


def _dump(model: BaseModel) -> dict:
    return model.model_dump(exclude_unset=True)


@router.get("/meta", summary="Vocabularies, music presets, and the local-only security note")
def meta():
    music = catalog.music_meta()
    running = [job for job in _store().list_jobs(limit=20) if job["status"] == "running"]
    queued = [job for job in _store().list_jobs(limit=50) if job["status"] == "queued"]
    return {
        "emotions": catalog.emotions(),
        "paces": catalog.paces(),
        "music": music,
        "auth": "none",
        "bind_default": "127.0.0.1",
        "mock_synthesis": mock_enabled(),
        "queue": {
            "running": running[0]["id"] if running else None,
            "queued": len(queued),
            "note": "One heavy job at a time (render, assemble, QA, pronunciation, voice design).",
        },
    }


@router.get("/sections", summary="Book 1 sections and how many paragraphs each has")
def sections():
    return _call(catalog.list_sections)


@router.get("/sections/{section}", summary="Paragraph text for one section, for the range picker")
def section(section: int):
    try:
        return catalog.section_detail(section)
    except StopIteration as exc:
        raise HTTPException(404, f"no section {section}") from exc


@router.get("/cast", summary="Speakers the line editor can assign")
def cast():
    return episodes.cast_options()


@router.post("/estimate", summary="Duration of a draft episode; nothing is saved")
def estimate(body: EpisodeIn):
    return _call(episodes.estimate, body.model_dump())


@router.post("/breaks", summary="Legal episode endings near the target duration")
def breaks(body: BreaksIn):
    payload = body.model_dump()
    limit = payload.pop("limit", 5)
    return _call(episodes.breaks, payload, limit=limit)


@router.get("/episodes", summary="Episodes on disk")
def list_episodes():
    return episodes.list_episodes()


@router.post("/episodes", status_code=201, summary="Create an episode YAML and an empty overrides file")
def create_episode(body: EpisodeIn):
    if not body.id:
        raise HTTPException(422, "id is required")
    return _call(episodes.create_episode, body.model_dump())


@router.get("/episodes/{episode_id}", summary="Episode spec, summary, and overrides")
def get_episode(episode_id: str):
    return _call(episodes.get_episode, episode_id)


@router.put("/episodes/{episode_id}", summary="Update the span, title, or music settings")
def update_episode(episode_id: str, body: EpisodeUpdate):
    return _call(episodes.update_episode, episode_id, _dump(body))


@router.delete("/episodes/{episode_id}", summary="Delete the episode YAML, overrides, and studio playback files")
def delete_episode(episode_id: str):
    return _call(episodes.delete_episode, episode_id)


@router.post("/episodes/{episode_id}/build", summary="Rebuild the script. Overrides are reapplied.")
def build_episode(episode_id: str):
    return _call(episodes.build_saved, episode_id)


@router.get("/episodes/{episode_id}/script", summary="Line table: speaker, emotion, TTS text, music cue, audio")
def get_script(episode_id: str):
    return _call(episodes.script_view, episode_id)


@router.get("/episodes/{episode_id}/script.md", summary="Review Markdown, the same file the CLI writes")
def get_markdown(episode_id: str):
    _call(episodes.get_episode, episode_id)
    path = script_markdown(episode_id)
    if not path.exists():
        _call(episodes.build_saved, episode_id)
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@router.get("/episodes/{episode_id}/overrides", summary="Raw overrides file")
def get_overrides(episode_id: str):
    data = _call(episodes.get_episode, episode_id)
    return {"overrides": data["overrides"]}


@router.put("/episodes/{episode_id}/overrides", summary="Replace the overrides file, then rebuild")
def put_overrides(episode_id: str, body: OverridesIn):
    path = overrides_path(episode_id)
    _call(episodes.get_episode, episode_id)
    path.write_text(json.dumps({"overrides": body.overrides}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return _call(episodes.build_saved, episode_id)


@router.post("/episodes/{episode_id}/lines/{line_id}", summary="Edit one line via an override, then rebuild")
def edit_line(episode_id: str, line_id: str, body: LineEdit):
    return _call(episodes.edit_line, episode_id, line_id, _dump(body))


@router.post("/episodes/{episode_id}/lines/{line_id}/split", summary="Split a line. Parts must re-join to the KMG text.")
def split_line(episode_id: str, line_id: str, body: SplitIn):
    return _call(episodes.split_line, episode_id, line_id, [part.model_dump(exclude_none=True) for part in body.parts])


@router.post("/episodes/{episode_id}/lines/{line_id}/merge", summary="Merge this line with the next one")
def merge_line(episode_id: str, line_id: str):
    return _call(episodes.merge_line, episode_id, line_id)


@router.delete("/episodes/{episode_id}/lines/{line_id}/override", summary="Drop overrides that match this line, then rebuild")
def clear_override(episode_id: str, line_id: str):
    return _call(episodes.clear_line_override, episode_id, line_id)


@router.post("/episodes/{episode_id}/render", status_code=202, summary="Queue a render. Cached lines are skipped.")
def render_episode(episode_id: str, body: RenderIn | None = Body(default=None)):
    _call(episodes.get_episode, episode_id)
    params = (body or RenderIn()).model_dump()
    return jobs.enqueue(_store(), kind="render" if not params.get("only") else "rerender", params=params, episode_id=episode_id)


@router.post("/episodes/{episode_id}/assemble", status_code=202, summary="Queue assembly, optional music, and an MP3")
def assemble_episode(episode_id: str, body: AssembleIn | None = Body(default=None)):
    _call(episodes.get_episode, episode_id)
    params = (body or AssembleIn()).model_dump(exclude_none=True)
    return jobs.enqueue(_store(), kind="assemble", params=params, episode_id=episode_id)


@router.post("/episodes/{episode_id}/qa", status_code=202, summary="Queue episode QA")
def qa_episode(episode_id: str, body: QaIn | None = Body(default=None)):
    _call(episodes.get_episode, episode_id)
    params = (body or QaIn()).model_dump(exclude_none=True)
    return jobs.enqueue(_store(), kind="qa", params=params, episode_id=episode_id)


@router.get("/episodes/{episode_id}/waveform", summary="Peaks plus per-line spans for the player")
def waveform(episode_id: str, buckets: int = Query(900, ge=50, le=4000)):
    return _call(playback.waveform, episode_id, buckets)


@router.get("/episodes/{episode_id}/qa", summary="QA report, or status none if it has not been run")
def get_qa(episode_id: str):
    _call(episodes.get_episode, episode_id)
    return playback.qa_report(episode_id)


@router.get("/episodes/{episode_id}/lines/{line_id}/audio", summary="Rendered wav for one line")
def line_audio(episode_id: str, line_id: str):
    path = _call(playback.line_audio, episode_id, line_id)
    return FileResponse(path, media_type="audio/wav", filename=f"{line_id}.wav")


@router.get("/episodes/{episode_id}/episode.wav", summary="Assembled episode wav")
def episode_wav(episode_id: str):
    path = playback.episode_wav(episode_id)
    if not path.exists():
        raise HTTPException(404, "episode is not assembled yet")
    return FileResponse(path, media_type="audio/wav", filename=f"{episode_id}.wav")


@router.get("/episodes/{episode_id}/episode.mp3", summary="Assembled episode MP3")
def episode_mp3(episode_id: str):
    path = playback.episode_mp3(episode_id)
    if not path.exists():
        raise HTTPException(404, "mp3 is not ready; assemble the episode (ffmpeg is required)")
    return FileResponse(path, media_type="audio/mpeg", filename=f"{episode_id}.mp3")


@router.get("/lexicon", summary="Pronunciation lexicon rows")
def lexicon(q: str = "", verified: str = ""):
    found = lexicon_io.rows()
    if q:
        needle = q.casefold()
        found = [row for row in found if needle in row["term"].casefold() or needle in row["spoken"].casefold() or needle in row["respelling"].casefold()]
    if verified in {"0", "1"}:
        found = [row for row in found if str(row["verified"]) == verified]
    return found


@router.put("/lexicon", summary="Create or update one lexicon row, including verified")
def put_lexicon(body: LexiconIn):
    return _call(lexicon_io.upsert, body.model_dump())


@router.post("/lexicon/test", status_code=202, summary="Queue a pronunciation test for one name")
def test_lexicon(body: PronounceIn):
    return jobs.enqueue(_store(), kind="pronunciation", params=body.model_dump(), character_id=None, episode_id=None)


@router.get("/media", summary="Play a file written under the build directory (pronunciation clips)")
def media(path: str):
    return FileResponse(_call(playback.resolve_build_file, path))


@router.get("/voices", summary="Characters, briefs, reference clips, and candidate counts")
def voices(q: str = ""):
    rows = []
    for char in _store().list_characters():
        if q and q.casefold() not in char["name"].casefold() and q.casefold() not in char["id"]:
            continue
        folder = ROOT / "voices" / char["id"] / "candidates"
        rows.append({
            "id": char["id"],
            "name": char["name"],
            "voice_brief": char.get("voice_brief") or "",
            "voice_prompt": char.get("voice_prompt") or "",
            "sample_line": char.get("sample_line") or "",
            "voice_clip": char.get("voice_clip") or "",
            "voice_group": char.get("voice_group") or "",
            "candidates": sorted(p.name for p in folder.glob("*.wav")) if folder.exists() else [],
        })
    return rows


@router.post("/voices/{character_id}/design", status_code=202, summary="Queue voice-design candidates from the character brief")
def design_voice(character_id: str, body: DesignIn | None = Body(default=None)):
    char = _store().get_character(character_id)
    if not char:
        raise HTTPException(404, f"character {character_id!r} not found")
    spec = body or DesignIn()
    prompt = spec.prompt or char.get("voice_prompt") or char.get("voice_brief")
    text = spec.text or char.get("sample_line") or ""
    if not prompt:
        raise HTTPException(422, "no prompt or voice brief")
    if not text:
        text = "Hear this voice, clear and steady."
    vox = os.environ.get("MBH_VOX_PYTHON", str(ROOT / "proto/.venv-vox/bin/python"))
    if not mock_enabled() and not Path(vox).exists():
        raise HTTPException(503, f"VoxCPM2 python not found at {vox}; set MBH_VOX_PYTHON")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    folder = ROOT / "voices" / character_id / "candidates"
    folder.mkdir(parents=True, exist_ok=True)
    outs = [str((folder / f"cand_{stamp}_{index}.wav").relative_to(ROOT)) for index in range(spec.n)]
    return jobs.enqueue(
        _store(), kind="design_voice", character_id=character_id,
        params={"prompt": prompt, "text": text, "steps": spec.steps, "n": spec.n, "outs": outs},
    )


@job_router.post("/api/jobs/{jid}/cancel", summary="Cancel a queued or running job")
def cancel_job(jid: int):
    job = jobs.cancel(_store(), jid)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@job_router.get("/api/jobs/{jid}/log", summary="Plain-text log for a job")
def job_log(jid: int):
    job = _store().get_job(jid)
    if not job:
        raise HTTPException(404, "job not found")
    return PlainTextResponse(job.get("log") or "")
