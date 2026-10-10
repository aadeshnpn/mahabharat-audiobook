"""Render a script JSON with VoxCPM2 controllable cloning. usage: render_vox.py script.json voices_map.json outdir steps"""
import time, json, sys, os, soundfile as sf, torch
torch.set_num_threads(8); torch.set_default_dtype(torch.bfloat16)
from voxcpm import VoxCPM
script=json.load(open(sys.argv[1])); vmap=json.load(open(sys.argv[2])); out=sys.argv[3]; steps=int(sys.argv[4])
os.makedirs(out, exist_ok=True)
t=time.time(); model=VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False); torch.set_default_dtype(torch.float32)
print("load_s", round(time.time()-t,1), flush=True); sr=model.tts_model.sample_rate
EMO={"solemn_resolve":"solemn and resolute","shy":"shy and modest","awed":"full of awe","commanding":"commanding and noble","tender":"tender and gentle","joyful":"overjoyed","warm":"warm","solemn":"solemn","neutral":"calm"}
log=[]; tot_g=0; tot_a=0
for i,s in enumerate(script["segments"]):
    instr=f"({EMO.get(s['emotion'],s['emotion'])}, {s.get('pace','moderate')} pace)"
    t=time.time()
    wav=model.generate(text=instr+s["text"], reference_wav_path=vmap[s["speaker"]], cfg_value=2.0, inference_timesteps=steps)
    dt=time.time()-t; dur=len(wav)/sr; tot_g+=dt; tot_a+=dur
    fn=f"{out}/{i:03d}_{s['speaker']}.wav"; sf.write(fn,wav,sr)
    r=dict(i=i,speaker=s['speaker'],instr=instr,file=fn,gen_s=round(dt,1),audio_s=round(dur,1),rtf=round(dt/dur,2)); print(r,flush=True); log.append(r)
json.dump(dict(steps=steps,total_gen_s=round(tot_g,1),total_audio_s=round(tot_a,1),rtf=round(tot_g/tot_a,2),segments=log),open(f"{out}/render_log.json","w"),indent=1)
print("TOTAL", round(tot_g,1), round(tot_a,1), round(tot_g/tot_a,2))
