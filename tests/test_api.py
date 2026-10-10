import os, json, io, pathlib, tempfile, importlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["MBH_DB"] = tempfile.mktemp(suffix=".sqlite3")
from fastapi.testclient import TestClient
from mbh.webapp import app as appmod
c = TestClient(appmod.app)

def test_seed_import_and_graph():
    r = c.post("/api/import/seed?mode=replace"); assert r.status_code == 200, r.text
    assert r.json()["characters"] >= 80
    g = c.get("/api/graph").json(); assert len(g["nodes"]) >= 80 and len(g["edges"]) >= 100
    ids = {n["data"]["id"] for n in g["nodes"]}
    assert all(e["data"]["source"] in ids and e["data"]["target"] in ids for e in g["edges"])

def test_character_crud():
    r = c.post("/api/characters", json={"name": "Test Rishi", "gender": "male", "aliases": ["TR"]}); assert r.status_code == 201
    cid = r.json()["id"]; assert cid == "test_rishi"
    assert c.post("/api/characters", json={"name": "Test Rishi"}).status_code == 409
    r = c.patch(f"/api/characters/{cid}", json={"respelling": "TEST-ri-shee", "sections": [3, 5]}); assert r.json()["sections"] == [3, 5]
    r = c.put(f"/api/characters/{cid}", json={"name": "Test Rishi II", "kind": "divine"}); assert r.json()["kind"] == "divine"
    assert c.get("/api/characters?q=rishi ii").json()[0]["id"] == cid
    assert c.delete(f"/api/characters/{cid}").status_code == 200
    assert c.get(f"/api/characters/{cid}").status_code == 404

def test_relationship_crud_and_cascade():
    c.post("/api/characters", json={"name": "A One"}); c.post("/api/characters", json={"name": "B Two"})
    assert c.post("/api/relationships", json={"source": "a_one", "target": "b_two", "type": "bogus"}).status_code == 422
    assert c.post("/api/relationships", json={"source": "a_one", "target": "nobody", "type": "ally_of"}).status_code == 404
    r = c.post("/api/relationships", json={"source": "a_one", "target": "b_two", "type": "teacher_of"}); assert r.status_code == 201
    rid = r.json()["id"]
    assert c.post("/api/relationships", json={"source": "a_one", "target": "b_two", "type": "teacher_of"}).status_code == 409
    r = c.put(f"/api/relationships/{rid}", json={"source": "a_one", "target": "b_two", "type": "enemy_of", "notes": "x"}); assert r.json()["type"] == "enemy_of"
    assert any(x["id"] == rid for x in c.get("/api/characters/a_one").json()["relationships"])
    c.delete("/api/characters/b_two")  # cascade
    assert all(x["id"] != rid for x in c.get("/api/relationships").json())
    c.delete("/api/characters/a_one")

def test_voice_upload_replace_detach():
    c.post("/api/characters", json={"name": "Voice Test"})
    wav = (ROOT / "voices/bhishma/ref.wav").read_bytes()
    r = c.post("/api/characters/voice_test/voice", files={"file": ("x.wav", wav, "audio/wav")}); assert r.status_code == 200
    assert r.json()["voice_clip"] == "voices/voice_test/ref.wav"
    assert c.get("/voices/voice_test/ref.wav").status_code == 200
    r = c.post("/api/characters/voice_test/voice", files={"file": ("y.wav", wav, "audio/wav")}); assert r.status_code == 200  # replace keeps history
    assert list((ROOT / "voices/voice_test").glob("ref_replaced_*"))
    assert c.post("/api/characters/voice_test/voice", files={"file": ("y.txt", b"hi", "text/plain")}).status_code == 422
    assert c.delete("/api/characters/voice_test/voice").json()["voice_clip"] == ""
    c.delete("/api/characters/voice_test?delete_voice_files=true"); assert not (ROOT / "voices/voice_test").exists()

def test_export_roundtrip():
    data = c.get("/api/export").json(); n, m = len(data["characters"]), len(data["relationships"])
    r = c.post("/api/import?mode=replace", json=data).json(); assert r == {"characters": n, "relationships": m}
    again = c.get("/api/export").json(); assert len(again["characters"]) == n and len(again["relationships"]) == m

def test_extracted_fields_and_new_rel_types():
    assert c.post("/api/import/seed?mode=replace").status_code == 200
    h = c.get("/api/characters/hidimbi").json()
    assert h["provenance"] == "text-extracted" and "Hidimva" in h["name"] and h["speaking_lines"] > 0
    assert isinstance(h["speech_by_section"], dict) and h["narrative_sections"]
    types = {r["type"] for r in c.get("/api/relationships").json()}
    assert {"incarnation_of", "rival_of", "guardian_of", "slew"} <= types
    assert all(r["section"] for r in c.get("/api/relationships").json())
    g = c.get("/api/graph").json(); assert len(g["nodes"]) >= 150 and all(e["data"]["label"] and "§" not in e["data"]["label"] for e in g["edges"])
    # PATCH keeps the extraction-only fields
    p = c.patch("/api/characters/hidimbi", json={"role": "edited", "provenance": "text-extracted+hand-edited"}).json()
    assert p["flags"] == h["flags"] and p["speech_by_section"] == h["speech_by_section"] and p["provenance"].endswith("hand-edited")

def test_reseed_preserves_voice_and_ui_edits(tmp_path):
    import json as _j
    from mbh.webapp import reseed
    from mbh.webapp.db import ROOT
    c.post("/api/import/seed?mode=replace")
    c.patch("/api/characters/bhishma", json={"voice_clip": "voices/bhishma/ref.wav", "voice_prompt": "custom prompt", "role": "UI-edited role"})
    c.post("/api/characters", json={"name": "UI Only Person"})
    prev = _j.loads((ROOT / "characters/book01.json").read_text()); f = tmp_path / "prev.json"; f.write_text(_j.dumps(prev))
    rep = reseed.main(str(f))
    b = c.get("/api/characters/bhishma").json()
    assert b["voice_clip"] == "voices/bhishma/ref.wav" and b["voice_prompt"] == "custom prompt"
    assert b["role"] == "UI-edited role" and b["provenance"] == "text-extracted+hand-edited" and "bhishma" in rep["ui_edits_kept"]
    assert c.get("/api/characters/ui_only_person").status_code == 200
    import pathlib; pathlib.Path(rep["export"]).unlink()

def test_user_decisions_2026_10_10():
    c.post("/api/import/seed?mode=replace")
    b, ch = c.get("/api/characters/balarama").json(), c.get("/api/characters/chitraratha").json()
    assert b["name"] == "Balarama" and "Valadeva" in b["aliases"]
    assert ch["name"] == "Chitraratha" and "Angaraparna" in ch["aliases"]
    d = c.get("/api/characters/draupadi").json(); assert "Krishnaa" in d["aliases"] and d["speaking_lines"] > 0
    for gid in ("satasringa_rishis", "valakhilyas"):
        assert c.get(f"/api/characters/{gid}").json()["voice_group"] == "naimisha_rishis"
    from mbh.text.krishna import resolve, speakable
    from mbh.characters.build_extracted import T
    assert "was born Draupadi (Draupadi)" in speakable(63, T[63])            # 'born Krishna (Draupadi)'
    assert [w for *_, w, _r in resolve(209, T[209])][2:4] == ["krishna", "draupadi"]  # 'Krishna and Vidura, taking with them Krishna, the daughter of Drupada'
    assert all(w == "krishna" for *_, w, _r in resolve(229, T[229]))       # Khandava battle
