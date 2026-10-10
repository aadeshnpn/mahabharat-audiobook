"""Join rendered lines with the same gaps the duration model uses, then normalize loudness."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from mbh.episode.audioio import read_mono, resample, write_pcm16
from mbh.episode.models import EpisodeScript, ScriptLine
from mbh.episode.render import RenderResult
from mbh.episode.timing import EngineSettings, Timing, gap_before


def assemble(
    script: EpisodeScript,
    results: list[RenderResult],
    timing: Timing,
    settings: EngineSettings,
    out_wav: Path,
    *,
    intro: Path | None = None,
    outro: Path | None = None,
) -> dict:
    by_id = {item.line_id: item for item in results}
    pieces: list[tuple[str, list[float]]] = []
    rate = settings.sample_rate
    missing: list[str] = []
    prev: ScriptLine | None = None
    if intro and intro.exists():
        samples, src_rate = read_mono(intro)
        pieces.append(("intro", resample(samples, src_rate, rate)))
    for line in script.lines:
        item = by_id.get(line.id)
        if item is None or not item.path or item.status in {"missing_voice", "would_render"}:
            missing.append(line.id)
            prev = line
            continue
        gap = gap_before(line, prev, timing)
        if gap:
            pieces.append(("gap", [0.0] * int(round(gap * rate))))
        samples, src_rate = read_mono(Path(item.path))
        pieces.append((line.id, resample(samples, src_rate, rate)))
        prev = line
    if outro and outro.exists():
        samples, src_rate = read_mono(outro)
        pieces.append(("outro", resample(samples, src_rate, rate)))
    if not any(name not in {"gap", "intro", "outro"} for name, _samples in pieces):
        raise RuntimeError("no rendered lines to assemble; run `mbh episode render` first")
    mixed = _concat(pieces)
    peak = _peak_normalize(mixed, db=settings.true_peak_db)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    raw_path = out_wav.with_suffix(".raw.wav")
    write_pcm16(raw_path, peak, rate)
    loudness = "peak"
    if shutil.which("ffmpeg"):
        _ffmpeg_loudnorm(raw_path, out_wav, settings)
        loudness = "lufs"
        raw_path.unlink(missing_ok=True)
    else:
        raw_path.replace(out_wav)
    return {
        "path": str(out_wav),
        "sample_rate": rate,
        "seconds": round(len(mixed) / rate, 3),
        "loudness": loudness,
        "missing_lines": missing,
        "pieces": len(pieces),
    }


def _concat(pieces: list[tuple[str, list[float]]]) -> list[float]:
    out: list[float] = []
    for _name, samples in pieces:
        out.extend(samples)
    return out


def _peak_normalize(samples: list[float], db: float) -> list[float]:
    peak = max((abs(sample) for sample in samples), default=0.0)
    if peak == 0:
        return list(samples)
    target = 10 ** (db / 20.0)
    gain = target / peak
    return [sample * gain for sample in samples]


def _ffmpeg_loudnorm(src: Path, dest: Path, settings: EngineSettings) -> None:
    filt = f"loudnorm=I={settings.loudness_lufs}:TP={settings.true_peak_db}:LRA=11"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", filt, "-ar", str(settings.sample_rate), str(dest)],
        check=True,
    )
