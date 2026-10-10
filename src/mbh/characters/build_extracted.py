"""Build characters/book01.json from the text-grounded profiles in mbh.characters.extracted.

Counts (sections, mentions, speech turns) are computed from data/text/book01 with alias-disambiguation rules;
every section citation in profiles and relationships is checked against the text (the character, or both
parties of an edge, must be mentioned in the cited section). Run: PYTHONPATH=src python -m mbh.characters.build_extracted
"""
import re, json, collections, pathlib, time, sys
from mbh.characters.extracted import CHARS, RELS

ROOT = pathlib.Path(__file__).resolve().parents[3]
TXT = ROOT / "data" / "text" / "book01"
SKIP = {176}                     # §176 is a near-verbatim duplicate of §177 in the source (both have a '(???—JBH)' gap)
SUMMARY = {1, 2}                 # table of contents / summary of the whole epic
LISTS = {65, 66, 67, 94, 95, 117, 186, 188}   # genealogy / catalogue sections (mentions there don't make someone "recurring")
T = {i: re.sub(r"\s+", " ", (TXT / f"{i:03d}.txt").read_text(encoding="utf-8")) for i in range(1, 237)}
BY = {c["id"]: c for c in CHARS}

from mbh.text.krishna import resolve as resolve_krishna
AMBIG = {"Krishna", "Rama", "Drona", "Dhaumya", "Jaratkaru", "Hidimva", "Chitrangada", "Kasyapa", "Bhima", "Bhimasena",
         "Dharmaraja", "Gandharva", "Gautama", "Bhargava", "Partha", "Dhritarashtra", "Salya", "Kali", "Bhadra", "Hidimba",
         "Hidimbi", "Baka", "Vasu", "Hara", "Sakti", "Yama", "Marut", "Kama"}
KR = r"Vasudeva|Kesava|Janardana|Govinda|Madhava|Achyuta|Hrishikesa"
DR = r"Draupadi|Panchali|Yajnaseni|Drupada"

def _names(c):
    out = []
    for a in [re.sub(r" \(.*\)", "", c["name"])] + c["aliases"]:
        a = re.sub(r" \(.*\)", "", a).strip()
        if a and a not in AMBIG: out.append(a)
    return out
PATS = {}
for c in CHARS:
    strong = [a for a in _names(c) if a[0].isupper() and not a.startswith(("The ", "Rishi "))]
    weak = [a for a in _names(c) if a not in strong]            # generic descriptors: only count inside key sections
    PATS[c["id"]] = (re.compile(r"\b(" + "|".join(map(re.escape, sorted(strong, key=len, reverse=True))) + r")\b") if strong else None,
                     re.compile(r"\b(" + "|".join(map(re.escape, sorted(weak, key=len, reverse=True))) + r")\b", re.I) if weak else None)

def sentences(t): return re.split(r"(?<=[.!?])['\"]?\s+(?=[\"']?[A-Z])", t)

_KRES = {}
def _krishna_whos(s, sec, start, length):
    """Per-occurrence resolution of bare 'Krishna' (mbh.text.krishna) inside sec[start:start+length]."""
    if s not in _KRES: _KRES[s] = resolve_krishna(s, sec)
    return [w for a, b, w, _ in _KRES[s] if start <= a < start + length]

