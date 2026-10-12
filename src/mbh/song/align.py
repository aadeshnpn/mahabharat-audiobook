"""Syllable timing for a spoken take via the MMS multilingual forced aligner (torchaudio MMS_FA, CPU).
Each syllable is aligned as a 'word' of its ASCII romanisation; vowel letters mark the nucleus."""
from __future__ import annotations

import numpy as np

from mbh.song.translit import VOWEL_LETTERS, to_ascii

_BUNDLE = None


def align_syllables(y: np.ndarray, sr: int, syllables: list[str]) -> list[tuple[float, float, float, float]]:
    """Return (start, vowel_start, vowel_end, end) seconds for each syllable."""
    global _BUNDLE
    import torch
    import torchaudio
    from torchaudio.pipelines import MMS_FA

    if _BUNDLE is None:
        _BUNDLE = (MMS_FA, MMS_FA.get_model(with_star=False).eval(), MMS_FA.get_tokenizer(), MMS_FA.get_aligner())
    bundle, model, tokenizer, aligner = _BUNDLE
    wav = torch.tensor(y, dtype=torch.float32)[None]
    if sr != bundle.sample_rate:
        wav = torchaudio.functional.resample(wav, sr, bundle.sample_rate)
    words = [to_ascii(s) or "a" for s in syllables]
    with torch.inference_mode():
        emission, _ = model(wav)
        spans = aligner(emission[0], tokenizer(words))
    ratio = wav.shape[1] / emission.shape[1] / bundle.sample_rate  # seconds per emission frame
    out = []
    for word, toks in zip(words, spans):
        start, end = toks[0].start * ratio, toks[-1].end * ratio
        letters = list(word)
        vow = [t for t, ch in zip(toks, letters) if ch in VOWEL_LETTERS] or toks
        # CTC spans are peaky (a vowel often gets one 20 ms frame), so the nucleus runs from the first vowel to the
        # end of the syllable minus a short allowance for coda consonants
        last_v = max((i for i, ch in enumerate(letters) if ch in VOWEL_LETTERS), default=len(letters) - 1)
        coda = len(letters) - 1 - last_v
        v_start = vow[0].start * ratio
        v_end = max(v_start + 0.04, end - 0.045 * coda)
        out.append((start, v_start, v_end, end))
    return out
