"""Aggregate harness scores per (term, form) across voices and pick the spoken form per term.
usage: select.py [--min-voices 2] [--json out.json]   (reads build/pron/scores.json)
A take passes when the anchors are found, it is not spelled out, and similarity >= 0.8 (or ASR heard the term).\nA form is verified when it passes on >= --min-voices distinct voices, >= 2/3 of its conclusive takes pass, and no take is spelled out. Ties prefer the KMG spelling ("orig"),
then the higher mean similarity."""
import argparse, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
import sys; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.pronounce import is_tts_safe
PREF = {"orig": 0}

def aggregate(scores):
    agg = defaultdict(lambda: dict(pass_voices=set(), npass=0, nfail=0, retakes=0, sims=[], spelled=0, heard=[], fmt=""))
    for s in scores.values():
        a = agg[(s["term"], s["form"])]; a["fmt"] = a["fmt"] or s["fmt"]
        if s.get("inconclusive"):
            a["retakes"] += 1; continue
        if s["passed"]:
            a["npass"] += 1; a["pass_voices"].add(s["voice"])
        else:
            a["nfail"] += 1
        a["sims"].append(s["sim"]); a["spelled"] += s["spelled"]; a["heard"].append(f"{s['voice'][:4]}:{s['heard']}")
    return agg


def verdict(a, min_voices):
    n = a["npass"] + a["nfail"]
    return len(a["pass_voices"]) >= min_voices and not a["spelled"] and n > 0 and a["npass"] / n >= 2 / 3


def choose(agg, min_voices):
    by_term = defaultdict(list)
    for (term, form), a in agg.items():
        if not is_tts_safe(form):
            continue  # caps/hyphen guides are the baseline being replaced, never a candidate
        n = a["npass"] + a["nfail"]
        score = (verdict(a, min_voices), len(a["pass_voices"]), a["npass"] / n if n else 0, -PREF.get(a["fmt"], 1),
                 sum(a["sims"]) / max(1, len(a["sims"])))
        by_term[term].append((score, form, a))
    out = {}
    for term, rows in by_term.items():
        rows.sort(key=lambda r: r[0], reverse=True)
        (ok, nv, rate, _p, sim), form, a = rows[0]
        out[term] = dict(spoken=form, verified=bool(ok), pass_voices=sorted(a["pass_voices"]), takes_passed=a["npass"],
                         takes_failed=a["nfail"], retakes=a["retakes"], mean_sim=round(sim, 3), fmt=a["fmt"], heard=a["heard"],
                         tried={f: dict(fmt=x["fmt"], voices=sorted(x["pass_voices"]), passed=x["npass"], failed=x["nfail"],
                                        retakes=x["retakes"], sim=round(sum(x["sims"]) / max(1, len(x["sims"])), 2)) for _s, f, x in rows})
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--min-voices", type=int, default=2); ap.add_argument("--json")
    a = ap.parse_args(); scores = json.loads((ROOT / "build/pron/scores.json").read_text())
    res = choose(aggregate(scores), a.min_voices)
    for t, r in res.items():
        print(f"{t:18} {'VERIFIED' if r['verified'] else 'pending '} {r['spoken']!r:22} voices={','.join(v[:4] for v in r['pass_voices']):15} takes {r['takes_passed']}/{r['takes_passed'] + r['takes_failed']} (+{r['retakes']} retake) sim={r['mean_sim']}")
    print(f"verified {sum(r['verified'] for r in res.values())}/{len(res)}")
    if a.json: Path(a.json).write_text(json.dumps(res, indent=1, ensure_ascii=False))
