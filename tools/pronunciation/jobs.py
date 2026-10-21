"""Build a harness job list. usage: jobs.py ROUND VOICE[,VOICE] [--only term,..] [--formats f,..] [--extra term=form,..]
Formats: orig (KMG spelling), caps (old lexicon respelling), auto (speakable_respelling of it), p1/p2 (plain words in words.tsv)."""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / "src"))
from mbh.episode.pronounce import CARRIER, speakable_respelling

# Sound key for the romanised-spelling score: the intended sound where KMG's spelling hides it (s = sh).
KEY = {"Vaisampayana": "Vaishampayana", "Saunaka": "Shaunaka", "Ugrasrava": "Ugrashrava", "Krishna-Dwaipayana": "Krishna Dwaipayana",
       # Episode 2: KMG writes the sh-sound as s
       "Duhsasana": "Duhshasana", "Sakuni": "Shakuni", "Sakra": "Shakra", "Sastras": "Shastras", "Sikhandin": "Shikhandin",
       "Aswatthaman": "Ashvatthaman", "Dhristadyumna": "Dhrishtadyumna", "Santanu": "Shantanu", "Saivya": "Shaivya", "Dasaratha": "Dasharatha", "Sakti": "Shakti",
       # Episode 4
       "Sweta": "Shweta", "Aisika": "Aishika", "Khilvansa": "Khilvamsha", "Sisupala-badha": "Shishupala vadha",
       # Episode 5
       "Sisupala": "Shishupala", "Vaisravana": "Vaishravana", "Lomasa": "Lomasha", "Rishyasringa": "Rishyashringa",
       "Sarngi": "Sharngi", "Saryati": "Sharyati", "Kailasa": "Kailasha", "Arshtishena": "Arshtishena", "Kartavirya": "Kartavirya",
       "Dhaumya": "Dhaumya", "Sivi": "Shibi", "Vasishtha": "Vashishtha", "Sakuntala": "Shakuntala", "Animandavya": "Animandavya"}

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

def plan(round_name, voices, *, only=None, formats=None, extra=None, out_prefix="build/pron"):
    """One clip per voice × term × form. Terms missing from words.tsv still get orig/extra forms.

    ``voices`` is a list of voice ids. ``only`` is a set of terms (None = every words.tsv term).
    ``extra`` maps a term to extra spoken forms. ``out`` paths are relative to the repo unless absolute.
    """
    table = words(); respellings = old_respellings()
    chosen = list(formats or ["orig", "caps", "auto", "p1", "p2"])
    extra = extra or {}
    if only is None:
        terms = list(table)
    else:
        wanted = list(only)
        known = {term for term in wanted if term in table}
        terms = [term for term in table if term in known] + [term for term in wanted if term not in table]
    jobs = []
    for voice in voices:
        for term in terms:
            forms = {}
            if "orig" in chosen:
                forms["orig"] = term.replace("-", " ")
            if "caps" in chosen:
                forms["caps"] = respellings.get(term, term)
            if "auto" in chosen:
                forms["auto"] = speakable_respelling(respellings.get(term, term))
            for i, plain in enumerate((table.get(term) or {}).get("plain") or [], 1):
                if f"p{i}" in chosen:
                    forms[f"p{i}"] = plain
            for i, form in enumerate(extra.get(term, []), 1):
                forms[f"x{i}"] = form
            intended = (table.get(term) or {}).get("intended") or term
            for fmt, form in forms.items():
                jobs.append(dict(
                    round=round_name, voice=voice, term=term, fmt=fmt, form=form,
                    text=CARRIER.format(word=form), intended=intended, key=KEY.get(term, term),
                    out=f"{out_prefix}/{round_name}/{voice}/{term}__{fmt}.wav",
                ))
    return jobs


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("round"); ap.add_argument("voices")
    ap.add_argument("--only"); ap.add_argument("--formats", default="orig,caps,auto,p1,p2"); ap.add_argument("--extra", default="")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    extra = {}
    for kv in filter(None, a.extra.split(";")):
        t, f = kv.split("="); extra.setdefault(t, []).append(f)
    print(json.dumps(plan(a.round, a.voices.split(","), only=only, formats=a.formats.split(","), extra=extra), indent=1))
