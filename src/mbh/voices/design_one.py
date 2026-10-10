"""Design one voice candidate with VoxCPM2 on CPU (run with the VoxCPM venv python).
usage: design_one.py --prompt "..." --text "..." --out voices/<id>/candidates/x.wav [--steps 10] [--threads 8]
Prints a JSON line with timing at the end."""
import argparse, json, time, os, sys
ap = argparse.ArgumentParser()
ap.add_argument("--prompt", required=True); ap.add_argument("--text", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--steps", type=int, default=10); ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
a = ap.parse_args()
import torch, soundfile as sf
torch.set_num_threads(a.threads)
torch.set_default_dtype(torch.bfloat16)  # avoid fp32 construction peak (OOM on 15 GB boxes)
from voxcpm import VoxCPM
t0 = time.time(); m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False); torch.set_default_dtype(torch.float32)
t1 = time.time(); wav = m.generate(text=f"({a.prompt}){a.text}", cfg_value=2.0, inference_timesteps=a.steps); t2 = time.time()
os.makedirs(os.path.dirname(a.out), exist_ok=True); sr = m.tts_model.sample_rate; sf.write(a.out, wav, sr)
print(json.dumps(dict(out=a.out, load_s=round(t1 - t0, 1), gen_s=round(t2 - t1, 1), audio_s=round(len(wav) / sr, 1), rtf=round((t2 - t1) / (len(wav) / sr), 2))))
