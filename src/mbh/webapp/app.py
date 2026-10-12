"""Mahabharata audiobook: character map and Episode Studio (REST + static UI).

Run (localhost only, no authentication):
  PYTHONPATH=src python -m mbh.webapp
Set MBH_HOST=0.0.0.0 only when you have put something else in front of it.
"""
import json, os, pathlib, re, shutil, time
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Body, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from mbh.studio.runtime import mock_enabled
from mbh.webapp import jobs as jobq
from mbh.webapp.studio_routes import job_router, router as studio_router
from .db import Store, REL_TYPES, ROOT

STATIC = pathlib.Path(__file__).parent / "static"
VOICES = ROOT / "voices"; VOICES.mkdir(exist_ok=True)
SEED = ROOT / "characters" / "book01.json"
VOX_PY = os.environ.get("MBH_VOX_PYTHON", str(ROOT / "proto/.venv-vox/bin/python"))
store = Store(os.environ.get("MBH_DB"))
app = FastAPI(
    title="Mahabharata Audiobook",
    version="0.2",
    description=(
        "Character map and Episode Studio for the KMG audiobook. "
        "The studio API is the same surface the browser uses: JSON in, JSON out, job ids for anything that synthesizes audio. "
        "There is no authentication. Bind to 127.0.0.1 (the default of `python -m mbh.webapp`) unless a trusted proxy is in front. "
        "See docs/STUDIO.md for the create → build → review → render → assemble → QA flow."
    ),
)

class Character(BaseModel):
    id: Optional[str] = None
    name: str
    aliases: list[str] = []; respelling: str = ""; gender: str = ""; era_age: str = ""; role: str = ""; kind: str = "human"
    personality: list[str] = []; emotional_range: list[str] = []; voice_brief: str = ""; backstory: str = ""
    key_sections: list[int] = []; first_section: Optional[int] = None; sections: list[int] = []
    mentions: int = 0; speaking_lines: int = 0; count_notes: str = ""; provisional: bool = False; source: str = "manual"
    sample_line: str = ""; voice_prompt: str = ""; voice_clip: str = ""; voice_engine: str = ""; voice_notes: str = ""
    narrative_sections: list[int] = []; speech_by_section: dict[str, int] = {}; flags: list[str] = []; provenance: str = "hand"; kind_detail: str = ""; voice_group: str = ""

class Relationship(BaseModel):
    source: str; target: str; type: str; label: str = ""; notes: str = ""; provisional: bool = False
    section: Optional[int] = None; provenance: str = "hand"

def slug(s): return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or f"char_{int(time.time())}"
def need_char(cid):
    c = store.get_character(cid)
    if not c: raise HTTPException(404, f"character {cid!r} not found")
    return c
def check_rel(d):
    if d["type"] not in REL_TYPES: raise HTTPException(422, f"unknown relationship type {d['type']!r}; allowed: {list(REL_TYPES)}")
    need_char(d["source"]); need_char(d["target"])
    if d["source"] == d["target"]: raise HTTPException(422, "source and target must differ")

# ---------- meta ----------
@app.get("/api/meta")
def meta():
    return {"relationship_types": {k: {"directed": v[0], "color": v[1], "label": v[2]} for k, v in REL_TYPES.items()},
            "kinds": sorted({c["kind"] for c in store.list_characters()} | {"human", "sage", "deity", "celestial", "naga", "asura", "rakshasa", "bird", "animal", "chorus"}),
            "voice_generation": {"available": pathlib.Path(VOX_PY).exists(), "engine": "voxcpm2", "python": VOX_PY}}

# ---------- characters ----------
@app.get("/api/characters")
def list_characters(q: str = "", kind: str = ""):
    out = store.list_characters()
    if kind: out = [c for c in out if c["kind"] == kind]
    if q:
        ql = q.lower(); out = [c for c in out if ql in c["name"].lower() or any(ql in a.lower() for a in c["aliases"]) or ql in c["role"].lower()]
    return out

