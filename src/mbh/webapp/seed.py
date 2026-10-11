"""Seed the SQLite store from characters/book01.json and attach the approved voices.
Voices come from voices/registry.json (tracked; written by tools/export_voice_registry.py). The legacy
proto/voice_map.json path is used only when its prototype renders exist locally (they are gitignored).
usage: python -m mbh.webapp.seed [--replace]"""
import json, shutil, sys
from .db import Store, ROOT

def main():
    st = Store(); mode = "replace" if "--replace" in sys.argv else "merge"
    print("import:", st.import_data(json.loads((ROOT / "characters/book01.json").read_text()), mode))
    reg = ROOT / "voices" / "registry.json"
    registry = json.loads(reg.read_text())["voices"] if reg.exists() else {}
    for cid, v in registry.items():
        if not st.get_character(cid) or not (ROOT / v["ref"]).exists(): continue
        st.update_character(cid, {"voice_clip": v["ref"], "voice_engine": v.get("engine", ""), "voice_prompt": v.get("prompt", ""),
                                  "sample_line": v.get("sample_line", ""), "voice_notes": v.get("notes", "")})
        print("voice:", cid)
    proto = ROOT / "proto"
    designs = {v["id"]: v for f in ("voices.json", "voices2.json") if (proto / f).exists() for v in json.loads((proto / f).read_text())}
    vmap = json.loads((proto / "voice_map.json").read_text()) if (proto / "voice_map.json").exists() else {}
    for cid, src in vmap.items():
        if cid in registry or not st.get_character(cid) or not (proto / src).exists(): continue
        d = ROOT / "voices" / cid; (d / "candidates").mkdir(parents=True, exist_ok=True)
        shutil.copy(proto / src, d / "ref.wav")
        for cand in (proto / "out/design").glob(f"{cid}_*.wav"): shutil.copy(cand, d / "candidates" / cand.name)
        v = designs.get(cid, {})
        st.update_character(cid, {"voice_clip": f"voices/{cid}/ref.wav", "voice_engine": "voxcpm2 (proto, 10 steps)",
                                  "voice_prompt": v.get("prompt", ""), "sample_line": v.get("line", ""),
                                  "voice_notes": f"Selected from proto candidates ({src.split('/')[-1]}); approved by Aadesh 2026-10-10 (prototype feedback)."})
        print("voice:", cid)
    for c in st.list_characters():  # default sample line / prompt for the rest
        if not c["voice_prompt"]: st.update_character(c["id"], {"voice_prompt": c["voice_brief"]})
if __name__ == "__main__": main()
