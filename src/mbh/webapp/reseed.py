"""Re-seed the DB from characters/book01.json while keeping everything the user did in the UI.
usage: python -m mbh.webapp.reseed [baseline.json]   (DB is exported to characters/backups/ first;
       baseline defaults to characters/backups/last_seed.json, written on every re-seed)
Preserved across the re-seed:
  * voice fields (voice_clip, voice_prompt, sample_line, voice_engine, voice_notes) for every id that still exists;
  * any character whose DB copy differs from the previous seed file (a UI edit) -> the edited fields win and
    provenance becomes 'text-extracted+hand-edited';
  * characters and relationships created in the UI (absent from the previous seed) are re-added.
"""
import json, os, sys, time, pathlib
from .db import Store, ROOT

VOICE = ("voice_clip", "voice_prompt", "sample_line", "voice_engine", "voice_notes")
EDITABLE = ("name", "aliases", "respelling", "gender", "era_age", "role", "kind", "personality", "emotional_range",
            "voice_brief", "backstory", "key_sections")

def main(prev_seed=None):
    st = Store(os.environ.get("MBH_DB")); bk = ROOT / "characters/backups"; bk.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    exp = st.export_data(); (bk / f"db_export.before_reseed.{stamp}.json").write_text(json.dumps(exp, indent=1, ensure_ascii=False))
    last = bk / "last_seed.json"   # exact file the DB was last seeded from = baseline for detecting UI edits
    prev_path = pathlib.Path(prev_seed) if prev_seed else (last if last.exists() else None)
    prev = json.loads(prev_path.read_text()) if prev_path else {"characters": [], "relationships": []}
    P = {c["id"]: c for c in prev["characters"]}; prev_rels = {(r["source"], r["target"], r["type"]) for r in prev["relationships"]}
    new = json.loads((ROOT / "characters/book01.json").read_text()); N = {c["id"] for c in new["characters"]}
    report = {"export": str(bk / f"db_export.before_reseed.{stamp}.json"), "voices_kept": [], "ui_edits_kept": {}, "ui_chars_readded": [],
              "ui_rels_readded": [], "dropped_ids": sorted({c["id"] for c in exp["characters"]} - N)}
    report["import"] = st.import_data(new, "replace")
    if not os.environ.get("MBH_DB"): last.write_text(json.dumps(new, ensure_ascii=False))
    for c in exp["characters"]:
        cid = c["id"]
        if cid not in N:
            if cid not in P:  # created in the UI, never in a seed file
                st.upsert_character(c); report["ui_chars_readded"].append(cid)
            continue
        patch = {f: c[f] for f in VOICE if c.get(f)}
        if patch.get("voice_clip"): report["voices_kept"].append(cid)
        if patch.get("voice_prompt") == c.get("voice_brief"): patch.pop("voice_prompt")   # was only the default copy of the brief
        if cid in P:
            edits = {f: c[f] for f in EDITABLE if f in P[cid] and c.get(f) != P[cid][f]}
            if edits: patch.update(edits, provenance="text-extracted+hand-edited"); report["ui_edits_kept"][cid] = sorted(edits)
        if patch: st.update_character(cid, patch)
    for c in st.list_characters():
        if not c["voice_prompt"]: st.update_character(c["id"], {"voice_prompt": c["voice_brief"]})
    have = {(r["source"], r["target"], r["type"]) for r in st.list_relationships()}
    for r in exp["relationships"]:
        k = (r["source"], r["target"], r["type"])
        if k not in prev_rels and k not in have and r["source"] in N and r["target"] in N:
            st.add_relationship(r); report["ui_rels_readded"].append(k)
    return report

if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1] if len(sys.argv) > 1 else None), indent=1, default=list))
