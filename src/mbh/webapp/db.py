"""SQLite-backed store for characters, relationships and voice-generation jobs."""
import json, sqlite3, time, pathlib, threading

ROOT = pathlib.Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "mbh.sqlite3"

JSON_FIELDS = ["aliases", "personality", "emotional_range", "key_sections", "sections", "narrative_sections", "flags"]
DICT_FIELDS = ["speech_by_section"]
CHAR_FIELDS = ["id", "name", "aliases", "respelling", "gender", "era_age", "role", "kind", "personality",
               "emotional_range", "voice_brief", "backstory", "key_sections", "first_section", "sections",
               "mentions", "speaking_lines", "count_notes", "provisional", "source", "sample_line",
               "voice_prompt", "voice_clip", "voice_engine", "voice_notes", "updated_at",
               "narrative_sections", "speech_by_section", "flags", "provenance", "kind_detail", "voice_group"]
REL_TYPES = {  # type: (directed, colour, label)
    "parent_of": (True, "#2b8a3e", "parent of"), "foster_parent_of": (True, "#69db7c", "foster parent of"),
    "spouse_of": (False, "#d6336c", "spouse of"), "sibling_of": (False, "#f59f00", "sibling of"),
    "teacher_of": (True, "#1c7ed6", "teacher of"), "ally_of": (False, "#15aabf", "ally of"),
    "enemy_of": (False, "#e03131", "enemy of"), "cursed": (True, "#7048e8", "cursed"),
    "serves": (True, "#868e96", "serves"), "narrates_to": (True, "#495057", "narrates to"),
    "incarnation_of": (True, "#ae3ec9", "incarnation of"), "rival_of": (False, "#fd7e14", "rival of"),
    "guardian_of": (True, "#0ca678", "guardian of"), "slew": (True, "#862e9c", "slew"),
}
MIGRATIONS = [("characters", "narrative_sections", "TEXT DEFAULT '[]'"), ("characters", "speech_by_section", "TEXT DEFAULT '{}'"),
              ("characters", "flags", "TEXT DEFAULT '[]'"), ("characters", "provenance", "TEXT DEFAULT 'hand'"),
              ("characters", "kind_detail", "TEXT DEFAULT ''"), ("characters", "voice_group", "TEXT DEFAULT ''"), ("relationships", "section", "INTEGER"), ("relationships", "provenance", "TEXT DEFAULT 'hand'"),
              ("jobs", "progress", "REAL DEFAULT 0"), ("jobs", "message", "TEXT DEFAULT ''"),
              ("jobs", "cancel", "INTEGER DEFAULT 0"), ("jobs", "episode_id", "TEXT")]
SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, aliases TEXT DEFAULT '[]', respelling TEXT DEFAULT '', gender TEXT DEFAULT '',
  era_age TEXT DEFAULT '', role TEXT DEFAULT '', kind TEXT DEFAULT 'human', personality TEXT DEFAULT '[]',
  emotional_range TEXT DEFAULT '[]', voice_brief TEXT DEFAULT '', backstory TEXT DEFAULT '', key_sections TEXT DEFAULT '[]',
  first_section INTEGER, sections TEXT DEFAULT '[]', mentions INTEGER DEFAULT 0, speaking_lines INTEGER DEFAULT 0,
  count_notes TEXT DEFAULT '', provisional INTEGER DEFAULT 1, source TEXT DEFAULT '', sample_line TEXT DEFAULT '',
  voice_prompt TEXT DEFAULT '', voice_clip TEXT DEFAULT '', voice_engine TEXT DEFAULT '', voice_notes TEXT DEFAULT '',
  updated_at REAL);
CREATE TABLE IF NOT EXISTS relationships (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  target TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE, type TEXT NOT NULL, label TEXT DEFAULT '',
  notes TEXT DEFAULT '', provisional INTEGER DEFAULT 1, UNIQUE(source, target, type));
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, character_id TEXT, kind TEXT, status TEXT, params TEXT, output TEXT,
  log TEXT DEFAULT '', created REAL, started REAL, finished REAL,
  progress REAL DEFAULT 0, message TEXT DEFAULT '', cancel INTEGER DEFAULT 0, episode_id TEXT);
