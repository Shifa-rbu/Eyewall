import socket
from pathlib import Path
from uuid import uuid4

from server import review


def test_hash_chain_detects_tampering(monkeypatch):
    db_path = Path(".test-runtime") / f"review-{uuid4()}.sqlite3"
    monkeypatch.setattr(review, "DB_PATH", db_path)
    draft = review.create_draft(3.0, "en", {"areaKm2": 1}, "review text")
    result = review.decide(draft, "approve", "reviewer")
    assert result["auditSeq"] == 2
    entries = review.export_audit()
    assert review.verify_audit(entries)["valid"]
    entries[0]["payload"]["mode"] = "tampered"
    assert review.verify_audit(entries) == {"valid": False, "brokenSeq": 1}
    db_path.unlink(missing_ok=True)


def test_review_flow_has_no_network(monkeypatch):
    db_path = Path(".test-runtime") / f"review-{uuid4()}.sqlite3"
    monkeypatch.setattr(review, "DB_PATH", db_path)
    def blocked(*args, **kwargs):
        raise AssertionError("review workflow attempted network I/O")
    monkeypatch.setattr(socket, "socket", blocked)
    draft = review.create_draft(2.0, "en", {}, "draft")
    assert review.decide(draft, "reject", "reviewer")["status"] == "recorded"
    draft = review.create_draft(2.5, "en", {}, "draft")
    assert review.decide(draft, "edit", "reviewer", "edited")["status"] == "recorded"
    db_path.unlink(missing_ok=True)
