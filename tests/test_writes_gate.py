from fastapi.testclient import TestClient

from server.main import app


def test_write_endpoints_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EYEWALL_ALLOW_WRITES", raising=False)
    client = TestClient(app)

    # Decision endpoint returns 403
    decision_resp = client.post(
        "/api/review/draft-123/decision",
        json={"decision": "approve", "reviewer": "test_user"},
    )
    assert decision_resp.status_code == 403
    assert "disabled" in decision_resp.json()["detail"].lower()

    # SAR refresh endpoint returns 403
    sar_resp = client.post("/api/sar/refresh")
    assert sar_resp.status_code == 403
    assert "disabled" in sar_resp.json()["detail"].lower()


def test_write_endpoints_enabled(monkeypatch):
    monkeypatch.setenv("EYEWALL_ALLOW_WRITES", "true")
    client = TestClient(app)

    # Decision endpoint proceeds (returns 404 since draft-123 doesn't exist)
    decision_resp = client.post(
        "/api/review/draft-123/decision",
        json={"decision": "approve", "reviewer": "test_user"},
    )
    assert decision_resp.status_code == 404

    # SAR refresh endpoint proceeds to existing 409 logic
    sar_resp = client.post("/api/sar/refresh")
    assert sar_resp.status_code == 409
    assert "Earth Engine" in sar_resp.json()["detail"]
