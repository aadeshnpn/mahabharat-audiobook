#!/usr/bin/env python3
"""Swap the title (intro) and ending (outro) of an already-assembled episode without re-rendering any TTS.

The episode must have been assembled by mbh.episode.assemble: [intro][2.5 s equal-power xf][body + music tail][xf][outro],
then mastered (gain + sparse peak limiter). This tool:
  1. decodes the episode (wav/mp3, any rate) to mono at the project rate,
  2. finds the old intro and old outro by FFT cross-correlation, and estimates the master gain on each,
  3. removes them, including their share of each crossfade (subtracting g * old * fade-curve), so no remnant is left,
  4. splices the new intro/outro in with the same crossfade curves and placement as assemble.py,
  5. re-masters to the target LUFS / true-peak (mbh.episode.loudness.master) and writes wav (+ mp3 if --mp3).

usage:
  PYTHONPATH=src python3 tools/swap_intro_outro.py IN.(mp3|wav) OUT.wav \
      --old-intro assets/intro/title_song_v5_krishna.wav --new-intro assets/intro/title_song_v6_sting.wav \
      --old-outro assets/outro/ending_v2_krishna.wav --new-outro assets/outro/ending_v6_sting.wav \
      [--intro-xf 2.5] [--outro-xf 2.5] [--lufs -16] [--true-peak -1.5] [--mp3 OUT.mp3] [--report OUT.json]
Defaults for the new assets / crossfades come from configs/intros.yaml (title_song) and configs/outros.yaml (ending_song).
"""
from __future__ import annotations

import argparse, json, math, subprocess, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mbh.episode import loudness  # noqa: E402
from mbh.episode.audioio import read_mono, resample, write_pcm16  # noqa: E402

RATE = 48000


def decode(path: Path, rate: int = RATE) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(float)


def ebur128(path: Path) -> tuple[float, float]:
    """(integrated LUFS, true peak dBFS) as measured by ffmpeg's ebur128 filter."""
    import re
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr.split("Summary:")[-1]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", err).group(1)), float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", err).group(1))


def asset(path: Path, rate: int = RATE) -> np.ndarray:
    s, r = read_mono(path)  # same mono downmix + resample as assemble.py
    return np.asarray(resample(s, r, rate), dtype=float)


def xcorr_peak(hay: np.ndarray, needle: np.ndarray) -> tuple[int, float]:
    """Best lag of needle inside hay (valid region) and its normalized correlation."""
    n = len(hay) + len(needle)
    nfft = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(hay, nfft) * np.conj(np.fft.rfft(needle, nfft)), nfft)[: len(hay) - len(needle) + 1]
    lag = int(np.argmax(c))
    seg = hay[lag: lag + len(needle)]
    norm = float(np.dot(seg, needle) / (np.linalg.norm(seg) * np.linalg.norm(needle) + 1e-12))
    return lag, norm


def fit_gain(seg: np.ndarray, ref: np.ndarray) -> tuple[float, float]:
    """Least-squares gain of ref in seg and the residual level (dB relative to seg)."""
    g = float(np.dot(seg, ref) / (np.dot(ref, ref) + 1e-12))
    res = seg - g * ref
    return g, round(20 * math.log10((np.sqrt(np.mean(res ** 2)) + 1e-12) / (np.sqrt(np.mean(seg ** 2)) + 1e-12)), 1)


def intro_curves(xf: int):  # assemble._prepend_intro: t = i/(xf-1); intro*cos + body*sin
    t = np.arange(xf) / (xf - 1) if xf > 1 else np.ones(xf)
    return np.cos(t * np.pi / 2), np.sin(t * np.pi / 2)


def outro_curves(xf: int):  # assemble._append_outro: t = (i+0.5)/xf; body*cos + outro*sin
    t = (np.arange(xf) + 0.5) / xf
    return np.cos(t * np.pi / 2), np.sin(t * np.pi / 2)


def locate_intro(x, old, xf, search_s=90.0):
    head = old[: len(old) - xf]  # the part of the intro heard alone
    lag, corr = xcorr_peak(x[: int(search_s * RATE) + len(old)], head)
    g, res_db = fit_gain(x[lag: lag + len(head)], head)
    return {"start": lag, "body_start": lag + len(old) - xf, "corr": round(corr, 4), "gain": g, "residual_db": res_db}


def locate_outro(x, old, xf, search_s=90.0):
    tail = old[xf:]  # the part of the outro heard alone
    base = max(0, len(x) - int(search_s * RATE) - len(old))
    lag, corr = xcorr_peak(x[base:], tail)
    lag += base
    g, res_db = fit_gain(x[lag: lag + len(tail)], tail)
    return {"start": lag - xf, "end": lag + len(tail), "corr": round(corr, 4), "gain": g, "residual_db": res_db}


