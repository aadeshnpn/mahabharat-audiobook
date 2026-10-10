import json, sys, re, numpy as np, librosa
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
d=sys.argv[1]; script=json.load(open(sys.argv[2])); vmap=json.load(open(sys.argv[3])); log=json.load(open(f"{d}/render_log.json"))
asr=WhisperModel("small.en", device="cpu", compute_type="int8"); enc=VoiceEncoder("cpu")
def norm(s): return re.sub(r"[^a-z ]","",s.lower().replace("-"," ")).split()
def wer(r,h):
    D=np.arange(len(h)+1)
    for i,rw in enumerate(r,1):
        p=D.copy(); D[0]=i
        for j,hw in enumerate(h,1): D[j]=min(p[j]+1,D[j-1]+1,p[j-1]+(rw!=hw))
    return D[-1]/max(1,len(r))
refemb={k:enc.embed_utterance(preprocess_wav(v)) for k,v in vmap.items()}
out=[]
for seg,l in zip(script["segments"],log["segments"]):
    y,_=librosa.load(l["file"],sr=16000)
    hyp=" ".join(s.text for s in asr.transcribe(y.astype(np.float32),beam_size=5)[0]).strip()
    e=enc.embed_utterance(preprocess_wav(l["file"]))
    sims={k:float(e@v) for k,v in refemb.items()}; best=max(sims,key=sims.get)
    r=dict(i=l["i"],speaker=seg["speaker"],wer=round(wer(norm(seg["text"]),norm(hyp)),3),sim_to_own_ref=round(sims[seg["speaker"]],3),closest_ref=best,asr=hyp)
    out.append(r); print(r["i"],r["speaker"],r["wer"],r["sim_to_own_ref"],r["closest_ref"],"|",hyp[:80],flush=True)
json.dump(out,open(f"{d}/qa.json","w"),indent=1)
print("mean WER",round(np.mean([o["wer"] for o in out]),3),"speaker-id acc",sum(o["closest_ref"]==o["speaker"] for o in out),"/",len(out))
