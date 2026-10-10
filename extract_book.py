"""Extract clean text from mahabharata-online HTML: one .txt per section + index.json"""
import re, html, json, sys, pathlib
book = int(sys.argv[1]) if len(sys.argv)>1 else 1
raw = pathlib.Path(f"data/raw/book{book:02d}"); out = pathlib.Path(f"data/text/book{book:02d}"); out.mkdir(parents=True, exist_ok=True)
idx=[]; cur=None
for f in sorted(raw.glob("*.html"), key=lambda p:int(p.stem)):
    s=f.read_text(encoding="utf-8"); i=s.find('id="to_index">'); body=s[i+len('id="to_index">'):]
    body=body[:body.find('</div>')]
    body=body.replace('<br><br>','\n\n').replace('<br>',' ')
    t=html.unescape(re.sub(r'<[^>]+>','',body))
    paras=[re.sub(r'\s+',' ',p).strip() for p in t.split('\n\n')]; paras=[p for p in paras if p]
    m=re.match(r'\(([^)]*?Parva)\s*(,?\s*continued)?\s*\)', paras[0]) if paras else None
    if m: cur=m.group(1).strip(); paras=paras[1:]
    elif int(f.stem)<=2: cur={1:"Anukramanika Parva",2:"Parva-sangraha Parva"}[int(f.stem)]
    text="\n\n".join(paras); (out/f"{int(f.stem):03d}.txt").write_text(text, encoding="utf-8")
    idx.append(dict(book=book, section=int(f.stem), sub_parva=cur, words=len(text.split()), paragraphs=len(paras),
                    source_url=f"https://mahabharata-online.github.io/{book}/{f.stem}.html", file=f"{int(f.stem):03d}.txt"))
json.dump(idx, open(out/"index.json","w"), indent=1)
print(len(idx), sum(x['words'] for x in idx))
