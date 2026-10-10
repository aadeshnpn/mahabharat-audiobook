"""A/B the music mix against the dialogue-only master, line by line (run with proto/.venv-pocket python).
usage: qa_music.py SCRIPT.json MUSIC_REPORT.json MIX.wav DRY.(wav|mp3) [STEM.wav] [--out build/qa_music.json]
Per line: Whisper WER on the dry and the mixed slice, speaker identity on the mixed slice, speech-to-music
ratio (from the assemble report). With the stem: music loudness in pauses vs under speech."""
import argparse, json, re, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
import numpy as np, librosa
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
from mbh.episode import loudness

def norm(t): return re.sub(r"[^a-z' ]", " ", t.lower().replace("-", " ")).split()
def dist(r, h):
    d = np.arange(len(h) + 1)
    for i in range(1, len(r) + 1):
        prev, d[0] = d.copy(), i
        for j in range(1, len(h) + 1):
            d[j] = min(prev[j] + 1, d[j - 1] + 1, prev[j - 1] + (r[i - 1] != h[j - 1]))
    return int(d[-1])

ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("report"); ap.add_argument("mix"); ap.add_argument("dry")
ap.add_argument("stem", nargs="?"); ap.add_argument("--out", default="build/qa_music.json"); a = ap.parse_args()
lines = {l["id"]: l for l in json.loads(Path(a.script).read_text())["lines"]}
info = json.loads(Path(a.report).read_text())["music"]
ratio = {r["line_id"]: r["ratio_db"] for r in info["speech_to_music_db"]}
cue = {r["line_id"]: r["cue"] for r in info["cue_sheet"]}
SR = 16000
mix, _ = librosa.load(a.mix, sr=SR, mono=True); dry, _ = librosa.load(a.dry, sr=SR, mono=True)
asr = WhisperModel("small.en", device="cpu", compute_type="int8"); enc = VoiceEncoder("cpu")
refs = {p.parent.name: enc.embed_utterance(preprocess_wav(str(p))) for p in sorted((ROOT / "voices").glob("*/ref.wav"))}
def hear(x): return " ".join(s.text for s in asr.transcribe(x, language="en", beam_size=5, condition_on_previous_text=False)[0]).strip()
rows, tot = [], {"dry": [0, 0], "mix": [0, 0]}
for lid, s, e in info["intervals"]:
    l = lines[lid]; ref = norm(l["text"]); s0, s1 = int(max(0, s - 0.1) * SR), int((e + 0.15) * SR)
    row = {"line_id": lid, "speaker": l["speaker"], "cue": cue.get(lid), "ratio_db": ratio.get(lid)}
    for k, sig in (("dry", dry), ("mix", mix)):
        h = hear(sig[s0:s1]); d = dist(ref, norm(h)); tot[k][0] += d; tot[k][1] += len(ref)
        row[f"{k}_wer"] = round(d / max(1, len(ref)), 3); row[f"{k}_asr"] = h
    if e - s >= 1.5:
        for k, sig in (("dry", dry), ("mix", mix)):
            emb = enc.embed_utterance(preprocess_wav(sig[s0:s1], source_sr=SR))
            sims = {v: float(np.dot(emb, r)) for v, r in refs.items()}
            row[f"{k}_voice"] = max(sims, key=sims.get); row[f"{k}_own_sim"] = round(sims.get(l["voice_id"], 0), 3)
        row["best_voice"] = row["mix_voice"]
    rows.append(row); print(lid[-4:], row["cue"], row["dry_wer"], row["mix_wer"], row.get("best_voice"), row["mix_asr"][:60], flush=True)
out = {"overall_wer": {k: round(v[0] / v[1], 4) for k, v in tot.items()}, "lines": rows}
if a.stem:
    st, _ = librosa.load(a.stem, sr=48000, mono=True); mask = np.zeros(len(st), bool)
    for _l, s, e in info["intervals"]: mask[int(s * 48000):int(e * 48000)] = True
    out["stem"] = {"under_speech_lufs": loudness.integrated_lufs(st[mask], 48000), "pauses_lufs": loudness.short_lufs(st[~mask], 48000),
                   "whole_lufs": loudness.integrated_lufs(st, 48000)}
worse = [r for r in rows if r["mix_wer"] > r["dry_wer"]]
out["lines_worse_with_music"] = [r["line_id"] for r in worse]
out["wrong_voice"] = {k: [r["line_id"] for r in rows if r.get(f"{k}_voice") and r[f"{k}_voice"] != lines[r["line_id"]]["voice_id"]] for k in ("dry", "mix")}
sims = [(r["mix_own_sim"] - r["dry_own_sim"]) for r in rows if "dry_own_sim" in r]
out["own_sim_change"] = {"mean": round(float(np.mean(sims)), 3), "worst": round(float(np.min(sims)), 3)} if sims else None
Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "lines"}, indent=1))
