import time, json, sys, torch, soundfile as sf
torch.set_num_threads(8)
from qwen_tts import Qwen3TTSModel
t=time.time()
m=Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cpu", dtype=torch.bfloat16)
print("load_s",round(time.time()-t,1),flush=True)
V={v["id"]:v for f in ["voices.json","voices2.json"] for v in json.load(open(f))}
res=[]
for vid in sys.argv[1].split(","):
    v=V[vid]; t=time.time()
    wavs,sr=m.generate_voice_design(text=v["line"], language="English", instruct=v["prompt"])
    dt=time.time()-t; dur=len(wavs[0])/sr; fn=f"out/design/{vid}_qwen_0.wav"; sf.write(fn,wavs[0],sr)
    r=dict(id=vid,file=fn,gen_s=round(dt,1),audio_s=round(dur,1),rtf=round(dt/dur,2)); print(r,flush=True); res.append(r)
json.dump(res,open("logs/design_qwen.json","w"),indent=1)
