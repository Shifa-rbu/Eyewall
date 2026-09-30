"""Local-only draft review storage and tamper-evident audit chain."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .config import DB_PATH

ZERO_HASH = "0" * 64


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
      PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS draft (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, surge REAL NOT NULL, lang TEXT NOT NULL, mode TEXT NOT NULL, model TEXT, exposure_json TEXT NOT NULL, text TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS decision (id INTEGER PRIMARY KEY AUTOINCREMENT, draft_id TEXT NOT NULL REFERENCES draft(id), decided_at TEXT NOT NULL, decision TEXT NOT NULL, reviewer TEXT NOT NULL, edited_text TEXT, note TEXT);
      CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL, payload_json TEXT NOT NULL);
    """)
    return db


@contextmanager
def database():
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def add_audit(db, payload):
    row = db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev = row["hash"] if row else ZERO_HASH
    body = canonical(payload)
    digest = hashlib.sha256((prev + body).encode()).hexdigest()
    ts = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO audit(ts,prev_hash,hash,payload_json) VALUES(?,?,?,?)", (ts, prev, digest, body))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0], digest


def create_draft(surge, lang, exposure, text, mode="template", model=None):
    draft_id = str(uuid4())
    with database() as db:
        db.execute("INSERT INTO draft VALUES(?,?,?,?,?,?,?,?)", (draft_id, datetime.now(timezone.utc).isoformat(), surge, lang, mode, model, canonical(exposure), text))
        add_audit(db, {"type": "draft", "draftId": draft_id, "mode": mode})
    return draft_id


def decide(draft_id, decision, reviewer, edited_text=None, note=None):
    with database() as db:
        if not db.execute("SELECT 1 FROM draft WHERE id=?", (draft_id,)).fetchone():
            return None
        ts = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO decision(draft_id,decided_at,decision,reviewer,edited_text,note) VALUES(?,?,?,?,?,?)", (draft_id, ts, decision, reviewer, edited_text, note))
        seq, digest = add_audit(db, {"type":"decision", "draftId":draft_id, "decision":decision, "reviewer":reviewer, "editedText":edited_text, "note":note})
        return {"status":"recorded", "auditSeq":seq, "hash":digest}


def queue():
    with database() as db:
        pending = db.execute("SELECT d.* FROM draft d LEFT JOIN decision x ON x.draft_id=d.id WHERE x.id IS NULL ORDER BY d.created_at").fetchall()
        decided = db.execute("SELECT d.*, x.decision, x.reviewer, x.decided_at FROM draft d JOIN decision x ON x.draft_id=d.id ORDER BY x.id DESC").fetchall()
        def item(row):
            out = dict(row)
            if "exposure_json" in out: out["exposure"] = json.loads(out.pop("exposure_json"))
            return out
        return {"pending":[item(r) for r in pending], "decided":[item(r) for r in decided]}


def export_audit():
    with database() as db:
        return [{"seq":r["seq"], "ts":r["ts"], "prevHash":r["prev_hash"], "hash":r["hash"], "payload":json.loads(r["payload_json"])} for r in db.execute("SELECT * FROM audit ORDER BY seq")]


def verify_audit(entries=None):
    entries = export_audit() if entries is None else entries
    prev = ZERO_HASH
    for entry in entries:
        digest = hashlib.sha256((prev + canonical(entry["payload"])).encode()).hexdigest()
        if entry["prevHash"] != prev or entry["hash"] != digest:
            return {"valid":False,"brokenSeq":entry["seq"]}
        prev = digest
    return {"valid":True,"entries":len(entries)}
