"""Waveforms, assemble reports, and QA files for the episode player."""

from __future__ import annotations

import array
import json
import sys
import wave
from pathlib import Path

from mbh.episode.paths import repo_root
from mbh.studio.paths import build_dir, manifest_path, playback_dir, script_json


def episode_wav(episode_id: str) -> Path:
    return playback_dir(episode_id) / "episode.wav"


def episode_mp3(episode_id: str) -> Path:
    return playback_dir(episode_id) / "episode.mp3"


def report_path(episode_id: str) -> Path:
    return playback_dir(episode_id) / "assemble.json"


def qa_path(episode_id: str) -> Path:
    return playback_dir(episode_id) / "qa.json"


def waveform(episode_id: str, buckets: int = 900) -> dict:
    wav = episode_wav(episode_id)
    if not wav.exists():
        raise FileNotFoundError(episode_id)
    cache = playback_dir(episode_id) / f"peaks_{buckets}.json"
    if cache.exists() and cache.stat().st_mtime >= wav.stat().st_mtime:
        payload = json.loads(cache.read_text(encoding="utf-8"))
    else:
        payload = _peaks(wav, buckets)
        cache.write_text(json.dumps(payload), encoding="utf-8")
    payload["timeline"] = _timeline(episode_id)
    payload["qa"] = _qa_flags(episode_id)
    return payload


def qa_report(episode_id: str) -> dict:
    path = qa_path(episode_id)
    if not path.exists():
        return {"episode_id": episode_id, "status": "none", "lines": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"episode_id": episode_id, "status": "ready", "lines": data}


def line_audio(episode_id: str, line_id: str) -> Path:
    path = manifest_path(episode_id)
    if not path.exists():
        raise FileNotFoundError(line_id)
    rows = json.loads(path.read_text(encoding="utf-8"))
    match = next((row for row in rows if row.get("line_id") == line_id), None)
    if not match or not match.get("path"):
        raise FileNotFoundError(line_id)
    audio = Path(match["path"])
    if not audio.is_file() or not _allowed(audio):
        raise FileNotFoundError(line_id)
    return audio


def resolve_build_file(relative: str) -> Path:
    """A file under the build directory. Rejects paths that climb out of it."""
    root = build_dir().resolve()
    path = (root / relative).resolve()
    if not _under(path, root) or not path.is_file():
        raise FileNotFoundError(relative)
    return path


def _timeline(episode_id: str) -> list[dict]:
    report = report_path(episode_id)
    spans = {}
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        spans = {row["line_id"]: row for row in data.get("timeline") or []}
    script_file = script_json(episode_id)
    if not script_file.exists():
        return list(spans.values())
    script = json.loads(script_file.read_text(encoding="utf-8"))
    rows = []
    for line in script.get("lines") or []:
        span = spans.get(line["id"]) or {}
        rows.append({
            "line_id": line["id"],
            "speaker": line.get("speaker"),
            "start_s": span.get("start_s", line.get("start_s")),
            "end_s": span.get("end_s"),
            "text": (line.get("text") or "")[:140],
            "non_kmg": bool(line.get("non_kmg")),
        })
    return rows


def _qa_flags(episode_id: str) -> dict:
    path = qa_path(episode_id)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        line_id: {"flags": row.get("flags") or [], "wer": row.get("wer"), "start_s": row.get("start_s")}
        for line_id, row in data.items()
        if isinstance(row, dict)
    }


def _peaks(path: Path, buckets: int) -> dict:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        raw = handle.readframes(frames)
    if width != 2:
        raise ValueError(f"{path.name} is not 16-bit PCM")
    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if channels > 1:
        samples = array.array("h", (samples[index] for index in range(0, len(samples), channels)))
    buckets = max(1, min(int(buckets), 4000))
    step = max(1, len(samples) // buckets)
    peaks = []
    for start in range(0, len(samples), step):
        chunk = samples[start:start + step]
        peak = max((abs(sample) for sample in chunk), default=0)
        peaks.append(round(peak / 32768, 4))
    return {"buckets": len(peaks), "peaks": peaks, "seconds": round(frames / rate, 3) if rate else 0, "sample_rate": rate}


def _allowed(path: Path) -> bool:
    return _under(path, build_dir()) or _under(path, repo_root() / "build") or _under(path, repo_root() / "voices")


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
