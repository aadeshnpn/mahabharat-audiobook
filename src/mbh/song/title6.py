"""Title v6 concepts (docs/TITLE_TRACK_RESEARCH.md): spoken Krishna verse (clean diction) + a sung 4-note leitmotif on
प्रणश्यति (m G r S, Bhairav) + code orchestra. Config: configs/title_v6.yaml. Stereo 48 kHz.

Clips (dict of mono arrays): k62a k62b k63a k63b (Krishna halves), e63b (Krishna, ending take), hook (sung hook,
lead voice), hook_k (sung hook, Krishna voice; optional). ``build(concept, clips, cfg)`` returns (stereo, timeline)."""
from __future__ import annotations

import numpy as np

from mbh.song import orchestra as O
from mbh.song.arrange import bell, swell, tanpura
from mbh.song.epic import conch, hall

SR = 48000


class Score:
    def __init__(self, seconds):
        self.n = int(seconds * SR); self.bus = {k: np.zeros((2, self.n)) for k in ("voice", "choir", "orch", "fx")}
        self.timeline = []

    def add(self, bus, y, at, gain=1.0, pan=0.5, label=None):
        y = np.asarray(y); k = int(at * SR)
        if k >= self.n: return
        if y.ndim == 1: y = np.stack([y * np.cos(pan * np.pi / 2), y * np.sin(pan * np.pi / 2)]) * np.sqrt(2)
        m = min(y.shape[1], self.n - k); self.bus[bus][:, k:k + m] += y[:, :m] * gain
        if label: self.timeline.append({"at": round(at, 2), "what": label, "s": round(y.shape[1] / SR, 2)})

    def mix(self, cfg):
        g = cfg.get("bus_db", {})
        v = hall(self.bus["voice"], SR, cfg.get("voice_reverb", 0.18), 2.4)
        c = hall(self.bus["choir"], SR, cfg.get("choir_reverb", 0.4), 3.5)
        o = hall(self.bus["orch"], SR, 0.3, 3.0)
        f = hall(self.bus["fx"], SR, 0.35, 3.5)
        out = sum(x[:, :self.n] * 10 ** (g.get(k, 0) / 20) for k, x in (("voice", v), ("choir", c), ("orch", o), ("fx", f)))
        # duck orchestra under the spoken voice a little
        env = np.convolve(np.abs(self.bus["voice"][0]), np.ones(int(.25 * SR)) / int(.25 * SR), "same")
        duck = 1 - cfg.get("duck", 0.35) * np.clip(env / (env.max() + 1e-9) * 3, 0, 1)
        out = v[:, :self.n] * 10 ** (g.get("voice", 0) / 20) + (out - v[:, :self.n] * 10 ** (g.get("voice", 0) / 20)) * duck
        return out


def _rms(x):
    return np.sqrt(np.mean(x[np.abs(x) > 1e-4] ** 2)) + 1e-9


def _n(x, level=0.1):
    return x / _rms(x) * level


def _motif(instr, sa, beat, tokens=("m:1", "G:1", "r:1", "S:3"), **kw):
    return O.line(instr, list(tokens), beat, sa, SR, **kw)


