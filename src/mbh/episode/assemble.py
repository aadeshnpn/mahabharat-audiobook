"""Join rendered lines with the same gaps the duration model uses; normalise each line, then master the episode (BS.1770)."""

from __future__ import annotations

from pathlib import Path

from mbh.episode import loudness
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
    normalize_lines: bool = True,
) -> dict:
    """Join lines with gaps. Each line is first brought to ``settings.loudness_lufs`` (so voices match),
    then the whole episode is mastered to the same target with a true-peak ceiling and re-measured."""
    by_id = {item.line_id: item for item in results}
    pieces: list[tuple[str, list[float]]] = []
    rate = settings.sample_rate
    target = settings.loudness_lufs
    missing: list[str] = []
    per_line: list[dict] = []
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
        samples = resample(samples, src_rate, rate)
        if normalize_lines:
            samples, info = loudness.normalize_line(samples, rate, target)
            after, _method = loudness.measure(samples, rate)
            per_line.append({"line_id": line.id, "speaker": line.speaker, "voice_id": line.voice_id,
                             "seconds": round(len(samples) / rate, 2), **info, "after": after})
        pieces.append((line.id, samples))
        prev = line
    if outro and outro.exists():
        samples, src_rate = read_mono(outro)
        pieces.append(("outro", resample(samples, src_rate, rate)))
    if not any(name not in {"gap", "intro", "outro"} for name, _samples in pieces):
        raise RuntimeError("no rendered lines to assemble; run `mbh episode render` first")
    mixed = _concat(pieces)
    mastered, master_info = loudness.master(mixed, rate, target, settings.true_peak_db)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    write_pcm16(out_wav, mastered, rate)
    final, _method = loudness.measure(read_mono(out_wav)[0], rate)  # what is actually on disk (16-bit)
    return {
        "path": str(out_wav),
        "sample_rate": rate,
        "seconds": round(len(mixed) / rate, 3),
        "loudness": "bs1770",
        "target_lufs": target,
        "true_peak_db": settings.true_peak_db,
        "measured_lufs": final,
        "master": master_info,
        "speakers": speaker_spread(per_line),
        "lines": per_line,
        "missing_lines": missing,
        "pieces": len(pieces),
    }


def speaker_spread(per_line: list[dict]) -> dict:
    """Mean loudness per speaker before and after line normalisation, plus the max-min spread."""
    out: dict = {"by_speaker": {}}
    for key in ("before", "after"):
        groups: dict[str, list[float]] = {}
        for row in per_line:
            if row.get(key) is not None:
                groups.setdefault(row["speaker"], []).append(row[key])
        means = {spk: round(sum(v) / len(v), 2) for spk, v in groups.items()}
        for spk, v in means.items():
            out["by_speaker"].setdefault(spk, {})[f"{key}_mean"] = v
        values = [row[key] for row in per_line if row.get(key) is not None]
        out[f"{key}_line_range_db"] = round(max(values) - min(values), 2) if values else None
        out[f"{key}_speaker_spread_db"] = round(max(means.values()) - min(means.values()), 2) if means else None
    return out


def _concat(pieces: list[tuple[str, list[float]]]) -> list[float]:
    out: list[float] = []
    for _name, samples in pieces:
        out.extend(samples)
    return out
