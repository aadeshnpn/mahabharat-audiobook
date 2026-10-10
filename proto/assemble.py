"""Assemble rendered segments: gaps by speaker change, celestial FX, loudness-normalize, export WAV+MP3."""
import json, sys, subprocess, numpy as np, soundfile as sf, librosa, os
d=sys.argv[1]; script=json.load(open(sys.argv[2])); log=json.load(open(f"{d}/render_log.json")); outbase=sys.argv[3]
SR=48000; parts=[]; prev=None
for seg,l in zip(script["segments"],log["segments"]):
    f=l["file"]
    if seg.get("fx")=="celestial":
        fx=f.replace(".wav","_fx.wav")
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",f,"-af","aecho=0.8:0.85:60|120|240:0.45|0.3|0.2,volume=0.9",fx],check=True); f=fx
    y,sr=librosa.load(f,sr=SR); y,_=librosa.effects.trim(y,top_db=35)
    gap=0.0 if prev is None else (0.25 if seg["speaker"]==prev else 0.5)
    parts+= [np.zeros(int(gap*SR)), y]; prev=seg["speaker"]
y=np.concatenate(parts+[np.zeros(SR)]); tmp=outbase+"_raw.wav"; sf.write(tmp,y,SR)
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",tmp,"-af","loudnorm=I=-16:TP=-1.5:LRA=11","-ar","48000",outbase+".wav"],check=True)
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",outbase+".wav","-b:a","160k",outbase+".mp3"],check=True); os.remove(tmp)
print(outbase, round(len(y)/SR,1),"s")
