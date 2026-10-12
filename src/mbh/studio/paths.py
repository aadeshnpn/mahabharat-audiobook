"""Where Studio reads and writes. Tests point these at temp directories with env vars."""

from __future__ import annotations

import os
from pathlib import Path

from mbh.episode.paths import repo_root


def episodes_dir() -> Path:
    raw = os.environ.get("MBH_EPISODES")
    path = Path(raw) if raw else repo_root() / "episodes"
    path.mkdir(parents=True, exist_ok=True)
    (path / "overrides").mkdir(parents=True, exist_ok=True)
    return path


def lexicon_file() -> Path:
    raw = os.environ.get("MBH_LEXICON")
    return Path(raw) if raw else repo_root() / "lexicon" / "book01.tsv"


def build_dir() -> Path:
    raw = os.environ.get("MBH_BUILD")
    return Path(raw) if raw else repo_root() / "build"


def episode_yaml(episode_id: str) -> Path:
    return episodes_dir() / f"{episode_id}.yaml"


def overrides_path(episode_id: str) -> Path:
    return episodes_dir() / "overrides" / f"{episode_id}.json"


def script_json(episode_id: str) -> Path:
    return episodes_dir() / f"{episode_id}.script.json"


def script_markdown(episode_id: str) -> Path:
    return episodes_dir() / f"{episode_id}_script.md"


def manifest_path(episode_id: str) -> Path:
    return episodes_dir() / f"{episode_id}.render.json"


def playback_dir(episode_id: str) -> Path:
    path = build_dir() / "studio" / episode_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir(engine: str) -> Path:
    path = build_dir() / "cache" / engine
    path.mkdir(parents=True, exist_ok=True)
    return path


def display_path(path: Path) -> str:
    """Repo-relative when the file lives in the checkout, otherwise absolute."""
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(repo_root()))
    except ValueError:
        return str(resolved)
