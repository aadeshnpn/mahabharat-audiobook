import json,sys
E_=json.load(open('work/evidence.json'))
n=int(sys.argv[1]); L=int(sys.argv[2])
for c in sys.argv[3:]:
    o=E_[c]; print(f"## {c} narr{o['narrative_sections'][:30]}")
    for e in o['evidence'][:n]: print("  ",e[:L])
