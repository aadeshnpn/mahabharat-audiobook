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
    music_cfg: dict | None = None,
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
    intervals: list[tuple[str, float, float]] = []
    cursor = 0
    if intro and intro.exists():
        samples, src_rate = read_mono(intro)
        pieces.append(("intro", resample(samples, src_rate, rate)))
        cursor += len(pieces[-1][1])
    for line in script.lines:
        item = by_id.get(line.id)
        if item is None or not item.path or item.status in {"missing_voice", "would_render"}:
            missing.append(line.id)
            prev = line
            continue
        gap = gap_before(line, prev, timing)
        if gap:
            pieces.append(("gap", _zeros(int(round(gap * rate)))))
            cursor += len(pieces[-1][1])
        samples, src_rate = read_mono(Path(item.path))
        samples = resample(samples, src_rate, rate)
        if normalize_lines:
            samples, info = loudness.normalize_line(samples, rate, target)
            after, _method = loudness.measure(samples, rate)
            per_line.append({"line_id": line.id, "speaker": line.speaker, "voice_id": line.voice_id,
                             "seconds": round(len(samples) / rate, 2), **info, "after": after})
        pieces.append((line.id, samples))
        intervals.append((line.id, cursor / rate, (cursor + len(samples)) / rate))
        cursor += len(samples)
        prev = line
    if outro and outro.exists():
        samples, src_rate = read_mono(outro)
        pieces.append(("outro", resample(samples, src_rate, rate)))
    if not any(name not in {"gap", "intro", "outro"} for name, _samples in pieces):
        raise RuntimeError("no rendered lines to assemble; run `mbh episode render` first")
    music_info = None
    if music_cfg:
        tail = float(music_cfg.get("tail_s", 4.0))
        if tail > 0 and not (outro and outro.exists()):
            pieces.append(("gap", _zeros(int(round(tail * rate)))))
    mixed = _concat(pieces)
    if music_cfg:
        mixed, music_info = _add_music(script, mixed, rate, intervals, music_cfg)
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
        "music": music_info,
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


def _add_music(script: EpisodeScript, mixed: list[float], rate: int, intervals, cfg: dict):
    """Synthesise the cue plan, mix it under the dialogue and report speech-to-music ratios."""
    import numpy as np

    from mbh.episode import music

    cues = music.resolve_cues(script.lines, cfg)
    total = len(mixed) / rate
    regions, stings = music.plan(cues, intervals, total, cfg)
    bus = music.render_music(regions, stings, [(a, b) for _i, a, b in intervals], total, rate, cfg)
    speech = np.asarray(mixed, dtype=float)
    floor = float(cfg.get("min_speech_to_music_db", 18))

    def measure_ratios():
        out = []
        for lid, a, b in intervals:
            s0, s1 = int(a * rate), int(b * rate)
            sp, _m = loudness.measure(speech[s0:s1], rate)
            mu, _m = loudness.measure(bus[s0:s1], rate) if np.any(bus[s0:s1]) else (None, "")
            out.append((lid, a, b, sp, mu))
        return out

    # the floor: wherever a line would sit closer than ``floor`` dB to the music, dip the music there
    trims = []
    gain = np.ones(len(bus))
    for lid, a, b, sp, mu in measure_ratios():
        if sp is not None and mu is not None and sp - mu < floor:
            deficit = floor - (sp - mu) + 0.5
            s0, s1 = int(max(0, a - 0.3) * rate), int(min(len(bus) / rate, b + 0.3) * rate)
            gain[s0:s1] = np.minimum(gain[s0:s1], 10 ** (-deficit / 20))
            trims.append({"line_id": lid, "trim_db": round(deficit, 1)})
    if trims:
        k = int(0.25 * rate)
        win = np.hanning(2 * k + 1); win /= win.sum()
        bus = bus * np.convolve(np.pad(gain, k, mode="edge"), win, mode="valid")
    ratios = []
    for lid, a, b in intervals:
        s0, s1 = int(a * rate), int(b * rate)
        sp, _m = loudness.measure(speech[s0:s1], rate)
        mu, _m = loudness.measure(bus[s0:s1], rate) if np.any(bus[s0:s1]) else (None, "")
        ratios.append({"line_id": lid, "speech_lufs": sp, "music_lufs": mu,
                       "ratio_db": round(sp - mu, 1) if sp is not None and mu is not None else None})
    known = [r["ratio_db"] for r in ratios if r["ratio_db"] is not None]
    info = {
        "cue_sheet": music.cue_sheet(script.lines, cues),
        "regions": [{"cue": r.cue, "start_s": round(r.start_s, 2), "end_s": round(r.end_s, 2), "intensity": r.intensity,
                     "build_to_end": r.build_to_end, "lines": [r.lines[0], r.lines[-1]]} for r in regions],
        "stings": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in st.items()} for st in stings],
        "speech_to_music_db": ratios,
        "min_speech_to_music_db": min(known) if known else None,
        "floor_db": floor,
        "floor_trims": trims,
        "intervals": [[lid, round(a, 3), round(b, 3)] for lid, a, b in intervals],
    }
    if cfg.get("stem_path"):  # music-only stem, pre-master, for review
        from mbh.episode.audioio import write_pcm16
        write_pcm16(Path(cfg["stem_path"]), bus, rate)
        info["stem_path"] = str(cfg["stem_path"])
    return speech + bus, info


def _zeros(n: int):
    try:
        import numpy as np
        return np.zeros(n)
    except ImportError:  # pragma: no cover
        return [0.0] * n


def _concat(pieces: list[tuple[str, list[float]]]):
    try:
        import numpy as np
        return np.concatenate([np.asarray(p, dtype=float) for _n, p in pieces]) if pieces else np.zeros(0)
    except ImportError:  # pragma: no cover
        pass
    out: list[float] = []
    for _name, samples in pieces:
        out.extend(samples)
    return out
