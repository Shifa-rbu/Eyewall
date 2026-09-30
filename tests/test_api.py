from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from server import main, review


def test_health_exposure_sse_and_review(monkeypatch):
    db_path = Path(".test-runtime") / f"api-{uuid4()}.sqlite3"
    monkeypatch.setattr(review, "DB_PATH", db_path)
    client = TestClient(main.app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["gemini"]["configured"] is False
    assert health.json()["gee"]["configured"] is False
    assert client.get("/api/exposure?surge=9").status_code == 422
    exposure = {"areaKm2": 1, "medical": 0, "shelter": 0, "power": 0}
    response = client.post("/api/advisory/draft", json={"surge": 1, "lang": "en", "exposure": exposure})
    assert response.status_code == 200
    assert "reviewRequired" in response.text
    assert client.get("/api/review/queue").json()["pending"]
    db_path.unlink(missing_ok=True)


def test_static_security_headers_and_no_browser_key():
    client = TestClient(main.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    html = response.text
    assert "onclick=" not in html
    assert "gemkey" not in html
    script = client.get("/app.js").text
    assert "generativelanguage.googleapis.com" not in script
    assert "GEMINI_API_KEY" not in script


def test_draft_rate_limit(monkeypatch):
    db_path = Path(".test-runtime") / f"rate-{uuid4()}.sqlite3"
    monkeypatch.setattr(review, "DB_PATH", db_path)
    main._rate.clear()
    client = TestClient(main.app)
    body = {"surge": 1, "lang": "en", "exposure": {"areaKm2": 0}}
    responses = [client.post("/api/advisory/draft", json=body) for _ in range(11)]
    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[-1].status_code == 429
    assert responses[-1].headers["Retry-After"] == "60"
    db_path.unlink(missing_ok=True)