def hits(s, sent, sec, pos=None):
    h = collections.Counter()
    x = re.sub(r"Krishna[- ]Dwaipayana", "Dwaipayana", sent)
    for cid, (st, wk) in PATS.items():
        n = len(st.findall(x)) if st else 0
        if wk and s in BY[cid]["key_sections"]: n += len(wk.findall(x))
        if n: h[cid] += n
    w = lambda a: len(re.findall(r"\b" + a + r"\b", x))
    if w("Krishna"):
        start = pos if pos is not None else sec.find(sent)
        whos = _krishna_whos(s, sec, start, len(sent)) if start >= 0 else []
        for who in whos:
            if who: h["vyasa" if who == "vyasa" else who] += 1
    if w("Rama"):
        if s >= 186 and not re.search("Jamadagni|Bhargava|Bhrigu", x): h["balarama"] += w("Rama")
        elif s not in (2, 104) and re.search("Jamadagni|Bhargava|Bhrigu|Kshatriya", sec): h["parasurama"] += w("Rama")
    if w("Drona"): h["drona_sarngaka" if 231 <= s <= 235 else "drona"] += w("Drona")
    if w("Dhaumya"): h["ayoda_dhaumya" if s == 3 else "dhaumya"] += w("Dhaumya")
    if w("Jaratkaru"):
        h["jaratkaru_naga" if re.search(r"\b(she|her|sister|wife|mother|daughter|woman|lady|maiden)\b", x, re.I) else "jaratkaru_rishi"] += w("Jaratkaru")
    if w("Hidimva"):
        h["hidimbi" if s >= 157 or re.search(r"\b(she|her|sister|woman|maiden|Rakshasi|wife|female)\b", x, re.I) else "hidimba"] += w("Hidimva")
    if w("Chitrangada"): h["chitrangada_kuru" if s < 150 else "chitrangada"] += w("Chitrangada")
    if w("Kasyapa"): h["kasyapa_healer" if s in (42, 43, 50) else "kasyapa"] += w("Kasyapa")
    if s != 3 and (w("Bhima") or w("Bhimasena")): h["bhima"] += w("Bhima") + w("Bhimasena")
    if w("Dharmaraja"): h["dharma_deva" if s < 100 else "yudhishthira"] += w("Dharmaraja")
    if 172 <= s <= 185 and w("Gandharva"): h["chitraratha"] += w("Gandharva")
    if s in (129, 130) and w("Gautama"): h["saradwat" if s == 130 else "kripa"] += w("Gautama")
    if 76 <= s <= 85 and w("Bhargava"): h["sukra"] += w("Bhargava")
    if w("Partha"): h["arjuna"] += w("Partha")
    if w("Dhritarashtra") and s not in (3, 35, 57): h["dhritarashtra"] += w("Dhritarashtra")   # Naga Dhritarashtra in §3/35/57
    if w("Salya") and s != 102: h["salya"] += w("Salya")                                        # §102 'Salya' = Salwa of Saubha
    if w("Bhadra") and s >= 221: h["subhadra"] += w("Bhadra")
    if w("Sakti"): h["saktri"] += w("Sakti")
    if w("Yama") and s not in (55,): h["dharma_deva"] += w("Yama")
    if s == 138 and w("Kama"): h["karna"] += w("Kama")                                          # misprint for Karna
    if s == 63 and w("Kali"): h["satyavati"] += w("Kali")
    return h

# ---- speech turns ----
SAY = r"(?:said|replied|answered|asked|continued|rejoined|spoke|exclaimed)"
GENERIC = {  # (section, tag) -> id : resolved 'unmapped' speakers
    (1, "The Rishi"): "naimisha_rishis", (2, "The Rishis"): "naimisha_rishis", (4, "The holy men"): "naimisha_rishis",
    (12, "The Rishi"): "dundubha", (104, "The Rishi"): "dirghatamas", (33, "Santi"): "sauti", (47, "the Rishi"): "jaratkaru_rishi",
    (162, "The Brahmana"): "ekachakra_brahmana", (168, "The Brahmana"): "brahmana_guest", (169, "The Brahmana"): "brahmana_guest",
    (95, "She"): "satyavati", (100, "She"): "satyavati", (98, "The king"): "santanu", (138, "Kama"): "karna",
    (225, "Rudra"): "mahadeva", (64, "Hari"): "vishnu", (9, "Dharmaraja"): "dharma_deva", (172, "The Gandharvi"): "kumbhinasi",
    (118, "The deer"): "kindama", (179, "His daughter-in-law"): "adrisyanti", (233, "Their mother"): "jarita",
    (120, "The Rishis"): "satasringa_rishis", (2, "Rama"): "parasurama", (48, "He"): "jaratkaru_rishi", (108, "Thus"): "mandavya", (111, "the Rishi"): "durvasa",
    (147, "He"): "vidura", (156, "She"): "kunti", (163, "the Brahmana"): "ekachakra_brahmana", (177, "He"): "vasishtha", (217, "He"): "arjuna",
    (56, "The Ritwiks"): "sacrificial_priests", (56, "The Sadasyas"): "sacrificial_priests", (231, "The celestials"): "devas_chorus",
}
UNRESOLVED = {(3, "He"): "Sarama's son (the dog Sarameya), one line; not a recurring character",
              (3, "his mother"): "Sarama (celestial bitch), one line",
              (18, "the Ocean"): "the Ocean personified, one line in the churning story",
              (37, "Others"): "unnamed snakes debating how to stop the sacrifice (generic crowd)",
              (190, "Others"): "unnamed kings/Brahmanas at the swayamvara (generic crowd)",
              (12, "Thus"): "not a speaker ('Thus asked, his father related')",
              (22, "They"): "unnamed snakes (Kadru's sons), one line",
              (63, "They"): "the fishermen reporting the fish-born twins to Uparichara, one line",
              (104, "She"): "Mamata, wife of Utathya, rebuffing Vrihaspati (one section; not recurring)",
              (104, "Vali"): "King Vali who saves Dirghatamas (one section; not recurring)",
              (167, "The Pandavas"): "the Pandava brothers speaking together (group line; read by Yudhishthira or narrator)",
              (186, "The Brahmanas"): "travelling Brahmanas bound for the swayamvara (generic crowd)",
              (209, "Some"): "citizens of Hastinapura (generic crowd)",
              (215, "The Brahmana"): "the Brahmana whose kine were stolen (one section; not recurring)",
              (219, "the Brahmana"): "the Brahmana who cursed Varga and her friends, one line (not recurring)",
              (39, "Well"): "not a speaker ('Well said, well said!' exclaimed by the serpents)"}

