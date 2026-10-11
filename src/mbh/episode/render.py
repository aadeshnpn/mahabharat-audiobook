"""Resumable per-line renderer. The backend is pluggable; VoxCPM2 is the CPU default.

A line is cached by a hash of TTS text, instruction, voice file version, engine,
and parameters. Re-rendering an episode only synthesizes lines whose hash changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mbh.episode.audioio import write_pcm16
from mbh.episode.emotion import phrase
from mbh.episode.models import EpisodeScript, ScriptLine
from mbh.episode.paths import repo_root
from mbh.episode.timing import EngineSettings


class SynthesisBackend(Protocol):
    engine: str

    def synthesize(
        self,
        *,
        text: str,
        instruction: str,
        reference_wav: Path,
        out_wav: Path,
        params: dict,
    ) -> None:
        ...


@dataclass
class RenderResult:
    line_id: str
    cache_key: str
    status: str
    path: str | None
    speaker: str
    voice_id: str

    def to_dict(self) -> dict:
        return {
            "line_id": self.line_id,
            "cache_key": self.cache_key,
            "status": self.status,
            "path": self.path,
            "speaker": self.speaker,
            "voice_id": self.voice_id,
        }


def instruction_for(line: ScriptLine) -> str:
    pace = line.pace or "measured"
    base = f"({phrase(line.emotion)}, {pace} pace"
    if line.direction:
        base += f", {line.direction}"
    return base + ")"


def cache_key(
    line: ScriptLine,
    *,
    voice_version: str,
    engine: str,
    params: dict,
) -> str:
    payload = {
        "tts_text": line.tts_text,
        "instruction": instruction_for(line),
        "voice_id": line.voice_id,
        "voice_version": voice_version,
        "engine": engine,
        "params": params,
        "fx": line.fx,
    }
    if line.take:  # only retakes change the key, so existing cached lines stay valid
        payload["take"] = line.take
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def voice_version(path: Path | None) -> str:
    if path is None or not path.exists():
        return "missing"
    # content hash, not mtime: a git checkout or copy must not invalidate every cached line
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"sha256:{digest}"


def reference_wav(voice_id: str, voices_dir: Path | None = None) -> Path:
    root = voices_dir or (repo_root() / "voices")
    return root / voice_id / "ref.wav"


def render_script(
    script: EpisodeScript,
    backend: SynthesisBackend,
    settings: EngineSettings,
    *,
    cache_dir: Path | None = None,
    voices_dir: Path | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> list[RenderResult]:
    cache = cache_dir or (repo_root() / "build" / "cache" / backend.engine)
    cache.mkdir(parents=True, exist_ok=True)
    params = {"steps": settings.steps, "cfg_value": settings.cfg_value}
    results: list[RenderResult] = []
    lines = script.lines if limit is None else script.lines[:limit]
    for line in lines:
        ref = reference_wav(line.voice_id, voices_dir)
        version = voice_version(ref if ref.exists() else None)
        key = cache_key(line, voice_version=version, engine=backend.engine, params=params)
        dest = cache / f"{key}.wav"
        if not ref.exists():
            results.append(RenderResult(line.id, key, "missing_voice", None, line.speaker, line.voice_id))
            continue
        if dest.exists() and dest.stat().st_size > 0:
            results.append(RenderResult(line.id, key, "cached", str(dest), line.speaker, line.voice_id))
            continue
        if dry_run:
            results.append(RenderResult(line.id, key, "would_render", str(dest), line.speaker, line.voice_id))
            continue
        spoken = f"{instruction_for(line)} {line.tts_text}"
        backend.synthesize(
            text=spoken,
            instruction=instruction_for(line),
            reference_wav=ref,
            out_wav=dest,
            params={**params, "seed": line.take} if line.take else params,
        )
        sidecar = dest.with_suffix(".json")
        sidecar.write_text(json.dumps({
            "line_id": line.id,
            "speaker": line.speaker,
            "voice_id": line.voice_id,
            "instruction": instruction_for(line),
            "tts_text": line.tts_text,
            "engine": backend.engine,
            "params": params,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        results.append(RenderResult(line.id, key, "rendered", str(dest), line.speaker, line.voice_id))
    return results


class VoxCPM2Backend:
    """CPU VoxCPM2 controllable cloning. The heavy imports happen when this module loads.

    Constructing the backend does not load the model. ``synthesize`` does, once.
    """

    engine = "voxcpm2"

    def __init__(self, threads: int | None = None):
        self.threads = threads
        self._model = None
        self._write = write_pcm16

    def synthesize(self, *, text: str, instruction: str, reference_wav: Path, out_wav: Path, params: dict) -> None:
        del instruction  # already prefixed onto text by render_script
        model, sample_rate = self._load()
        if params.get("seed"):  # retakes: reproducible alternative sample
            import torch

            torch.manual_seed(int(params["seed"]))
        wav = model.generate(
            text=text,
            reference_wav_path=str(reference_wav),
            cfg_value=float(params.get("cfg_value", 2.0)),
            inference_timesteps=int(params.get("steps", 10)),
        )
        samples = [float(sample) for sample in wav]
        self._write(out_wav, samples, sample_rate)

    def _load(self):
        if self._model is not None:
            return self._model
        from mbh.episode.voxcpm2 import load_model

        self._model = load_model(self.threads)
        return self._model
