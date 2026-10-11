"""Encode a mastered WAV to MP3 and verify the MP3 itself still hits the loudness target (lossy encoding shifts it).
usage: encode_mp3.py IN.wav OUT.mp3 [--target -16] [--tp -1.0] [--bitrate 192k]
Measures the decoded MP3 with ffmpeg's EBU R128 meter; if integrated loudness is off by > 0.2 LU, re-encodes once with a
gain correction (capped so true peak stays under --tp). Prints JSON {lufs, true_peak_db, gain_db}."""
import argparse, json, re, subprocess
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("dst")
ap.add_argument("--target", type=float, default=-16.0); ap.add_argument("--tp", type=float, default=-1.0); ap.add_argument("--bitrate", default="192k")
a = ap.parse_args()
def enc(g):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.src, "-af", f"volume={g:.2f}dB", "-codec:a", "libmp3lame", "-b:a", a.bitrate, a.dst], check=True)
def meas():
    err = subprocess.run(["ffmpeg", "-nostats", "-i", a.dst, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summ = err[err.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1)), float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))
g = 0.0; enc(g); lufs, tp = meas()
if abs(lufs - a.target) > 0.2:
    g = min(a.target - lufs, a.tp - tp); enc(g); lufs, tp = meas()
print(json.dumps(dict(out=a.dst, lufs=lufs, true_peak_db=tp, gain_db=round(g, 2))))
