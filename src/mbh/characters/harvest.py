"""Build characters/book01.json from the provisional starter roster + statistics computed from the KMG text.

Computed from text (not hand-written): sections, first_section, mentions, speaking_lines, key_sections.
Also writes characters/book01_unmapped_speakers.json: "<X> said," speakers not in the roster (review list).
usage: python -m mbh.characters.harvest  (run from repo root with src on PYTHONPATH)
"""
import json, re, pathlib, collections
from .starter_book01 import C, R

ROOT = pathlib.Path(__file__).resolve().parents[3]
TEXT = ROOT / "data/text/book01"
MIN_SECTIONS = 2  # "recurring" = appears in >=2 sections
FORCE = {"dasa", "hidimbi", "devas_chorus"}  # keep despite low counts (has a designed voice / merged-alias spelling in KMG)
# epithet/ambiguity filters: matches that are NOT the character
EXCLUDE = {
    "bharata": re.compile(r"O Bharata|Bharata(?:'s)? race|Bharata princes|Bharatas"),
}
COUNT_NOTES = {
    "bharata": "vocative 'O Bharata' and 'Bharata race' excluded; remaining counts still include epithets",
    "krishna": "'Krishna' also used for Draupadi (Krishnaa) in KMG; counts are noisy",
    "surya": "alias 'the Sun' inflates counts", "ganga": "river mentions included",
    "indra": "includes epithets like 'Indra among men'", "dharma_deva": "'Dharma' as virtue inflates counts",
    "hidimba": "KMG spells both Hidimba and his sister 'Hidimva'; counts merged", "hidimbi": "see hidimba",
    "chitrangada": "merged with Chitrangada son of Santanu (same spelling)",
}

def main():
    idx = json.loads((TEXT / "index.json").read_text())
    texts = {d["section"]: (TEXT / d["file"]).read_text(encoding="utf-8") for d in idx}
    # alias -> id, longest first so "Krishna-Dwaipayana" masks before "Krishna"
    alias = []
    for cid, row in C.items():
        name, aliases = row[0], row[1]
        base = re.sub(r"\s*\(.*\)", "", name)
        for a in {base, *aliases}:
            alias.append((a, cid))
    alias.sort(key=lambda x: -len(x[0]))
    pats = [(re.compile(r"(?<![\w-])" + re.escape(a) + r"(?![\w-])"), cid) for a, cid in alias]
    mentions = collections.defaultdict(collections.Counter)
    speaking = collections.Counter()
    unmapped = collections.Counter()
    say = re.compile(r"(?:^|[\"'(]\s*|\. )([A-Z][\w\- ]{1,40}?) (?:said|replied|continued|answered|asked)[,.:]")
    for sec, t in texts.items():
        masked = t
        for cid, ex in EXCLUDE.items():
            masked = ex.sub(" ", masked)
        for p, cid in pats:
            n = len(p.findall(masked))
            if n:
                mentions[cid][sec] += n
                masked = p.sub(" ", masked)
        for m in say.finditer(t):
            who = re.sub(r" (then|again|thereupon)$", "", re.sub(r"^(And|Then|Thereupon|The|O) ", "", m.group(1).strip()))
            hit = next((cid for p, cid in pats if p.fullmatch(who)), None)
            if hit: speaking[hit] += 1
            else: unmapped[who] += 1
    out, dropped = {}, []
    for cid, row in C.items():
        name, aliases, resp, gender, era, role, kind, pers, emo, brief, back = row
        secs = sorted(mentions[cid])
        if len(secs) < MIN_SECTIONS and cid not in FORCE:
            dropped.append(cid); continue
        key = [s for s, _ in mentions[cid].most_common(6)]
        out[cid] = dict(
            id=cid, name=name, aliases=aliases, respelling=resp, gender=gender, era_age=era, role=role, kind=kind,
            personality=pers, emotional_range=emo, voice_brief=brief,
            backstory=back, key_sections=sorted(key), first_section=(secs[0] if secs else None), sections=secs,
            mentions=sum(mentions[cid].values()), speaking_lines=speaking[cid],
            count_notes=COUNT_NOTES.get(cid, ""), provisional=True, source="starter roster (hand-written) + regex alias counts over KMG text; review needed",
        )
    rels = [dict(source=s, target=t, type=ty, provisional=True) for s, t, ty in R if s in out and t in out]
    dest = ROOT / "characters"; dest.mkdir(exist_ok=True)
    (dest / "book01.json").write_text(json.dumps(dict(book=1, characters=list(out.values()), relationships=rels), indent=1, ensure_ascii=False))
    (dest / "book01_unmapped_speakers.json").write_text(json.dumps(unmapped.most_common(), indent=1))
    print(f"roster={len(C)} recurring={len(out)} dropped={dropped} relationships={len(rels)}/{len(R)}")
    print("top unmapped speakers:", unmapped.most_common(25))

if __name__ == "__main__":
    main()