@app.get("/api/characters/{cid}")
def get_character(cid: str):
    c = need_char(cid); c["relationships"] = store.list_relationships(cid); return c

@app.post("/api/characters", status_code=201)
def create_character(ch: Character):
    d = ch.model_dump(); d["id"] = slug(d["id"] or d["name"])
    if store.get_character(d["id"]): raise HTTPException(409, f"character {d['id']!r} already exists")
    return store.upsert_character(d)

@app.put("/api/characters/{cid}")
def replace_character(cid: str, ch: Character):
    need_char(cid); d = ch.model_dump(); d["id"] = cid; return store.upsert_character(d)

@app.patch("/api/characters/{cid}")
def patch_character(cid: str, patch: dict = Body(...)):
    need_char(cid); return store.update_character(cid, patch)

@app.delete("/api/characters/{cid}")
def delete_character(cid: str, delete_voice_files: bool = False):
    need_char(cid); store.delete_character(cid)
    if delete_voice_files and (VOICES / cid).exists(): shutil.rmtree(VOICES / cid)
    return {"deleted": cid}

# ---------- relationships ----------
@app.get("/api/relationships")
def list_relationships(character: str = ""): return store.list_relationships(character or None)

@app.post("/api/relationships", status_code=201)
def create_relationship(r: Relationship):
    d = r.model_dump(); check_rel(d)
    try: return store.add_relationship(d)
    except Exception as e: raise HTTPException(409, f"could not add relationship: {e}")

@app.put("/api/relationships/{rid}")
def update_relationship(rid: int, r: Relationship):
    if not store.get_relationship(rid): raise HTTPException(404, "relationship not found")
    d = r.model_dump(); check_rel(d); return store.update_relationship(rid, d)

@app.delete("/api/relationships/{rid}")
def delete_relationship(rid: int):
    if not store.delete_relationship(rid): raise HTTPException(404, "relationship not found")
    return {"deleted": rid}

# ---------- graph ----------
@app.get("/api/graph")
def graph():
    nodes = [{"data": {"id": c["id"], "label": c["name"], "kind": c["kind"], "gender": c["gender"], "mentions": c["mentions"],
                       "has_voice": bool(c["voice_clip"]), "provisional": c["provisional"],
                       "provenance": c.get("provenance", "hand"), "flags": c.get("flags", []), "speaking_lines": c["speaking_lines"]}} for c in store.list_characters()]
    edges = [{"data": {"id": f"r{r['id']}", "rid": r["id"], "source": r["source"], "target": r["target"], "type": r["type"],
                       "label": r["label"] or REL_TYPES[r["type"]][2], "color": REL_TYPES[r["type"]][1], "directed": REL_TYPES[r["type"]][0]}}
             for r in store.list_relationships() if r["type"] in REL_TYPES]
    return {"nodes": nodes, "edges": edges}

# ---------- voice ----------
def _voice_dir(cid): d = VOICES / cid; d.mkdir(parents=True, exist_ok=True); return d

@app.post("/api/characters/{cid}/voice")
async def upload_voice(cid: str, file: UploadFile = File(...)):
    need_char(cid)
    ext = pathlib.Path(file.filename or "clip.wav").suffix.lower()
    if ext not in (".wav", ".mp3", ".flac", ".ogg", ".m4a"): raise HTTPException(422, "audio file required (.wav/.mp3/.flac/.ogg/.m4a)")
    d = _voice_dir(cid)
    for old in d.glob("ref.*"):
        old.rename(d / f"ref_replaced_{int(time.time())}{old.suffix}")  # keep history, never silently lose a clip
    dest = d / f"ref{ext}"; dest.write_bytes(await file.read())
    return store.update_character(cid, {"voice_clip": str(dest.relative_to(ROOT)), "voice_engine": "uploaded"})

@app.delete("/api/characters/{cid}/voice")
def remove_voice(cid: str):
    need_char(cid); return store.update_character(cid, {"voice_clip": ""})