"""
_lock = threading.RLock()

def connect(path=None):
    path = pathlib.Path(path or DB_PATH); path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False, timeout=30); con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON"); con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA busy_timeout=5000")
    con.executescript(SCHEMA)
    for table, col, decl in MIGRATIONS:
        if col not in {r[1] for r in con.execute(f"PRAGMA table_info({table})")}:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    con.commit(); return con

def _row_to_char(r):
    d = dict(r)
    for f in JSON_FIELDS: d[f] = json.loads(d.get(f) or "[]")
    for f in DICT_FIELDS: d[f] = json.loads(d.get(f) or "{}")
    d["provisional"] = bool(d["provisional"]); return d

def _char_params(d):
    out = {}
    for f in CHAR_FIELDS:
        if f in d:
            v = d[f]
            if f in JSON_FIELDS: v = json.dumps(v or [], ensure_ascii=False)
            if f in DICT_FIELDS: v = json.dumps(v or {}, ensure_ascii=False)
            if f == "provisional": v = int(bool(v))
            out[f] = v
    out["updated_at"] = time.time(); return out

def _job_row(r):
    d = dict(r)
    d["params"] = json.loads(d.get("params") or "{}")
    d["progress"] = float(d.get("progress") or 0)
    d["cancel"] = int(d.get("cancel") or 0)
    d["message"] = d.get("message") or ""
    return d

class Store:
    def __init__(self, path=None): self.con = connect(path)

    def _all(self, sql, args=()):
        with _lock:
            return self.con.execute(sql, args).fetchall()

    def _one(self, sql, args=()):
        with _lock:
            return self.con.execute(sql, args).fetchone()

    # characters
    def list_characters(self):
        return [_row_to_char(r) for r in self._all("SELECT * FROM characters ORDER BY name COLLATE NOCASE")]
    def get_character(self, cid):
        r = self._one("SELECT * FROM characters WHERE id=?", (cid,)); return _row_to_char(r) if r else None
    def upsert_character(self, d):
        p = _char_params(d)
        with _lock, self.con:
            cols = ",".join(p); q = ",".join("?" * len(p)); upd = ",".join(f"{k}=excluded.{k}" for k in p if k != "id")
            self.con.execute(f"INSERT INTO characters ({cols}) VALUES ({q}) ON CONFLICT(id) DO UPDATE SET {upd}", list(p.values()))
        return self.get_character(d["id"])
    def update_character(self, cid, patch):
        patch = {k: v for k, v in patch.items() if k in CHAR_FIELDS and k != "id"}
        p = _char_params(patch)
        with _lock, self.con:
            self.con.execute(f"UPDATE characters SET {','.join(f'{k}=?' for k in p)} WHERE id=?", [*p.values(), cid])
        return self.get_character(cid)
    def delete_character(self, cid):
        with _lock, self.con: n = self.con.execute("DELETE FROM characters WHERE id=?", (cid,)).rowcount
        return n > 0

    # relationships
    def list_relationships(self, cid=None):
        if cid:
            rows = self._all("SELECT * FROM relationships WHERE source=? OR target=? ORDER BY type", (cid, cid))
        else:
            rows = self._all("SELECT * FROM relationships ORDER BY id")
        return [dict(r, provisional=bool(r["provisional"])) for r in rows]
    def get_relationship(self, rid):
        r = self._one("SELECT * FROM relationships WHERE id=?", (rid,)); return dict(r, provisional=bool(r["provisional"])) if r else None
    def add_relationship(self, d):
        with _lock, self.con:
            cur = self.con.execute("INSERT INTO relationships (source,target,type,label,notes,provisional,section,provenance) VALUES (?,?,?,?,?,?,?,?)",
                                   (d["source"], d["target"], d["type"], d.get("label", ""), d.get("notes", ""), int(d.get("provisional", False)),
                                    d.get("section"), d.get("provenance") or "hand"))
        return self.get_relationship(cur.lastrowid)
    def update_relationship(self, rid, patch):
        allowed = {k: (int(v) if k == "provisional" else v) for k, v in patch.items() if k in ("source", "target", "type", "label", "notes", "provisional", "section", "provenance")}
        if allowed:
            with _lock, self.con:
                self.con.execute(f"UPDATE relationships SET {','.join(f'{k}=?' for k in allowed)} WHERE id=?", [*allowed.values(), rid])
        return self.get_relationship(rid)
    def delete_relationship(self, rid):
        with _lock, self.con: n = self.con.execute("DELETE FROM relationships WHERE id=?", (rid,)).rowcount
        return n > 0

    # jobs
    def add_job(self, cid, kind, params, episode_id=None):
        with _lock, self.con:
            cur = self.con.execute(
                "INSERT INTO jobs (character_id,kind,status,params,created,episode_id,progress,message,cancel) VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, kind, "queued", json.dumps(params), time.time(), episode_id, 0, "", 0))
        return self.get_job(cur.lastrowid)
    def update_job(self, jid, **kw):
        with _lock, self.con: self.con.execute(f"UPDATE jobs SET {','.join(f'{k}=?' for k in kw)} WHERE id=?", [*kw.values(), jid])
    def append_log(self, jid, text, progress=None, message=None):
        with _lock, self.con:
            row = self.con.execute("SELECT log FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row:
                return
            log = ((row["log"] or "") + text)[-20000:]
            sets, vals = ["log=?"], [log]
            if progress is not None:
                sets.append("progress=?"); vals.append(float(progress))
            if message is not None:
                sets.append("message=?"); vals.append(message)
            vals.append(jid)
            self.con.execute(f"UPDATE jobs SET {','.join(sets)} WHERE id=?", vals)
    def get_job(self, jid):
        r = self._one("SELECT * FROM jobs WHERE id=?", (jid,))
        return _job_row(r) if r else None
    def list_jobs(self, cid=None, *, episode_id=None, kind=None, limit=100):
        clauses, args = [], []
        if cid:
            clauses.append("character_id=?"); args.append(cid)
        if episode_id:
            clauses.append("episode_id=?"); args.append(episode_id)
        if kind:
            clauses.append("kind=?"); args.append(kind)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(max(1, min(int(limit), 500)))
        q = f"SELECT * FROM jobs{where} ORDER BY id DESC LIMIT ?"
        return [_job_row(r) for r in self._all(q, args)]
    def claim_next_job(self):
        """Mark the oldest queued job running. Queued jobs that were cancelled never start."""
        now = time.time()
        with _lock, self.con:
            self.con.execute(
                "UPDATE jobs SET status='cancelled', finished=?, message='cancelled before start' WHERE status='queued' AND cancel=1",
                (now,))
            row = self.con.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
            if not row:
                return None
            self.con.execute("UPDATE jobs SET status='running', started=?, progress=0 WHERE id=?", (now, row["id"]))
            jid = row["id"]
        return self.get_job(jid)
    def recover_jobs(self):
        """Requeue jobs left 'running' by a dead process. Render/synth resume from the per-line cache."""
        with _lock, self.con:
            cur = self.con.execute(
                "UPDATE jobs SET status='queued', message='requeued after restart' WHERE status='running'")
            return cur.rowcount
    def request_cancel(self, jid):
        now = time.time()
        with _lock, self.con:
            row = self.con.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row or row["status"] not in ("queued", "running"):
                return False
            if row["status"] == "queued":
                self.con.execute(
                    "UPDATE jobs SET cancel=1, status='cancelled', finished=?, message='cancelled before start' WHERE id=?",
                    (now, jid))
            else:
                self.con.execute("UPDATE jobs SET cancel=1, message='cancel requested' WHERE id=?", (jid,))
            return True

    # import / export
    def import_data(self, data, mode="merge"):
        with _lock, self.con:
            if mode == "replace":
                self.con.execute("DELETE FROM relationships"); self.con.execute("DELETE FROM characters")
        nc = nr = 0
        for c in data.get("characters", []):
            self.upsert_character(c); nc += 1
        for r in data.get("relationships", []):
            try:
                with _lock, self.con:
                    self.con.execute("INSERT OR IGNORE INTO relationships (source,target,type,label,notes,provisional,section,provenance) VALUES (?,?,?,?,?,?,?,?)",
                                     (r["source"], r["target"], r["type"], r.get("label", ""), r.get("notes", ""), int(r.get("provisional", True)),
                                      r.get("section"), r.get("provenance", "hand")))
                nr += 1
            except Exception:
                pass
        return {"characters": nc, "relationships": nr}
    def export_data(self):
        return {"book": 1, "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "characters": self.list_characters(),
                "relationships": [{k: r[k] for k in ("source", "target", "type", "label", "notes", "provisional", "section", "provenance")} for r in self.list_relationships()]}
