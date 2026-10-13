"""Render the title-song chant (Bhagavad Gita 2.62-63) with VoxCPM2, one clip per half-verse (resumable).
usage: [STYLES=chant] [SPELLINGS=r3,r4] proto/.venv-vox/bin/python tools/title_song/chant.py  -> build/title_song/clips/*.wav (voices/chanter/ref.wav = chosen chanter design A)
1) designs a chanter reference voice (voices/chanter/candidates), 2) clones it for every half-verse x spelling x style x seed."""
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
CFG = json.loads((ROOT / "configs/title_song.json").read_text())
out_dir = ROOT / "build/title_song/clips"; out_dir.mkdir(parents=True, exist_ok=True)
ref_dir = ROOT / "voices/chanter/candidates"; ref_dir.mkdir(parents=True, exist_ok=True)
model = None
def m():
    global model
    if model is None:
        from mbh.episode.voxcpm2 import load_model
        model, _sr = load_model(); globals()["SR"] = _sr
    return model
import soundfile as sf, torch
for k, d in enumerate(CFG["designs"]):
    out = ref_dir / f"chanter-{d['id']}.wav"
    if out.exists(): continue
    torch.manual_seed(d.get("seed", 1)); t = time.time()
    wav = m().generate(text=f"({d['prompt']}){d['line']}", cfg_value=2.0, inference_timesteps=CFG.get("steps", 10))
    sf.write(out, wav, SR); print(json.dumps({"design": str(out.relative_to(ROOT)), "s": round(time.time() - t, 1)}), flush=True)
ONLY_ST = set(filter(None, os.environ.get("STYLES", "").split(","))); ONLY_SP = set(filter(None, os.environ.get("SPELLINGS", "").split(",")))
for style, instr in CFG["styles"].items():
    if ONLY_ST and style not in ONLY_ST: continue
    for sp_name, lines in CFG["spellings"].items():
        if ONLY_SP and sp_name not in ONLY_SP: continue
        for i, text in enumerate(lines):
            if not text: continue
            for seed in CFG["seeds"]:
                ref = ref_dir / f"chanter-{CFG['ref']}.wav"
                out = out_dir / f"{style}_{sp_name}_h{i + 1}_s{seed}.wav"
                if out.exists(): continue
                torch.manual_seed(seed); t = time.time()
                wav = m().generate(text=f"({instr}){text}", reference_wav_path=str(ref), cfg_value=2.0,
                                   inference_timesteps=CFG.get("steps", 10))
                sf.write(out, wav, SR)
                print(json.dumps({"clip": out.name, "s": round(time.time() - t, 1), "audio_s": round(len(wav) / SR, 1)}), flush=True)
print("CHANT_DONE")
