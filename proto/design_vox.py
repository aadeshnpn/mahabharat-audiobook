import time, json, sys, soundfile as sf, torch
torch.set_num_threads(8)
torch.set_default_dtype(torch.bfloat16)  # avoid fp32 construction peak (OOM on 15GB box)
from voxcpm import VoxCPM
t=time.time()
model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False)
torch.set_default_dtype(torch.float32)
print("load_s", round(time.time()-t,1), flush=True)
sr = model.tts_model.sample_rate
steps = int(sys.argv[1]) if len(sys.argv)>1 else 10
voices = json.load(open(sys.argv[2] if len(sys.argv)>2 else "voices.json"))
tag = sys.argv[3] if len(sys.argv)>3 else ""
res=[]
for v in voices:
    for k in range(v.get("n",1)):
        t=time.time()
        wav = model.generate(text=f"({v['prompt']}){v['line']}", cfg_value=2.0, inference_timesteps=steps)
        dt=time.time()-t; dur=len(wav)/sr
        fn=f"out/design/{v['id']}_vox_s{steps}_{k}.wav"; sf.write(fn, wav, sr)
        r=dict(id=v['id'],file=fn,gen_s=round(dt,1),audio_s=round(dur,1),rtf=round(dt/dur,2)); print(r, flush=True); res.append(r)
json.dump(res, open(f"logs/design_vox_s{steps}{tag}.json","w"), indent=1)
