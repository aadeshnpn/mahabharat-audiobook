"""Pronunciation check with multilingual faster-whisper (run with proto/.venv-pocket): transcribe in Devanagari
(Hindi decoder) and compare characters with the reference line."""
from __future__ import annotations

import json
import re
from pathlib import Path


def normalize(text: str) -> str:
    return re.sub(r"[^\u0900-\u0963\u0966-\u097F]", "", text).replace("ऽ", "")


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def char_similarity(h: str, r: str) -> float:
    """1 - normalised edit distance on Devanagari characters (difflib's ratio is unstable on short strings)."""
    if not h and not r:
        return 1.0
    return max(0.0, 1 - levenshtein(h, r) / max(len(h), len(r)))


def similarity(hyp: str, ref: str) -> float:
    return char_similarity(normalize(hyp), normalize(ref))


_MODEL = None


def transcribe(audio, sr: int = 16000) -> str:
    global _MODEL
    from faster_whisper import WhisperModel
    if _MODEL is None:
        _MODEL = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = _MODEL.transcribe(audio, language="hi", beam_size=5, temperature=0,
                                condition_on_previous_text=False, no_repeat_ngram_size=3)
    return "".join(s.text for s in segs).strip()


def score_takes(spec) -> dict:
    import librosa
    from mbh.song.render import cut_from_context
    path = spec.build_dir() / "scores.json"
    scores = json.loads(path.read_text()) if path.exists() else {}
    for line in spec.lines:
        for wav in sorted((spec.build_dir() / "takes").glob(f"{line.id}_*.wav")):
            if wav.name in scores:
                continue
            y = librosa.load(wav, sr=16000)[0]
            y = cut_from_context(librosa.effects.trim(y, top_db=35)[0], 16000, line)
            hyp = transcribe(y)
            scores[wav.name] = {"score": round(similarity(hyp, line.text), 3), "asr": hyp}
            print(f"{scores[wav.name]['score']:.2f} {wav.name} {hyp}", flush=True)
    path.write_text(json.dumps(scores, ensure_ascii=False, indent=1))
    return scores


def score_render(spec, report_path: Path, mixes=()) -> list[dict]:
    """Score each sung line inside a rendered mix (and its dry vocal stem)."""
    import librosa
    report = json.loads(Path(report_path).read_text())
    rows = []
    paths = {"out": report["out"], "vocal_stem": report["vocal_stem"], **{Path(m).stem: str(m) for m in mixes}}
    for stem, path in paths.items():
        y = librosa.load(path, sr=16000)[0]
        for row in report["lines"]:
            line = spec.line(row["line"])
            dur = sum(n.beats for n in line.notes) * spec.beat_s
            seg = y[int(max(0, row["starts_s"] - 0.8) * 16000):int((row["starts_s"] + dur + 0.8) * 16000)]
            hyp = transcribe(seg)
            rows.append({"stem": stem, "line": line.id, "score": round(similarity(hyp, line.text), 3), "asr": hyp})
    return rows


def best_window_similarity(hyp: str, ref: str) -> float:
    """Similarity of the reference to its best-matching stretch of the transcript (songs may repeat a line)."""
    h, r = normalize(hyp), normalize(ref)
    if len(h) <= len(r) * 1.3:
        return char_similarity(h, r)
    best = 0.0
    for i in range(0, len(h) - len(r) + 1, max(1, len(r) // 8)):
        best = max(best, char_similarity(h[i:i + len(r)], r))
    return best


def score_file(path, ref: str) -> dict:
    import librosa
    y = librosa.load(str(path), sr=16000)[0]
    hyp = transcribe(y)
    return {"score": round(best_window_similarity(hyp, ref), 3), "asr": hyp}