# Citations where the character is present only by epithet/pronoun; the quoted phrase must occur in that section.
EPITHET_OK = {
    ("dundubha", 12): "The Rishi replied", ("kadru", 15): "the mother of the snakes", ("vinata", 34): "bondage of his mother",
    ("aruna", 16): "the child in the egg became angry and cursed his mother", ("jaratkaru_rishi", 14): "That Brahmana of rigid vows",
    ("parikshit", 43): "best of monarchs", ("samika", 40): "that Muni observing then the vow of silence", ("samika", 41): "on the shoulder of thy sire",
    ("sacrificial_priests", 51): "his priest and Ritwiks", ("agni", 224): "a certain Brahmana came", ("salya", 102): "king Salya of immeasurable prowess",
    ("nakula", 126): "the twin children begotten upon Madri", ("sahadeva", 126): "the twin children begotten upon Madri",
    ("samvarana", 174): "as the monarch fell down", ("draupadi", 191): "bestowing his daughter on that Brahmana",
    ("draupadi", 201): "Krishna also, attired in red silk", ("garuda", 25): "carried (on his back) the snakes", ("vasuki", 25): "carried (on his back) the snakes",
    ("duhsasana", 115): "begat upon Gandhari a hundred sons", ("ekachakra_brahmana", 161): "her afflicted parents",
    ("ekachakra_brahmani", 161): "her afflicted parents", ("ekachakra_brahmana", 163): "Grieve not at all, O Brahmana",
    ("mandapala", 232): "Your cruel father left me",
}
EPITHET_USED = []

# unnamed-descriptor speakers in the quote-anchored pass: (from §, to §, clause regex, id)
PHRASE_SPEAKERS = [(100, 100, r"chief of the fishermen|[Tt]he fisherman|the latter addressed", "dasa"),
                   (118, 118, r"[Tt]he deer", "kindama"), (217, 217, r"the king", "chitravahana"), (155, 155, r"the Rakshasa", "hidimba"),
                   (160, 162, r"the Brahmana", "ekachakra_brahmana"), (161, 161, r"his wife|the Brahmani", "ekachakra_brahmani")]

def hid(s, clause):
    """Speaker resolver for the shared KMG name 'Hidimva' (brother vs sister)."""
    if re.search(r"\b(his|he|chief|cannibal)\b", clause) and not re.search(r"her brother", clause): return "hidimba"
    if re.search(r"\b(she|her|woman|Rakshasi|sister|maiden)\b", clause): return "hidimbi"
    return "hidimbi" if s >= 155 else "hidimba"

