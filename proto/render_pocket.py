"""Render script JSON with Pocket TTS, cloning the VoxCPM2-designed refs. Emotion comes only from the reference."""
import time, json, sys, os, torch, soundfile as sf
from pocket_tts import TTSModel
script=json.load(open(sys.argv[1])); vmap=json.load(open(sys.argv[2])); out=sys.argv[3]; q=len(sys.argv)>4 and sys.argv[4]=="q"
os.makedirs(out,exist_ok=True)
t=time.time(); m=TTSModel.load_model(quantize=q); print("load_s",round(time.time()-t,1),flush=True)
states={}; t=time.time()
for k,v in vmap.items(): states[k]=m.get_state_for_audio_prompt(v)
print("voice_prompt_s",round(time.time()-t,1),flush=True)
log=[]; G=A=0
for i,s in enumerate(script["segments"]):
    t=time.time(); wav=m.generate_audio(states[s["speaker"]], s["text"]); dt=time.time()-t
    wav=wav.squeeze().float().numpy(); dur=len(wav)/m.sample_rate; G+=dt; A+=dur
    fn=f"{out}/{i:03d}_{s['speaker']}.wav"; sf.write(fn,wav,m.sample_rate)
    r=dict(i=i,speaker=s["speaker"],file=fn,gen_s=round(dt,2),audio_s=round(dur,1),rtf=round(dt/dur,3)); print(r,flush=True); log.append(r)
json.dump(dict(engine="pocket-tts",quantize=q,total_gen_s=round(G,1),total_audio_s=round(A,1),rtf=round(G/A,3),segments=log),open(f"{out}/render_log.json","w"),indent=1)
print("TOTAL",round(G,1),round(A,1),round(G/A,3))