@app.get("/api/characters/{cid}/voice/candidates")
def voice_candidates(cid: str):
    need_char(cid); d = VOICES / cid / "candidates"
    return sorted([str(p.relative_to(ROOT)) for p in d.glob("*.wav")], reverse=True) if d.exists() else []

@app.post("/api/characters/{cid}/voice/select")
def select_candidate(cid: str, body: dict = Body(...)):
    need_char(cid); p = (ROOT / body.get("file", "")).resolve()
    if not str(p).startswith(str((VOICES / cid).resolve())) or not p.exists(): raise HTTPException(422, "not a candidate of this character")
    d = _voice_dir(cid)
    for old in d.glob("ref.*"): old.rename(d / f"ref_replaced_{int(time.time())}{old.suffix}")
    dest = d / "ref.wav"; shutil.copy(p, dest)
    return store.update_character(cid, {"voice_clip": str(dest.relative_to(ROOT)), "voice_engine": "voxcpm2",
                                        "voice_prompt": body.get("prompt") or store.get_character(cid)["voice_prompt"]})

@app.post("/api/characters/{cid}/voice/generate", status_code=202)
def generate_voice(cid: str, body: dict = Body(default={})):
    c = need_char(cid)
    if not mock_enabled() and not pathlib.Path(VOX_PY).exists():
        raise HTTPException(503, f"VoxCPM2 python not found at {VOX_PY}; set MBH_VOX_PYTHON")
    prompt = body.get("prompt") or c["voice_prompt"] or c["voice_brief"]
    text = body.get("text") or c["sample_line"] or (c["backstory"].split(". ")[0] + ".")
    if not prompt: raise HTTPException(422, "no prompt/voice brief")
    out = str((_voice_dir(cid) / "candidates" / f"cand_{time.strftime('%Y%m%d_%H%M%S')}.wav").relative_to(ROOT))
    return jobq.enqueue(store, kind="design_voice", character_id=cid,
                        params={"prompt": prompt, "text": text, "out": out, "steps": int(body.get("steps", 10))})

@app.get("/api/jobs")
def list_jobs(character: str = "", episode: str = "", kind: str = "", limit: int = 100):
    return store.list_jobs(character or None, episode_id=episode or None, kind=kind or None, limit=limit)
@app.get("/api/jobs/{jid}")
def get_job(jid: int):
    j = store.get_job(jid)
    if not j: raise HTTPException(404, "job not found")
    return j

# ---------- import / export ----------
@app.post("/api/import")
def import_data(data: dict = Body(...), mode: str = Query("merge", pattern="^(merge|replace)$")):
    return store.import_data(data, mode)

@app.post("/api/import/seed")
def import_seed(mode: str = Query("merge", pattern="^(merge|replace)$")):
    if not SEED.exists(): raise HTTPException(404, f"{SEED} missing; run python -m mbh.characters.build_extracted --write")
    return store.import_data(json.loads(SEED.read_text()), mode)

@app.get("/api/export")
def export_data(save: bool = False):
    data = store.export_data()
    if save:
        p = ROOT / "characters" / f"book01.export.{time.strftime('%Y%m%d_%H%M%S')}.json"; p.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        data["saved_to"] = str(p.relative_to(ROOT))
    return JSONResponse(data, headers={"Content-Disposition": "attachment; filename=characters.export.json"} if not save else {})

# ---------- studio ----------
app.include_router(studio_router)
app.include_router(job_router)

@app.on_event("startup")
def _start_jobs():
    host = os.environ.get("MBH_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print(f"WARNING: MBH_HOST={host}. Episode Studio has no authentication.", flush=True)
    jobq.start(store)

jobq.start(store)

# ---------- static ----------
app.mount("/voices", StaticFiles(directory=VOICES), name="voices")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
@app.get("/")
def index(): return FileResponse(STATIC / "index.html")
@app.get("/studio")
def studio_page(): return FileResponse(STATIC / "studio.html")
