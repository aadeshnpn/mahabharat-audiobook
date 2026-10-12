"""One function per job kind. Each calls the episode library or the existing tools.

Mock mode (``MBH_STUDIO_MOCK=1`` or ``runtime.use_mock()``) never loads VoxCPM2 or Whisper.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal, cast

from mbh.episode.assemble import assemble
from mbh.episode.audioio import write_pcm16
from mbh.episode.build import build_episode
from mbh.episode.models import assert_never
from mbh.episode.paths import repo_root
from mbh.episode.render import RenderResult, render_script
from mbh.episode.spec import load_spec
from mbh.episode.timing import load_timing
from mbh.studio import playback, runtime
from mbh.studio.paths import build_dir, cache_dir, episode_yaml, manifest_path, playback_dir

JobKind = Literal["render", "rerender", "assemble", "qa", "pronunciation", "design_voice"]
JOB_KINDS = ("render", "rerender", "assemble", "qa", "pronunciation", "design_voice")
HEAVY = frozenset(JOB_KINDS)

_PRON_PATH = repo_root() / "tools" / "pronunciation" / "jobs.py"


def _pronunciation_module():
    spec = importlib.util.spec_from_file_location("mbh_pronunciation_jobs", _PRON_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_PRON_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PRON = _pronunciation_module()


def handler_for(kind: str):
    if kind not in JOB_KINDS:
        raise RuntimeError(f"unknown job kind {kind!r}; expected one of {', '.join(JOB_KINDS)}")
    return _handler(cast(JobKind, kind))


def _handler(kind: JobKind):
    if kind == "render" or kind == "rerender":
        return run_render
    if kind == "assemble":
        return run_assemble
    if kind == "qa":
        return run_qa
    if kind == "pronunciation":
        return run_pronunciation
    if kind == "design_voice":
        return run_design_voice
    assert_never(kind)


def run_render(store, job, ctx) -> None:
    episode_id = job["episode_id"]
    spec = load_spec(episode_yaml(episode_id))
    script = build_episode(spec)
    only = set(job["params"].get("only") or []) or None
    engine = runtime.backend()
    total = len([line for line in script.lines if only is None or line.id in only])

    def on_line(index: int, count: int, result: RenderResult) -> None:
        ctx.log(f"{result.status}\t{result.line_id}\t{result.voice_id}\n", progress=(index + 1) / max(count, 1),
                message=f"{result.status} {result.line_id} ({index + 1}/{count})")

    results = render_script(
        script, engine, load_timing(spec.timing_path)[1],
        cache_dir=cache_dir(engine.engine),
        dry_run=bool(job["params"].get("dry_run")),
        limit=job["params"].get("limit"),
        only=only,
        should_stop=ctx.cancelled,
        on_line=on_line,
    )
    _write_manifest(episode_id, script, results)
    counts: dict[str, int] = {}
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1
    limit = job["params"].get("limit")
    expected = total if limit is None else min(total, int(limit))
    stopped = ctx.cancelled() and len(results) < expected
    summary = {"counts": counts, "lines": len(results), "cancelled": stopped}
    _finish(store, job, "cancelled" if stopped else "done", summary, ctx)


def run_assemble(store, job, ctx) -> None:
    episode_id = job["episode_id"]
    spec = load_spec(episode_yaml(episode_id))
    script = build_episode(spec)
    path = manifest_path(episode_id)
    if not path.exists():
        raise RuntimeError("no render manifest; render the episode first")
    results = [RenderResult(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
    timing, settings = load_timing(spec.timing_path)
    out = playback.episode_wav(episode_id)
    music = job["params"].get("music")
    if music is None:
        music = bool(spec.music)
    preset = job["params"].get("music_preset") or spec.music_preset
    ctx.log(f"assembling {len(script.lines)} lines, music={bool(music)} preset={preset or 'default'}\n", progress=0.1)
    report = assemble(
        script, results, timing, settings, out,
        intro=spec.intro, outro=spec.outro,
        music_cfg=_music(spec, bool(music), preset, playback_dir(episode_id) / "music.wav" if music else None),
    )
    playback.report_path(episode_id).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    ctx.log(f"wav {report.get('seconds')} s, {report.get('measured_lufs')} LUFS\n", progress=0.8)
    mp3 = _encode_mp3(out, playback.episode_mp3(episode_id), ctx)
    summary = {"wav": str(out), "mp3": str(mp3) if mp3 else None, "seconds": report.get("seconds"),
               "measured_lufs": report.get("measured_lufs"), "missing_lines": report.get("missing_lines")}
    _finish(store, job, "done", summary, ctx)


def run_qa(store, job, ctx) -> None:
    episode_id = job["episode_id"]
    script_path = episode_yaml(episode_id).with_name(f"{episode_id}.script.json")
    manifest = manifest_path(episode_id)
    if not script_path.exists() or not manifest.exists():
        raise RuntimeError("QA needs a built script and a render manifest")
    dest = playback.qa_path(episode_id)
    if runtime.mock_enabled():
        payload = _mock_qa(script_path, manifest)
        dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        flagged = sum(1 for row in payload.values() if row.get("flags"))
        _finish(store, job, "done", {"flagged": flagged, "lines": len(payload), "mock": True, "path": str(dest)}, ctx)
        return
    python = os.environ.get("MBH_QA_PYTHON", str(repo_root() / "proto" / ".venv-pocket" / "bin" / "python"))
    if not Path(python).exists():
        raise RuntimeError(f"QA python not found at {python}; set MBH_QA_PYTHON (see docs/LOCAL_SETUP.md)")
    cmd = [python, str(repo_root() / "tools" / "qa_episode.py"), str(script_path), str(manifest), "--out", str(dest)]
    only = job["params"].get("only")
    if only:
        cmd.extend(["--only", ",".join(only)])
    ok, _log = _run_process(ctx, cmd)
    if ctx.cancelled():
        _finish(store, job, "cancelled", {"path": str(dest)}, ctx)
        return
    if not ok or not dest.exists():
        raise RuntimeError("qa_episode.py failed")
    data = json.loads(dest.read_text(encoding="utf-8"))
    flagged = sum(1 for row in data.values() if isinstance(row, dict) and row.get("flags"))
    _finish(store, job, "done", {"flagged": flagged, "lines": len(data), "path": str(dest)}, ctx)


def run_pronunciation(store, job, ctx) -> None:
    params = job["params"]
    term = str(params.get("term") or "").strip()
    if not term or "/" in term or "\\" in term:
        raise RuntimeError("term is required")
    voices = list(params.get("voices") or ["sauti"])
    formats = list(params.get("formats") or ["orig"])
    extra = {term: list(params.get("extra") or [])} if params.get("extra") else {}
    out_root = playback_dir("pron") / str(job["id"])
    planned = _PRON.plan(
        f"job{job['id']}", voices, only=[term], formats=formats, extra=extra, out_prefix=str(out_root),
    )
    if not planned:
        raise RuntimeError(f"no pronunciation forms for {term!r}")
    ctx.log(f"{len(planned)} clip(s) for {term}\n", progress=0.05, message=f"testing {term}")
    if runtime.mock_enabled():
        clips = []
        for index, item in enumerate(planned):
            if ctx.cancelled():
                break
            dest = Path(item["out"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            write_pcm16(dest, runtime.tone(freq=180 + 40 * index), 16000)
            clips.append({
                "voice": item["voice"], "fmt": item["fmt"], "form": item["form"],
                "path": str(dest), "relative": _relative_build(dest), "mock": True,
            })
            ctx.log(f"mock {item['voice']} {item['fmt']} {item['form']}\n", progress=(index + 1) / len(planned))
        status = "cancelled" if ctx.cancelled() else "done"
        _finish(store, job, status, {"term": term, "clips": clips, "mock": True}, ctx)
        return
    vox = os.environ.get("MBH_VOX_PYTHON", str(repo_root() / "proto" / ".venv-vox" / "bin" / "python"))
    if not Path(vox).exists():
        raise RuntimeError(f"VoxCPM2 python not found at {vox}; set MBH_VOX_PYTHON")
    jobs_path = out_root / "jobs.json"
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(json.dumps(planned, indent=1), encoding="utf-8")
    ok, _log = _run_process(ctx, [vox, str(repo_root() / "tools" / "pronunciation" / "synth.py"), str(jobs_path)])
    if ctx.cancelled():
        _finish(store, job, "cancelled", {"term": term, "jobs": str(jobs_path)}, ctx)
        return
    if not ok:
        raise RuntimeError("pronunciation synth failed")
    scored = False
    qa_python = os.environ.get("MBH_QA_PYTHON", str(repo_root() / "proto" / ".venv-pocket" / "bin" / "python"))
    if Path(qa_python).exists():
        scored, _log = _run_process(ctx, [qa_python, str(repo_root() / "tools" / "pronunciation" / "score.py"), str(jobs_path)])
    clips = [{"voice": item["voice"], "fmt": item["fmt"], "form": item["form"], "path": item["out"]} for item in planned]
    _finish(store, job, "done", {"term": term, "clips": clips, "scored": bool(scored),
                                 "scores": str(repo_root() / "build" / "pron" / "scores.json")}, ctx)


def run_design_voice(store, job, ctx) -> None:
    params = job["params"]
    outs = list(params.get("outs") or ([params["out"]] if params.get("out") else []))
    if not outs:
        raise RuntimeError("voice design needs an output path")
    prompt = params.get("prompt") or ""
    text = params.get("text") or ""
    steps = int(params.get("steps") or 10)
    made = []
    for index, rel in enumerate(outs):
        if ctx.cancelled():
            break
        dest = Path(rel)
        if not dest.is_absolute():
            dest = repo_root() / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        ctx.log(f"candidate {index + 1}/{len(outs)} -> {dest.name}\n", progress=index / len(outs), message=f"designing {dest.name}")
        if runtime.mock_enabled():
            write_pcm16(dest, runtime.tone(seconds=0.6, freq=160 + 30 * index), 16000)
        else:
            python = os.environ.get("MBH_VOX_PYTHON", str(repo_root() / "proto" / ".venv-vox" / "bin" / "python"))
            if not Path(python).exists():
                raise RuntimeError(f"VoxCPM2 python not found at {python}; set MBH_VOX_PYTHON")
            cmd = [python, str(repo_root() / "src" / "mbh" / "voices" / "design_one.py"),
                   "--prompt", prompt, "--text", text, "--out", str(dest), "--steps", str(steps)]
            ok, log = _run_process(ctx, cmd)
            if ctx.cancelled():
                break
            if not ok or not dest.exists():
                raise RuntimeError(log[-500:] or "voice design failed")
        made.append(str(dest.relative_to(repo_root())) if _under_repo(dest) else str(dest))
    status = "cancelled" if ctx.cancelled() else "done"
    _finish(store, job, status, {"files": made}, ctx)


def _music(spec, enabled: bool, preset: str | None, stem: Path | None):
    if not enabled:
        return None
    from mbh.episode.music import load_music_config
    path = spec.music if isinstance(spec.music, Path) else None
    cfg = load_music_config(path, preset, spec.music_rules)
    if stem is not None:
        cfg["stem_path"] = stem
    return cfg


def _encode_mp3(wav: Path, mp3: Path, ctx) -> Path | None:
    if shutil.which("ffmpeg") is None:
        ctx.log("ffmpeg not found; wav is ready, mp3 was skipped\n")
        return None
    cmd = [sys.executable, str(repo_root() / "tools" / "encode_mp3.py"), str(wav), str(mp3)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=repo_root())
    except Exception as exc:
        ctx.log(f"mp3 encode failed: {exc}\n")
        return None
    if proc.returncode != 0 or not mp3.exists():
        ctx.log((proc.stderr or proc.stdout or "mp3 encode failed")[-1000:] + "\n")
        return None
    ctx.log((proc.stdout or "").strip() + "\n", progress=0.95, message="mp3 encoded")
    return mp3


def _mock_qa(script_path: Path, manifest: Path) -> dict:
    script = json.loads(script_path.read_text(encoding="utf-8"))
    rendered = {row["line_id"]: row for row in json.loads(manifest.read_text(encoding="utf-8"))}
    out = {}
    for line in script.get("lines") or []:
        clip = rendered.get(line["id"])
        flags = []
        if not clip or not clip.get("path") or clip.get("status") in {"missing_voice", "would_render"}:
            flags.append("missing audio")
        out[line["id"]] = {
            "speaker": line.get("speaker"),
            "voice_id": line.get("voice_id"),
            "flags": flags,
            "wer": 0.0 if not flags else 1.0,
            "asr": "" if flags else line.get("tts_text"),
            "dur_s": line.get("duration_s"),
            "start_s": line.get("start_s"),
            "status": "flagged" if flags else "ok",
            "mock": True,
        }
    return out


def _write_manifest(episode_id: str, script, results: list[RenderResult]) -> None:
    path = manifest_path(episode_id)
    existing = {}
    if path.exists():
        for row in json.loads(path.read_text(encoding="utf-8")):
            existing[row["line_id"]] = row
    for item in results:
        existing[item.line_id] = item.to_dict()
    ordered = [existing[line.id] for line in script.lines if line.id in existing]
    path.write_text(json.dumps(ordered, indent=1) + "\n", encoding="utf-8")


def _finish(store, job, status: str, summary: dict, ctx) -> None:
    del ctx
    message = ctx_message(summary, status)
    fields = {"status": status, "finished": time.time(), "output": json.dumps(summary), "message": message}
    if status == "done":
        fields["progress"] = 1
    store.update_job(job["id"], **fields)


def ctx_message(summary: dict, status: str) -> str:
    if status == "cancelled":
        return "cancelled"
    if "counts" in summary:
        return " ".join(f"{key}={value}" for key, value in sorted(summary["counts"].items()))
    if "flagged" in summary:
        return f"{summary['flagged']} flagged / {summary['lines']} lines"
    if "files" in summary:
        return f"{len(summary['files'])} candidate(s)"
    if "clips" in summary:
        return f"{len(summary['clips'])} clip(s)"
    if "seconds" in summary:
        return f"{summary['seconds']} s"
    return status


def _run_process(ctx, cmd: list[str]) -> tuple[bool, str]:
    proc = subprocess.Popen(cmd, cwd=repo_root(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ctx.proc = proc
    collected: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        collected.append(line)
        ctx.log(line)
        if ctx.cancelled():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return False, "".join(collected)
    code = proc.wait()
    ctx.proc = None
    return code == 0, "".join(collected)


def _relative_build(path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(build_dir().resolve()))
    except ValueError:
        return None


def _under_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root())
        return True
    except ValueError:
        return False