def swap(x, old_in, new_in, old_out, new_out, in_xf_s, out_xf_s):
    xi, xo = int(round(in_xf_s * RATE)), int(round(out_xf_s * RATE))
    li = locate_intro(x, old_in, xi)
    lo = locate_outro(x, old_out, xo)
    g = (li["gain"] + lo["gain"]) / 2
    # body as assembled (unmastered units), still carrying its own fade-in/fade-out weights inside the crossfades
    body = x[li["body_start"]: lo["start"] + xo] / g
    ci, _si = intro_curves(xi)
    body[:xi] -= (li["gain"] / g) * old_in[len(old_in) - xi:] * ci           # remove old intro tail from the crossfade
    _co, so = outro_curves(xo)
    body[len(body) - xo:] -= (lo["gain"] / g) * old_out[:xo] * so            # remove old outro head from the crossfade
    # splice the new ones with the same curves
    nxi, nxo = min(xi, len(new_in), len(body)), min(xo, len(new_out), len(body))
    assert nxi == xi and nxo == xo, "new intro/outro shorter than the crossfade"
    body[:xi] += new_in[len(new_in) - xi:] * ci
    body[len(body) - xo:] += new_out[:xo] * so
    mixed = np.concatenate([new_in[: len(new_in) - xi], body, new_out[xo:]])
    info = {
        "old_intro": {"start_s": round(li["start"] / RATE, 3), "end_s": round((li["start"] + len(old_in)) / RATE, 3),
                      "episode_starts_s": round(li["body_start"] / RATE, 3), "corr": li["corr"],
                      "gain_db": round(20 * math.log10(li["gain"]), 2), "residual_db": li["residual_db"]},
        "old_outro": {"start_s": round(lo["start"] / RATE, 3), "end_s": round(lo["end"] / RATE, 3), "corr": lo["corr"],
                      "gain_db": round(20 * math.log10(lo["gain"]), 2), "residual_db": lo["residual_db"]},
        "dropped_head_s": round(li["start"] / RATE, 3), "dropped_tail_s": round((len(x) - lo["end"]) / RATE, 3),
        "new_intro_s": round(len(new_in) / RATE, 3), "new_outro_s": round(len(new_out) / RATE, 3),
        "new_episode_starts_s": round((len(new_in) - xi) / RATE, 3),
        "new_outro_starts_s": round((len(new_in) - xi + len(body) - xo) / RATE, 3),
        "intro_crossfade_s": in_xf_s, "outro_crossfade_s": out_xf_s,
    }
    return mixed, info


def remnant_check(y, old_in, old_out, new_in, new_out):
    """Normalized correlation of each asset in the result (old should be ~0, new ~1)."""
    out = {}
    for name, a, region in (("old_intro", old_in, y[: int(120 * RATE)]), ("new_intro", new_in, y[: int(120 * RATE)]),
                            ("old_outro", old_out, y[-int(120 * RATE):]), ("new_outro", new_out, y[-int(120 * RATE):])):
        probe = a[: int(min(len(a) - 2.5 * RATE, 15 * RATE))] if "intro" in name else a[int(2.5 * RATE):]
        out[name] = xcorr_peak(region, probe)[1] if len(region) > len(probe) else None
        out[name] = round(out[name], 4) if out[name] is not None else None
    return out


def main(argv=None):
    import yaml
    intros = yaml.safe_load((ROOT / "configs/intros.yaml").read_text())
    outros = yaml.safe_load((ROOT / "configs/outros.yaml").read_text())
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("inp", type=Path); p.add_argument("out", type=Path)
    p.add_argument("--old-intro", type=Path, required=True); p.add_argument("--old-outro", type=Path, required=True)
    p.add_argument("--new-intro", type=Path, default=ROOT / intros["title_song"]["path"])
    p.add_argument("--new-outro", type=Path, default=ROOT / outros["ending_song"]["path"])
    p.add_argument("--intro-xf", type=float, default=float(intros["title_song"].get("crossfade_s", 2.5)))
    p.add_argument("--outro-xf", type=float, default=float(outros["ending_song"].get("crossfade_s", 2.5)))
    lc = (yaml.safe_load((ROOT / "configs/duration.yaml").read_text()) or {}).get("loudness", {})  # same target as assemble
    p.add_argument("--lufs", type=float, default=float(lc.get("integrated_lufs", -16.0)))
    p.add_argument("--true-peak", type=float, default=float(lc.get("true_peak_db", -1.5)))
    p.add_argument("--mp3", type=Path); p.add_argument("--bitrate", default="192k"); p.add_argument("--report", type=Path)
    a = p.parse_args(argv)
    x = decode(a.inp)
    old_in, new_in, old_out, new_out = (asset(q) for q in (a.old_intro, a.new_intro, a.old_outro, a.new_outro))
    mixed, info = swap(x, old_in, new_in, old_out, new_out, a.intro_xf, a.outro_xf)
    for k, v in (("old_intro", info["old_intro"]), ("old_outro", info["old_outro"])):
        if v["corr"] < 0.9:
            sys.exit(f"{k} not found cleanly in {a.inp} (corr {v['corr']}); wrong asset?")
    mastered, minfo = loudness.master(mixed, RATE, a.lufs, a.true_peak)
    write_pcm16(a.out, mastered, RATE)
    y = np.asarray(read_mono(a.out)[0], dtype=float)
    info.update(input=str(a.inp), output=str(a.out), input_s=round(len(x) / RATE, 3), seconds=round(len(y) / RATE, 3),
                master=minfo, measured_lufs=loudness.integrated_lufs(y, RATE),
                remnants=remnant_check(y, old_in, old_out, new_in, new_out),
                old_intro_path=str(a.old_intro), new_intro_path=str(a.new_intro),
                old_outro_path=str(a.old_outro), new_outro_path=str(a.new_outro))
    if a.mp3:  # encode, measure the mp3 itself (ffmpeg ebur128) and correct once if the encoder shifted it by > 0.1 LU
        trim = 0.0
        for _ in range(2):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a.out), "-af", f"volume={trim:.2f}dB", "-c:a", "libmp3lame",
                            "-b:a", a.bitrate, str(a.mp3)], check=True)
            lufs, peak = ebur128(a.mp3)
            if abs(lufs - a.lufs) <= 0.1 or peak + (a.lufs - lufs) > a.true_peak:
                break
            trim += a.lufs - lufs
        info["mp3"] = {"path": str(a.mp3), "lufs_ffmpeg": lufs, "true_peak_db": peak, "trim_db": round(trim, 2)}
    txt = json.dumps(info, ensure_ascii=False, indent=1)
    if a.report:
        a.report.write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
