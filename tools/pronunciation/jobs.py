"""Build a harness job list. usage: jobs.py ROUND VOICE[,VOICE] [--only term,..] [--formats f,..] [--extra term=form,..]
Formats: orig (KMG spelling), caps (old lexicon respelling), auto (speakable_respelling of it), p1/p2 (plain words in words.tsv)."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.pronounce import CARRIER, speakable_respelling

# Sound key for the romanised-spelling score: the intended sound where KMG's spelling hides it (s = sh).
KEY = {"Vaisampayana": "Vaishampayana", "Saunaka": "Shaunaka", "Ugrasrava": "Ugrashrava", "Krishna-Dwaipayana": "Krishna Dwaipayana"}

def words():
    rows = {}
    for line in (ROOT / "tools/pronunciation/words.tsv").read_text().splitlines():
        if line.startswith("#") or not line.strip(): continue
        term, ipa, plain = line.split("\t"); rows[term] = dict(intended=ipa, plain=plain.split("|"))
    return rows

def old_respellings():
    out = {}
    for line in (ROOT / "lexicon/book01.tsv").read_text().splitlines():
        p = line.split("\t")
        if len(p) > 1 and not line.startswith(("#", "term\t")): out.setdefault(p[0], p[1])
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("round"); ap.add_argument("voices")
    ap.add_argument("--only"); ap.add_argument("--formats", default="orig,caps,auto,p1,p2"); ap.add_argument("--extra", default="")
    a = ap.parse_args(); W = words(); R = old_respellings(); jobs = []
    only = set(a.only.split(",")) if a.only else set(W)
    extra = {}
    for kv in filter(None, a.extra.split(";")):
        t, f = kv.split("="); extra.setdefault(t, []).append(f)
    for voice in a.voices.split(","):
        for term in [t for t in W if t in only]:
            forms = {"orig": term.replace("-", " "), "caps": R.get(term, term), "auto": speakable_respelling(R.get(term, term))}
            for i, p in enumerate(W[term]["plain"], 1): forms[f"p{i}"] = p
            sel = {k: v for k, v in forms.items() if k in a.formats.split(",")}
            for i, f in enumerate(extra.get(term, []), 1): sel[f"x{i}"] = f
            for fmt, form in sel.items():
                jobs.append(dict(round=a.round, voice=voice, term=term, fmt=fmt, form=form, text=CARRIER.format(word=form),
                                 intended=W[term]["intended"], key=KEY.get(term, term), out=f"build/pron/{a.round}/{voice}/{term}__{fmt}.wav"))
    print(json.dumps(jobs, indent=1))
