import re,json,collections,sys
sys.path.insert(0,'work'); from roster import R
SKIP={1,2,176}   # 1-2: table of contents / summary; 176: duplicate of 177 in source
LISTS={63,65,66,67,94,95,117,186,188}  # genealogy/catalogue sections
T={i:open(f'data/text/book01/{i:03d}.txt',encoding='utf-8').read() for i in range(1,237)}
KR=r"Vasudeva|Kesava|Janardana|Govinda|Madhava|Achyuta|Hrishikesa"
DR=r"Draupadi|Panchali|Yajnaseni|Drupada"
def sents(t):
    t=re.sub(r"\s+"," ",t)
    return re.split(r"(?<=[.!?])['\"]?\s+(?=[\"']?[A-Z])",t)
def owners(s,sent,sec_t):
    """return list of (cid) mentioned in this sentence"""
    hits=set()
    x=re.sub(r"Krishna[- ]Dwaipayana","Dwaipayana",sent)
    for cid,(nm,al) in R.items():
        names=[re.sub(r" \(.*\)","",nm)]+al
        for a in names:
            if a in("Krishna","Rama","Drona","Dhaumya","Jaratkaru","Hidimva","Chitrangada","Kasyapa","Bhima","Bhimasena","Vasu","Dharmaraja","Gandharva","the Gandharva","Gautama","Bhargava","the Sun","Partha"): continue
            if re.search(r"\b"+re.escape(a)+r"\b",x): hits.add(cid);break
    w=lambda a: re.search(r"\b"+a+r"\b",x)
    if w("Krishna"):
        if re.search(KR,sec_t): hits.add("krishna")
        elif re.search(DR,sec_t): hits.add("draupadi")
    if w("Rama"):
        if s>=186 and not re.search("Jamadagni|Bhargava|Bhrigu",x): hits.add("balarama")
        elif re.search("Jamadagni|Bhargava|Bhrigu|Kshatriya|Kshatriyas",sec_t) and s!=2: hits.add("parasurama")
    if w("Drona"): hits.add("drona_sarngaka" if 231<=s<=235 else "drona")
    if w("Dhaumya"): hits.add("ayoda_dhaumya" if s==3 else "dhaumya")
    if w("Jaratkaru"): hits.add("jaratkaru_naga" if re.search(r"\b(she|her|sister|wife|mother|daughter|woman|lady|maiden)\b",x,re.I) else "jaratkaru_rishi")
    if w("Hidimva"): hits.add("hidimva_rakshasi" if s>=157 or re.search(r"\b(she|her|sister|woman|maiden|Rakshasi|wife)\b",x,re.I) else "hidimva")
    if w("Chitrangada"): hits.add("chitrangada_kuru" if s<150 else "chitrangada_manipura")
    if w("Kasyapa"): hits.add("kasyapa_healer" if s in(42,43,50) else "kasyapa")
    if (w("Bhima") or w("Bhimasena")) and s!=3: hits.add("bhima")
    if w("Vasu") and s==63: hits.add("uparichara")
    if w("Dharmaraja"): hits.add("dharma" if s<100 else "yudhishthira")
    if (w("Gandharva") or w("the Gandharva")) and 172<=s<=185: hits.add("angaraparna")
    if w("Gautama") and s in(129,130): hits.add("saradwat")
    if w("Bhargava") and 76<=s<=85: hits.add("sukra")
    if w("Partha"): hits.add("arjuna")
    if w("the Sun") and re.search("Kunti|Pritha|Karna|Tapati|Samvarana|Aruna|Garuda",x): hits.add("surya")
    return hits
CUE=re.compile(r"\b(son|sons|daughter|wife|wives|husband|brother|brothers|sister|father|mother|sire|begot|begat|born|married|wedded|disciple|preceptor|pupil|taught|slew|slain|killed|cursed|curse|friend|enemy|foe|incarnat\w*|portion of|grandson|grandsire|uncle|nephew|vow|priest|nurse|foster|adopted|ally|rival|guard\w*|protect\w*)\b",re.I)
SAY=r"(said|replied|answered|asked|continued|spoke|rejoined|addressed)"
if __name__=="__main__":
    stat={c:{"secs":collections.Counter(),"evid":[],"speak":collections.Counter(),"listonly":set()} for c in R}
    for s in range(1,237):
        if s in SKIP: continue
        t=T[s]; flat=re.sub(r"\s+"," ",t)
        for sent in sents(t):
            for c in owners(s,sent,t):
                st=stat[c]; st["secs"][s]+=1
                if CUE.search(sent) and s not in LISTS: st["evid"].append((s,sent))
        # speech tags
        for c,(nm,al) in R.items():
            for a in [re.sub(r" \(.*\)","",nm)]+al:
                if len(a)<3: continue
                for m in re.finditer(r"(?:^|[\"'‘“]\s*|\.\s+)(?:And |Then |Thereupon |Hearing this, )?(?:the |The )?"+re.escape(a.replace("the ",""))+r"(?: then| again| thereupon| also)? "+SAY+r"[,:\.]",flat):
                    stat[c]["speak"][s]+=1
    # resolve shared speech tags
    for s in list(stat["krishna"]["speak"]): pass
    out={}
    for c,st in stat.items():
        narr=sorted(x for x in st["secs"] if x not in LISTS)
        out[c]={"name":R[c][0],"sections":sorted(st["secs"]),"narrative_sections":narr,"mentions":sum(st["secs"].values()),
                "speech_tags":sum(st["speak"].values()),"speech_by_section":dict(sorted(st["speak"].items())),"n_evid":len(st["evid"])}
        ev=st["evid"]; 
        # spread evidence across sections: first per section then fill
        seen=set();pick=[]
        for s,x in ev:
            if s not in seen: pick.append((s,x));seen.add(s)
        for s,x in ev:
            if len(pick)>=10:break
            if (s,x) not in pick: pick.append((s,x))
        out[c]["evidence"]=[f"§{s}: {x[:300]}" for s,x in sorted(pick[:12])]
    json.dump(out,open('work/evidence.json','w'),indent=1)
    for c,o in sorted(out.items(),key=lambda kv:-len(kv[1]['narrative_sections'])):
        print(f"{c:22s} narr={len(o['narrative_sections']):3d} all={len(o['sections']):3d} m={o['mentions']:4d} spk={o['speech_tags']:3d} {o['speech_by_section'] if o['speech_tags']<12 else ''}")
