"""Song pipeline: spoken takes (VoxCPM2 clone of the singer voice) -> sung lines -> arrangement -> master.
Run in the render venv (proto/.venv-vox: numpy, soundfile, librosa, pyworld, VoxCPM2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from mbh.episode.paths import repo_root
from mbh.song.spec import SongLine, SongSpec

SR = 48000


def voice_ref(spec: SongSpec, voice: dict | None = None) -> Path:
    voice = voice or spec.voice
    if voice.get("ref"):
        return repo_root() / voice["ref"]
    return repo_root() / "voices" / voice["id"] / "ref.wav"


def take_text(line: SongLine) -> str:
    return line.context or line.text


def take_path(spec: SongSpec, line: SongLine, voice_id: str, seed: int) -> Path:
    h = hashlib.sha1(take_text(line).encode()).hexdigest()[:6]
    return spec.build_dir() / "takes" / f"{line.id}_{voice_id}_{h}_s{seed}.wav"


def make_takes(spec: SongSpec, line_ids: list[str] | None = None, voice: dict | None = None, seeds=None) -> list[Path]:
    """Speak each line (or its context) with the singer voice, one take per seed. Cached by file name."""
    import soundfile as sf
    import torch

    voice = {**spec.voice, **(voice or {})}
    ref = voice_ref(spec, voice)
    model = sr = None
    made = []
    for line in spec.lines:
        if line_ids and line.id not in line_ids:
            continue
        for seed in seeds or voice.get("seeds", [11]):
            out = take_path(spec, line, voice["id"], seed)
            made.append(out)
            if out.exists():
                continue
            if model is None:
                from mbh.episode.voxcpm2 import load_model
                model, sr = load_model()
            out.parent.mkdir(parents=True, exist_ok=True)
            torch.manual_seed(seed)
            wav = model.generate(text=f"({voice.get('prompt', '')}){take_text(line)}", reference_wav_path=str(ref),
                                 cfg_value=2.0, inference_timesteps=int(voice.get("steps", 10)))
            sf.write(out, wav, sr)
            print(json.dumps({"take": str(out.relative_to(repo_root())), "seconds": round(len(wav) / sr, 2)}), flush=True)
    return made


def _trim(y: np.ndarray, top_db: float = 35) -> np.ndarray:
    import librosa
    return librosa.effects.trim(y, top_db=top_db)[0]


def cut_from_context(y: np.ndarray, sr: int, line: SongLine) -> np.ndarray:
    """A take of ``line.context`` holds several lines separated by '।'; cut out this line at the pauses."""
    if not line.context:
        return y
    parts = [p.strip(" ,") for p in line.context.split("।") if p.strip(" ,")]
    k = len(parts)
    idx = next((i for i, p in enumerate(parts) if line.text.rstrip("।").strip() in p or p in line.text), 0)
    if k == 1:
        return y
    import librosa
    hop = 480
    e = librosa.feature.rms(y=y, frame_length=1920, hop_length=hop)[0]
    quiet = e < 0.08 * e.max()
    cuts = []
    for j in range(1, k):  # deepest/longest pause near each expected boundary
        lo, hi = int(len(e) * (j / k - 0.18)), int(len(e) * (j / k + 0.18))
        best, run, pos = 0, 0, int(len(e) * j / k)
        for i in range(max(1, lo), min(len(e), hi)):
            run = run + 1 if quiet[i] else 0
            if run > best:
                best, pos = run, i - run // 2
        cuts.append(pos * hop)
    bounds = [0, *cuts, len(y)]
    return _trim(y[bounds[idx]:bounds[idx + 1]])


def load_take(spec: SongSpec, line: SongLine, voice_id: str, take: str | None = None) -> tuple[np.ndarray, int, str]:
    import librosa

    takes_dir = spec.build_dir() / "takes"
    name = take or line.take
    if not name:
        scores_path = spec.build_dir() / "scores.json"
        scores = json.loads(scores_path.read_text()) if scores_path.exists() else {}
        cands = sorted(takes_dir.glob(f"{line.id}_{voice_id}_*.wav"),
                       key=lambda p: -scores.get(p.name, {}).get("score", 0))
        if not cands:
            raise FileNotFoundError(f"no takes for line {line.id} voice {voice_id}; run `mbh song takes`")
        name = cands[0].name
    y, sr = librosa.load(takes_dir / name, sr=SR, mono=True)
    return cut_from_context(_trim(y), sr, line), sr, name


def reverb(y: np.ndarray, wet: float, sr: int, seconds: float = 2.4, seed: int = 9) -> np.ndarray:
    from scipy.signal import butter, fftconvolve, sosfilt
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    ir = rng.standard_normal(len(t)) * np.exp(-t * 2.6)
    ir = sosfilt(butter(2, [200, 6000], btype="band", fs=sr, output="sos"), ir)
    ir /= np.sqrt(np.sum(ir ** 2))
    pre = int(0.03 * sr)
    wet_sig = np.concatenate([np.zeros(pre), fftconvolve(y, ir)])[:len(y)]
    return y + wet * wet_sig


def render(spec: SongSpec, out: Path, *, line_ids: list[str] | None = None, voice: dict | None = None,
           takes: dict[str, str] | None = None, seed: int = 0) -> dict:
    import soundfile as sf

    from mbh.episode import loudness
    from mbh.song.arrange import PRESETS, arrangement
    from mbh.song.sing import sing_line

    voice = {**spec.voice, **(voice or {})}
    beat = spec.beat_s
    intro_s = float(spec.arrangement.get("intro_beats", 8)) * beat
    gap_s = float(spec.arrangement.get("gap_beats", 2)) * beat
    outro_s = float(spec.arrangement.get("outro_beats", 6)) * beat
    structure = [row for row in spec.structure if not line_ids or row["line"] in line_ids] or \
        [{"line": i} for i in (line_ids or [])]
    lead = 0.6
    vocal_parts, timeline, used = [], [], []
    t = intro_s
    for row in structure:
        line = spec.line(row["line"])
        y, sr, name = load_take(spec, line, voice["id"], (takes or {}).get(line.id) or row.get("take"))
        sung, info = sing_line(y, sr, line.notes, len(line.syllables), spec.sa_hz, beat, voice, lead_s=lead, seed=seed,
                                syllables=line.syllables)
        start = t - lead
        vocal_parts.append((start, sung))
        timeline.append((line, t))
        used.append({"line": line.id, "take": name, "starts_s": round(t, 2), "seconds": info["seconds"],
                     "segments": info["segments"], "align": info["align"]})
        t += info["beats"] * beat + gap_s
    total = t - gap_s + outro_s + 4.0
    n = int(total * SR)
    out.parent.mkdir(parents=True, exist_ok=True)
    vocal = np.zeros(n)
    for start, sung in vocal_parts:
        k = int(start * SR); seg = sung[:n - k]; vocal[k:k + len(seg)] += seg
    cfg = {**PRESETS[spec.arrangement.get("preset", "devotional_title")], **spec.arrangement.get("mix", {})}
    vr = np.sqrt(np.mean(vocal[np.abs(vocal) > 1e-4] ** 2)) + 1e-9
    sf.write(out.with_suffix(".dry.wav"), vocal / (np.abs(vocal).max() + 1e-9) * 0.9, SR, subtype="PCM_16")
    vocal = reverb(vocal / vr * 0.1, cfg["vocal_reverb"], SR)
    stems = arrangement(spec, timeline, total, SR, intro_s)
    bed = sum(stems.values())
    bed = bed / (np.sqrt(np.mean(bed ** 2)) + 1e-9) * 0.1 * 10 ** (cfg["bed_db"] / 20)
    # gentle ducking of the bed under the voice
    env = np.convolve(np.abs(vocal), np.ones(int(0.3 * SR)) / int(0.3 * SR), mode="same")
    duck = 1 - 0.3 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    mix = vocal + bed * duck
    fi, fo = 2.5, 4.0
    mix[:int(fi * SR)] *= np.linspace(0, 1, int(fi * SR)) ** 2
    mix[-int(fo * SR):] *= np.linspace(1, 0, int(fo * SR)) ** 2
    mastered, master = loudness.master(mix, SR, float(spec.master.get("lufs", -16)), float(spec.master.get("true_peak_db", -2)))
    sf.write(out, np.asarray(mastered), SR, subtype="PCM_16")
    sf.write(out.with_suffix(".vocal.wav"), vocal / (np.abs(vocal).max() + 1e-9) * 0.9, SR, subtype="PCM_16")
    report = {"out": str(out), "seconds": round(total, 2), "voice": voice["id"], "lines": used, "master": master,
              "vocal_stem": str(out.with_suffix(".vocal.wav"))}
    out.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return report
