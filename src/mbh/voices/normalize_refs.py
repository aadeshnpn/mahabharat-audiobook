"""Normalise voice reference clips to a common loudness (VoxCPM2 clone level follows the reference).

usage: python -m mbh.voices.normalize_refs [--target -20] [--tp -1.5] [--dry-run] [voice_id ...]
Each changed ref.wav is backed up first as ref_replaced_<unix>_prenorm.wav (the web app's history
convention). Pure gain plus the sparse peak limiter: timbre is unchanged. Re-renders are triggered
automatically because the render cache key includes the reference file version.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import wave
from pathlib import Path

from mbh.episode import loudness
from mbh.episode.audioio import read_mono, write_pcm16
from mbh.episode.paths import repo_root


def normalize_ref(path: Path, target: float, tp: float, dry_run: bool = False, tolerance: float = 0.5) -> dict:
    samples, rate = read_mono(path)
    before, method = loudness.measure(samples, rate)
    row = {"voice": path.parent.name, "before": before, "method": method}
    if before is None or abs(before - target) <= tolerance:
        return {**row, "after": before, "changed": False}
    out, info = loudness.master(samples, rate, target, tp)
    if not dry_run:
        with wave.open(str(path)) as h:
            if h.getnchannels() != 1:
                raise ValueError(f"{path}: expected mono reference")
        shutil.copy2(path, path.with_name(f"ref_replaced_{int(time.time())}_prenorm.wav"))
        write_pcm16(path, out, rate)
    return {**row, "after": info["after"], "gain_db": info["gain_db"], "limited_samples": info["limited_samples"], "changed": not dry_run}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("voices", nargs="*")
    ap.add_argument("--target", type=float, default=-20.0)
    ap.add_argument("--tp", type=float, default=-1.5)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = repo_root() / "voices"
    paths = [root / v / "ref.wav" for v in a.voices] if a.voices else sorted(root.glob("*/ref.wav"))
    print(json.dumps([normalize_ref(p, a.target, a.tp, a.dry_run) for p in paths], indent=1))


if __name__ == "__main__":
    main()
