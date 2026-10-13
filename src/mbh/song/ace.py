"""ACE-Step 1.5 (MIT, diffusers AceStepPipeline) on CPU: a fully sung, arranged rendition of song lines.
Two modes: ``text2music`` (the model composes the melody from the lyrics + style prompt) and ``cover`` (re-sing and
re-orchestrate our own WORLD-sung render, keeping its melody). Run with proto/.venv-ace."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

REPO = "ACE-Step/acestep-v15-xl-turbo-diffusers"
_PIPE = None


def pipeline(threads: int | None = None):
    global _PIPE
    if _PIPE is None:
        import torch
        from diffusers import AceStepPipeline
        if threads:
            torch.set_num_threads(threads)
        _PIPE = AceStepPipeline.from_pretrained(REPO, torch_dtype=torch.bfloat16).to("cpu")
        if hasattr(_PIPE.vae, "use_tiling"):
            _PIPE.vae.use_tiling = True   # tiled VAE encode/decode: long (60-90 s) sources otherwise need ~17 GB
    return _PIPE


def lyrics_for(spec, line_ids: list[str] | None, script: str = "devanagari", repeat: int = 1) -> str:
    """Lyrics block for ACE-Step. ``script``: devanagari (as written) or roman (plain ASCII from mbh.song.translit)."""
    from mbh.song.translit import to_ascii
    lines = [l for l in spec.lines if not line_ids or l.id in line_ids]
    out = []
    for l in lines:
        text = l.text
        if script == "roman":
            text = " ".join(to_ascii(w) for w in text.replace("।", "").split()).replace(",", "")
            text = text.replace("  ", " ")
        out.append(text)
    body = "\n".join(out * repeat)
    return f"[verse]\n{body}"


def generate(spec, out: Path, *, line_ids=None, seed: int = 0, mode: str = "text2music", src: Path | None = None,
             duration: float | None = None, cover_strength: float | None = None, script: str | None = None,
             prompt: str | None = None, track: str | None = None, lyrics: str | None = None,
             bpm: int | None = None, keyscale: str | None = None, steps: int | None = None,
             repaint: tuple[float, float] | None = None) -> dict:
    import soundfile as sf
    import torch

    cfg = dict(spec.raw.get("ace") or {})
    pipe = pipeline(cfg.get("threads"))
    kwargs = dict(prompt=prompt or cfg.get("prompt", ""),
                  lyrics=lyrics or lyrics_for(spec, line_ids, script or cfg.get("script", "devanagari"), int(cfg.get("repeat", 1))),
                  audio_duration=float(duration or cfg.get("duration", 30)), vocal_language=cfg.get("language", "hi"),
                  num_inference_steps=int(steps or cfg.get("steps", 8)), bpm=int(bpm or cfg.get("bpm", round(spec.tempo_bpm))),
                  keyscale=keyscale or cfg.get("keyscale"), timesignature=str(cfg.get("timesignature", "4")),
                  generator=torch.Generator().manual_seed(seed))
    if mode in ("cover", "complete", "lego", "repaint"):
        y, sr = sf.read(src, always_2d=True)
        if sr != pipe.sample_rate:
            import librosa
            y = librosa.resample(y.T, orig_sr=sr, target_sr=pipe.sample_rate).T
        stereo = torch.from_numpy(np.repeat(y[:, :1], 2, axis=1) if y.shape[1] == 1 else y).float().T
        kwargs.update(task_type=mode, src_audio=stereo, audio_duration=stereo.shape[1] / pipe.sample_rate)
        if mode == "cover":
            kwargs["audio_cover_strength"] = float(cover_strength if cover_strength is not None else cfg.get("cover_strength", 0.6))
        if mode == "lego":
            kwargs["track_name"] = track or "vocals"
            kwargs["repainting_start"], kwargs["repainting_end"] = 0.0, -1
        if mode == "repaint":   # regenerate only [start, end) s, e.g. a weak syllable; the rest is kept
            kwargs["repainting_start"], kwargs["repainting_end"] = repaint
        if mode == "complete":
            kwargs["complete_track_classes"] = cfg.get("complete_tracks", ["strings", "percussion", "keyboard"])
    t = time.time()
    audio = pipe(**kwargs).audios
    a = audio[0].float().cpu().numpy().T
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, a, pipe.sample_rate)
    info = {"out": str(out), "mode": mode, "seed": seed, "seconds": round(a.shape[0] / pipe.sample_rate, 2),
            "gen_s": round(time.time() - t, 1), "prompt": kwargs["prompt"], "lyrics": kwargs["lyrics"],
            "src": str(src) if src else None}
    Path(out).with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    return info


def lyrics_format(spec, line_ids, fmt: str) -> str:
    """Lyric layouts that change phrasing/diction. ``half``: one half-line (pada) per lyric line, so the model breathes at
    each caesura; ``roman``: plain ASCII; ``verse``: the config default (one line per half-verse)."""
    from mbh.song.translit import to_ascii
    lines = [l for l in spec.lines if not line_ids or l.id in line_ids]
    padas = [p.strip(" ।") for l in lines for p in l.text.replace("।", "").split(",")]
    if fmt == "roman":
        padas = [" ".join(to_ascii(w) for w in p.split()) for p in padas]
    if fmt == "verse":
        return lyrics_for(spec, line_ids)
    return "[intro]\n\n[verse]\n" + "\n".join(padas) + "\n\n[outro]"