def concept_sting(c, cfg):
    """A: conch -> drum + brass motif -> 2.62 over a growing ostinato -> 2.63 louder -> choir answers पणश्यति -> button."""
    sa, beat = cfg["sa_hz"], cfg["beat_s"]
    k = {x: _n(c[x]) for x in ("k62a", "k62b", "k63a", "k63b")}
    t = 0.0; total = 60.0; S = Score(total)
    S.add("fx", _n(conch(SR, 3.2, f0=sa * 1.5)), 0.0, 0.9, label="conch")
    S.add("orch", _n(O.drum(SR)), 2.6, 1.6, label="drum")
    mot, ms = _motif(O.brass, sa / 2, beat * 0.75); S.add("orch", _n(mot), 2.6, 0.8, label="motif brass")
    t = 2.6 + ms + 0.6
    tan = _n(tanpura(sa, total, SR)); S.add("orch", tan, 0.5, 0.35)
    starts = {}
    for key, gap in (("k62a", 1.6), ("k62b", 2.2), ("k63a", 1.4), ("k63b", 0.5)):
        if key == "k63a":
            S.add("orch", _n(O.drum(SR)), t - 0.3, 1.3, label="drum")
            S.add("fx", swell(2.0, SR), t - 2.0, 0.03)
        starts[key] = t; S.add("voice", k[key], t, 1.0, label=key); t += len(k[key]) / SR + gap
    end_voice = t
    # ostinato under the verse: quiet on 2.62, building on 2.63
    S.add("orch", _n(O.ostinato(sa, starts["k63a"] - starts["k62a"], SR, g0=0.25, g1=0.5)), starts["k62a"], 0.55)
    S.add("orch", _n(O.ostinato(sa, end_voice - starts["k63a"], SR, beat_s=0.375, g0=0.6, g1=1.0)), starts["k63a"], 0.8)
    # rising string chord steps under 2.63
    for i, (sw, at) in enumerate((("S", starts["k63a"]), ("r", starts["k63b"]))):
        S.add("orch", _n(O.string_tone(O.swara_hz(sw, sa), 4.5, SR)), at, 0.45 + 0.15 * i)
    # choir answer on the motif, with drums on each note, brass doubling
    h = c["hook"]; hk = _n(O.choir(h, SR))
    S.add("choir", hk, end_voice, 1.2, label="choir hook")
    on = cfg.get("hook_onset_s", 0.6)
    for i in range(4):
        S.add("orch", _n(O.drum(SR, f0=58 if i < 3 else 46)), end_voice + on + i * beat, 1.2 if i < 3 else 1.8)
    mot, ms = _motif(O.brass, sa / 2, beat); S.add("orch", _n(mot), end_voice + on, 0.7)
    btn = end_voice + on + 3 * beat
    S.add("fx", _n(bell(sa * 4, SR)), btn, 0.5, label="bell")
    S.add("orch", _n(O.string_tone(sa / 2, 4.0, SR, release=2.5)), btn, 0.5)
    return S, btn + cfg.get("ring_s", 4.0)


def concept_motif(c, cfg):
    """B: leitmotif-led. Bansuri states the motif; Krishna speaks each half; the motif answers each half and grows
    (flute -> strings -> brass) until the choir sings it on प्रणश्यति. Gentle, intimate, no big drums until the end."""
    sa, beat = cfg["sa_hz"], cfg["beat_s"]
    k = {x: _n(c[x]) for x in ("k62a", "k62b", "k63a", "k63b")}
    total = 60.0; S = Score(total)
    S.add("orch", _n(tanpura(sa, total, SR)), 0.0, 0.45)
    mot, ms = _motif(O.bansuri, sa * 2, beat * 0.8); S.add("orch", _n(mot), 0.8, 0.9, label="motif flute")
    t = 0.8 + ms + 0.8
    answers = [(O.bansuri, sa * 2, ("m:0.5", "G:0.5", "r:1"), 0.6), (O.string_tone, sa, ("m:0.5", "G:0.5", "r:1"), 0.7),
               (O.brass, sa / 2, ("m:0.5", "G:0.5", "r:0.5", "S:1"), 0.8)]
    for i, key in enumerate(("k62a", "k62b", "k63a", "k63b")):
        S.add("voice", k[key], t, 1.0, label=key); t += len(k[key]) / SR + 0.3
        if i < 3:
            ins, base, toks, g = answers[i]; y, s = O.line(ins, list(toks), beat * 0.7, base, SR)
            S.add("orch", _n(y), t, g, label=f"answer {i + 1}"); t += s + 0.6
            if i == 2: S.add("orch", _n(O.drum(SR)), t - 0.4, 0.9)
    S.add("choir", _n(O.choir(c["hook"], SR)), t, 1.2, label="choir hook")
    on = cfg.get("hook_onset_s", 0.6)
    mot, ms = _motif(O.string_tone, sa, beat); S.add("orch", _n(mot), t + on, 0.6)
    btn = t + on + 3 * beat
    S.add("orch", _n(O.drum(SR, f0=46)), btn, 1.4); S.add("fx", _n(bell(sa * 4, SR)), btn, 0.45, label="bell")
    return S, btn + cfg.get("ring_s", 4.0)


