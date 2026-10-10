import json, sys, glob, re, numpy as np, soundfile as sf
from faster_whisper import WhisperModel
from resemblyzer import VoiceEncoder, preprocess_wav
import librosa
asr=WhisperModel("small.en", device="cpu", compute_type="int8")
enc=VoiceEncoder("cpu")
lines={v["id"]:v["line"] for f in ["voices.json","voices2.json"] for v in json.load(open(f))}
def norm(s): return re.sub(r"[^a-z ]","",s.lower()).split()
def wer(r,h):
    d=np.arange(len(h)+1)
    for i,rw in enumerate(r,1):
        p=d.copy(); d[0]=i
        for j,hw in enumerate(h,1): d[j]=min(p[j]+1,d[j-1]+1,p[j-1]+(rw!=hw))
    return d[-1]/max(1,len(r))
res={}; embs={}
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv)>1 else "out/design/*.wav")):
    vid=f.split("/")[-1].split("_vox")[0].split("_qwen")[0]
    y,sr=librosa.load(f,sr=16000)
    segs,_=asr.transcribe(y.astype(np.float32), beam_size=5); hyp=" ".join(s.text for s in segs); f0,_,_=librosa.pyin(y,fmin=60,fmax=400,sr=sr); f0m=float(np.nanmedian(f0))
    e=enc.embed_utterance(preprocess_wav(f)); embs[f]=e
    res[f]=dict(voice=vid,wer=round(wer(norm(lines.get(vid,"")),norm(hyp)),3),f0_median_hz=round(f0m,1),asr=hyp.strip())
    print(f, res[f]["wer"], res[f]["f0_median_hz"], hyp.strip()[:90], flush=True)
fs=list(embs); M=np.array([[float(embs[a]@embs[b]) for b in fs] for a in fs])
json.dump(dict(clips=res,files=fs,cos_sim=M.round(3).tolist()),open("logs/qa_design.json","w"),indent=1)
print("max cross-voice similarity:")
for i,a in enumerate(fs):
    j=max((k for k in range(len(fs)) if res[fs[k]]["voice"]!=res[a]["voice"]),key=lambda k:M[i,k]); print(a.split('/')[-1], "~", fs[j].split('/')[-1], round(M[i,j],3))
