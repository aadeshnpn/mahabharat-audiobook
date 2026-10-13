"""Song config (YAML): lyrics in Devanagari split into syllables, a melody per line, voice, arrangement preset."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mbh.episode.paths import repo_root
from mbh.song.melody import Note, check_raga, parse_line_melody


@dataclass
class SongLine:
    id: str
    text: str                      # Devanagari, what VoxCPM2 speaks
    syllables: list[str]           # one entry per sung syllable (IAST or Devanagari, for alignment)
    notes: list[Note]
    take: str | None = None        # chosen take file name (build/song/<id>/takes), or None = best ASR score
    context: str | None = None     # optional longer text to speak, from which this line is cut (fixes onsets)


@dataclass
class SongSpec:
    id: str
    title: str
    path: Path
    sa_hz: float
    tempo_bpm: float
    raga: str | None
    voice: dict
    arrangement: dict
    lines: list[SongLine]
    structure: list[dict] = field(default_factory=list)
    master: dict = field(default_factory=lambda: {"lufs": -16.0, "true_peak_db": -2.0})
    raw: dict = field(default_factory=dict)

    @property
    def beat_s(self) -> float:
        return 60.0 / self.tempo_bpm

    def line(self, line_id: str) -> SongLine:
        for line in self.lines:
            if line.id == line_id:
                return line
        raise KeyError(line_id)

    def build_dir(self) -> Path:
        return repo_root() / "build" / "song" / self.id


def load_song(path: Path | str) -> SongSpec:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    lines = []
    for row in data["lines"]:
        syl = list(row["syllables"]) if isinstance(row["syllables"], list) else str(row["syllables"]).split()
        lines.append(SongLine(id=str(row["id"]), text=str(row["text"]), syllables=syl,
                              notes=parse_line_melody(list(row["melody"]), syl),
                              take=row.get("take"), context=row.get("context")))
    spec = SongSpec(
        id=str(data["id"]), title=str(data.get("title", data["id"])), path=path,
        sa_hz=float(data["sa_hz"]), tempo_bpm=float(data.get("tempo_bpm", 72)), raga=data.get("raga"),
        voice=dict(data.get("voice") or {}), arrangement=dict(data.get("arrangement") or {}), lines=lines,
        structure=list(data.get("structure") or [{"line": line.id} for line in lines]),
        master=dict(data.get("master") or {"lufs": -16.0, "true_peak_db": -2.0}),
        raw=data,
    )
    for line in spec.lines:
        bad = check_raga(line.notes, spec.raga)
        if bad:
            raise ValueError(f"line {line.id}: swaras {bad} are outside raga {spec.raga}")
    return spec