def speech_counts():
    per = {c["id"]: collections.Counter() for c in CHARS}
    for s in range(1, 237):
        if s in SKIP: continue
        t = T[s]
        for m in re.finditer(r"(?:^|[\"'‘“]\s*|[.!?]\s+)(?:And |Then |Thereupon |Hearing this, |And then )?((?:The |the )?[A-Z][\w\-]*(?: [A-Z][\w\-]*)?)(?: then| again| thereupon| also)? " + SAY + r"[,:.]", t):
            tag = m.group(1)
            cid = GENERIC.get((s, tag)) or (hid(s, t[max(0, m.start() - 200):m.end()]) if tag == "Hidimva" else None)
            if not cid:
                hh = hits(s, tag, t, m.start(1))
                if len(hh) == 1: cid = next(iter(hh))
                elif tag in ("Kasyapa",): cid = "kasyapa_healer" if s in (42, 43, 50) else "kasyapa"
            if cid: per[cid][s] += 1
        # quote-anchored pass: each opening quote not already credited above is attributed to the first
        # character named in the clause before it, if that clause carries a speech verb.
        done = {m.end() for m in re.finditer(r"(?:^|[\"'‘“]\s*|[.!?]\s+)(?:And |Then |Thereupon |Hearing this, |And then )?(?:(?:The |the )?[A-Z][\w\-]*(?: [A-Z][\w\-]*)?)(?: then| again| thereupon| also)? " + SAY + r"[,:.]", t)}
        for q in re.finditer(r"(?:saying|said|replied|answered|spake|spoke|exclaimed|asked|these words|thus)(?: in reply| unto (?:him|her|them)| (?:him|her|them))?[,:.]?\s*['\"‘“]", t):
            if any(abs(q.end() - d) < 4 for d in done): continue
            k = max(t.rfind(x, 0, q.start()) for x in (". ", "' ", "\" ", "! ", "? ", "\n"))
            clause = t[k + 1:q.start()]
            if len(clause) > 260: clause = clause[-260:]
            first = None
            for nm in re.finditer(r"[A-Z][\w\-]+(?: [A-Z][\w\-]+)?", clause):
                pre = clause[max(0, nm.start() - 4):nm.start()]
                if re.search(r"(\bO |\bof |\bto |unto |upon |commanded |addressed |addressing |beholding |seeing )$", clause[max(0, nm.start() - 11):nm.start()]) or clause[nm.end():nm.end() + 2] == "'s": continue
                hh = hits(s, nm.group(0), t, k + 1 + max(0, len(t[k + 1:q.start()]) - 260) + nm.start())
                if nm.group(0) == "Hidimva":
                    hh = {hid(s, clause): 1}
                if len(hh) == 1: first = next(iter(hh)); break
            if not first and s == 3 and re.search(r"\b(preceptor|[Mm]aster)\b", clause) and "preceptress" not in clause:
                first = "veda" if q.start() > t.find("Veda having signified") else "ayoda_dhaumya"   # §3: two teachers in turn
            if not first:
                for lo, hi, pat, cid in PHRASE_SPEAKERS:
                    if lo <= s <= hi and re.search(pat, clause): first = cid; break
            if first: per[first][s] += 1
        # long-form tags: '<Name> said unto/to ...', 'his wife said', 'the daughter ... addressed them'
        for cid, pat in (("ekachakra_brahmani", r"his wife said"), ("ekachakra_daughter", r"the daughter was filled with grief, and she addressed")):
            if s in BY[cid]["key_sections"]: per[cid][s] += len(re.findall(pat, t))
    return per

def krishna_rules():
    """Where bare 'Krishna' means Draupadi (TTS says Draupadi), Vasudeva or Vyasa; see mbh/text/krishna.py."""
    from mbh.text import krishna as K
    by = {"draupadi": collections.defaultdict(int), "krishna": collections.defaultdict(int), "vyasa": collections.defaultdict(int)}
    rules = collections.Counter()
    for s in range(1, 237):
        if s in SKIP: continue
        for a, b, who, rule in K.resolve(s, T[s]):
            if who: by[who][s] += 1
            rules[rule] += 1
    return {"Krishna": {"decision": "where 'Krishna' means Draupadi, attribute to draupadi and TTS says '" + K.TTS_DRAUPADI + "' (alias 'Krishnaa')",
                        "tts_replacement_for_draupadi": K.TTS_DRAUPADI, "resolver": "mbh.text.krishna.resolve / speakable",
                        "occurrences": {k: sum(v.values()) for k, v in by.items()}, "rules_used": dict(rules),
                        "hand_overrides": len(K.OVERRIDES),
                        "draupadi_sections": {str(k): v for k, v in sorted(by["draupadi"].items())},
                        "vasudeva_sections": {str(k): v for k, v in sorted(by["krishna"].items())},
                        "vyasa_sections": {str(k): v for k, v in sorted(by["vyasa"].items())}}}