def concept_coldopen(c, cfg):
    """C: sonic-logo first. Cold open: the choir sings the hook alone (the brand), conch answers; then a steady deep drum
    pulse (60 bpm) and Krishna declaims the verse on the beat; brass + choir 'aah' pad swell under 2.63; final hook
    tutti with drums on every note; bell button."""
    sa, beat = cfg["sa_hz"], cfg["beat_s"]
    k = {x: _n(c[x]) for x in ("k62a", "k62b", "k63a", "k63b")}
    total = 60.0; S = Score(total)
    S.add("choir", _n(O.choir(c["hook"], SR)), 0.0, 0.9, label="choir hook (cold open)")
    first = cfg.get("hook_onset_s", 0.6) + 3 * beat
    S.add("fx", _n(conch(SR, 3.0, f0=sa * 1.5)), first + 0.4, 0.8, label="conch")
    S.add("orch", _n(tanpura(sa, total, SR)), first, 0.35)
    t = first + 2.4
    starts = []
    for key, gap in (("k62a", 1.4), ("k62b", 2.0), ("k63a", 1.2), ("k63b", 0.6)):
        starts.append(t); S.add("voice", k[key], t, 1.0, label=key); t += len(k[key]) / SR + gap
    end_voice = t
    p = starts[0] - 1.0
    while p < end_voice:                       # drum pulse, louder on 2.63
        S.add("orch", _n(O.drum(SR, seconds=1.4, f0=55)), p, 0.5 if p < starts[2] - 0.5 else 0.9); p += beat * 2
    pad = O.string_tone(O.swara_hz("S", sa), end_voice - starts[2] + 1, SR, attack=2.5)
    S.add("orch", _n(pad), starts[2] - 0.5, 0.6); S.add("orch", _n(O.brass(sa / 2, end_voice - starts[2] + 1, SR, 3.0)), starts[2], 0.5)
    S.add("fx", swell(2.5, SR), end_voice - 2.5, 0.03)
    S.add("choir", _n(O.choir(c["hook"], SR)), end_voice, 1.3, label="choir hook (tutti)")
    on = cfg.get("hook_onset_s", 0.6)
    for i in range(4):
        S.add("orch", _n(O.drum(SR, f0=58 if i < 3 else 46)), end_voice + on + i * beat, 1.2 if i < 3 else 1.8)
    mot, ms = _motif(O.brass, sa / 2, beat); S.add("orch", _n(mot), end_voice + on, 0.7)
    btn = end_voice + on + 3 * beat
    S.add("fx", _n(bell(sa * 4, SR)), btn, 0.5, label="bell")
    return S, btn + cfg.get("ring_s", 4.0)


def ending_sting(c, cfg):
    """Ending (<= 20 s): tanpura, Krishna 'स्मृतिभ्रंशाद्बुद्धिनाशो बुद्धिनाशात्प्रणश्यति' (e63b), choir hook softly, bell."""
    sa, beat = cfg["sa_hz"], cfg["beat_s"]
    S = Score(30.0)
    S.add("orch", _n(tanpura(sa, 30.0, SR)), 0.0, 0.4)
    mot, ms = _motif(O.bansuri, sa * 2, beat * 0.8); S.add("orch", _n(mot), 0.4, 0.7, label="motif flute")
    t = 0.4 + ms * 0.8
    e = _n(c["e63b"]); S.add("voice", e, t, 1.0, label="e63b"); t += len(e) / SR + 0.3
    S.add("choir", _n(O.choir(c["hook"], SR)), t, 0.9, label="choir hook")
    on = cfg.get("hook_onset_s", 0.6); btn = t + on + 3 * beat
    S.add("orch", _n(O.string_tone(sa / 2, btn - t + 3, SR, attack=1.0, release=2.5)), t, 0.5)
    S.add("orch", _n(O.drum(SR, f0=46)), btn, 1.0); S.add("fx", _n(bell(sa * 4, SR)), btn, 0.45, label="bell")
    return S, btn + cfg.get("ring_s", 4.0)


CONCEPTS = {"sting": concept_sting, "motif": concept_motif, "coldopen": concept_coldopen, "ending": ending_sting}


def build(concept, clips, cfg):
    S, end = CONCEPTS[concept](clips, {**cfg, **cfg.get(concept, {})})
    out = S.mix({**cfg, **cfg.get(concept, {})})[:, : int(end * SR)]
    f = int(cfg.get("fade_s", 2.5) * SR); out[:, -f:] *= np.linspace(1, 0, f) ** 2
    return out, sorted(S.timeline, key=lambda r: r["at"])
