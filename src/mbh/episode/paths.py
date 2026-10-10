"""Repository root, independent of the working directory."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # src/mbh/episode/paths.py → repo
    return Path(__file__).resolve().parents[3]