def main():
    t0 = time.time()
    secs = {c["id"]: collections.Counter() for c in CHARS}
    for s in range(1, 237):
        if s in SKIP: continue
        for sent in sentences(T[s]):
            for cid, n in hits(s, sent, T[s]).items(): secs[cid][s] += n
    speech = speech_counts()
    problems = []
    def mentioned(cid, s):
        if secs[cid][s] > 0: return True
        ph = EPITHET_OK.get((cid, s))
        if ph and ph in T[s]: EPITHET_USED.append(f"{cid} §{s}: '{ph}'"); return True
        return False
    out = []
    for c in CHARS:
        cid = c["id"]; sc = secs[cid]
        narrative = sorted(s for s in sc if s not in SUMMARY | LISTS)
        cited = sorted({int(x) for x in re.findall(r"§(\d+)", c["backstory"])} | set(c["key_sections"]))
        for s in cited:
            if not mentioned(cid, s): problems.append(f"{cid}: cited §{s} but no mention found")
        flags = [f for f in c["flags"] if f != "non_speaking"]
        if sum(speech[cid].values()) == 0: flags.append("non_speaking")   # derived from counts, not hand-set
        if len(narrative) < 2 and not any(f in flags for f in ("single_section_speaker", "chorus")): flags.append("below_threshold")
        notes = []
        if cid in ("indra", "agni", "surya", "brahma", "vishnu", "mahadeva", "dharma_deva", "vayu", "varuna", "ganga", "arjuna"):
            notes.append("mention count inflated by epithets/similes (e.g. 'like Indra', 'son of Pritha', river Ganga)")
        if cid == "krishna": notes.append("bare 'Krishna' attributed to Vasudeva only in sections that also use his other names; elsewhere to Draupadi")
        if cid == "draupadi": notes.append("KMG often calls her 'Krishna'; attributed by section context")
        if cid in ("jaratkaru_rishi", "jaratkaru_naga", "hidimba", "hidimbi"): notes.append("shared name; split by pronoun/context heuristics")
        if cid == "dhritarashtra": notes.append("excludes the Naga Dhritarashtra (§3, §35, §57)")
        if cid == "salya": notes.append("§102 'Salya' (fights Bhishma) is Salwa of Saubha; excluded")
        if cid == "drona": notes.append("excludes the Sarngaka bird Drona (§231–§235)")
        if cid == "bhima": notes.append("excludes Janamejaya's brother Bhimasena (§3)")
        if cid == "karna": notes.append("'Kama' in §138 is a misprint for Karna")
        sp = speech[cid]
        out.append({**{k: c[k] for k in ("id", "name", "aliases", "respelling", "gender", "kind", "era_age", "role",
                                          "personality", "emotional_range", "voice_brief", "backstory", "key_sections")},
                    "first_section": min(narrative or sorted(sc) or [None]),
                    "sections": sorted(sc), "narrative_sections": narrative, "summary_mentions": sorted(s for s in sc if s in SUMMARY),
                    "mentions": sum(sc.values()), "speaking_lines": sum(sp.values()),
                    "speech_by_section": {str(k): v for k, v in sorted(sp.items())},
                    "flags": flags, "provenance": c["provenance"], "voice_group": c.get("voice_group", ""),
                    "count_notes": "; ".join(notes), "provisional": False,
                    "source": ("text-extracted: profile written from a reading of the KMG Book 1 text with § citations; counts computed by build_extracted.py"
                               if c["provenance"] == "text-extracted" else "hand-added entry (generic voice); citations checked against the text")})
    for o in out:   # split descriptive kind into a base category (graph colour / filter) + detail
        km = re.match(r"\s*([A-Za-z]+)\s*(?:\((.*)\))?\s*$", o["kind"])
        if km: o["kind"], o["kind_detail"] = km.group(1).lower(), km.group(2) or ""
        else: o["kind_detail"] = ""
    rels = []
    for r in RELS:
        s = int(r["section"].strip("§").split("–")[0])
        ok = mentioned(r["source"], s) and mentioned(r["target"], s)
        if not ok: problems.append(f"rel {r['source']} -{r['type']}-> {r['target']} §{s}: " +
                                    ", ".join(x for x in (r["source"], r["target"]) if not mentioned(x, s)) + " not found in section")
        rels.append({"source": r["source"], "target": r["target"], "type": r["type"], "label": "",
                     "notes": (f"{r['section']}: {r['note']}" if r["note"] else r["section"]), "provisional": False,
                     "provenance": "text-extracted", "section": s})
    data = {"book": 1, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "method": "text-grounded extraction (LLM reading of KMG text) + computed counts",
            "skipped_sections": {"176": "duplicate of 177 in source; original §176 text missing"},
            "characters": out, "relationships": rels,
            "resolved_speakers": {f"§{k[0]} {k[1]}": v for k, v in GENERIC.items()},
            "unresolved_speakers": {f"§{k[0]} {k[1]}": v for k, v in UNRESOLVED.items()},
            "name_rules": krishna_rules(),
            "validation_problems": problems, "epithet_citations": sorted(set(EPITHET_USED))}
    return data, problems, time.time() - t0

if __name__ == "__main__":
    data, problems, dt = main()
    print(f"{len(data['characters'])} characters, {len(data['relationships'])} relationships, {len(problems)} citation problems ({dt:.1f}s)")
    for p in problems: print("  ", p)
    if "--write" in sys.argv:
        (ROOT / "characters" / "book01.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
        print("wrote characters/book01.json")
