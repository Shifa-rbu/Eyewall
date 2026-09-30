import json

from fastapi.testclient import TestClient

from server import gemini, main


def test_ai_panel_contract_case2_no_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    gemini.discover(force=True)

    client = TestClient(main.app)
    health_resp = client.get("/api/health").json()
    assert health_resp["gemini"]["configured"] is False
    assert "no GEMINI_API_KEY" in health_resp["gemini"]["error"]

    quota_resp = client.get("/api/quota").json()
    assert quota_resp["configured"] is False

    risk_resp = client.post("/api/risk/read", json={"surge": 3.0, "exposure": {}}).json()
    assert risk_resp["ok"] is False
    assert "Gemini is not configured" in risk_resp["note"]

    draft_resp = client.post(
        "/api/advisory/draft",
        json={"surge": 3.0, "lang": "en", "exposure": {}},
    )
    assert draft_resp.status_code == 200
    assert "mode" in draft_resp.text
    assert '"mode": "template"' in draft_resp.text


def test_ai_panel_contract_case3_quota_exhausted(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key_for_test")

    # Mock discover to return a valid model state
    mock_state = gemini.ModelState(selected="gemini-3.7-flash", available=["gemini-3.7-flash"])
    monkeypatch.setattr(gemini, "discover", lambda force=False: mock_state)

    # Set quota ledger remaining to 0
    ledger_path = tmp_path / "quota.json"
    ledger_path.write_text(json.dumps({"date": gemini.ledger()._today(), "used": 15}))
    test_ledger = gemini.QuotaLedger(ledger_path, budget=15)
    monkeypatch.setattr(gemini, "ledger", lambda: test_ledger)

    client = TestClient(main.app)
    quota_resp = client.get("/api/quota").json()
    assert quota_resp["remaining_today"] == 0

    draft_resp = client.post(
        "/api/advisory/draft",
        json={"surge": 3.0, "lang": "en", "exposure": {}},
    )
    assert draft_resp.status_code == 200
    assert '"mode": "template"' in draft_resp.text
    assert "daily Gemini budget exhausted" in draft_resp.text


def test_ai_panel_contract_case4_guardrail_rejection(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key_for_test")
    mock_state = gemini.ModelState(selected="gemini-3.7-flash", available=["gemini-3.7-flash"])
    monkeypatch.setattr(gemini, "discover", lambda force=False: mock_state)
    monkeypatch.setattr(gemini.ledger(), "consume", lambda: True)

    # Mock _generate to return text with invented numbers (e.g. 999999 casualties)
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Alert: 999999 casualties estimated in Kendrapara district."}]
                }
            }
        ]
    }
    monkeypatch.setattr(gemini, "_generate", lambda *args, **kwargs: payload)
    monkeypatch.setattr(gemini, "_cache_get", lambda key: None)

    client = TestClient(main.app)
    draft_resp = client.post(
        "/api/advisory/draft",
        json={"surge": 3.0, "lang": "en", "exposure": {}},
    )
    assert draft_resp.status_code == 200
    assert '"mode": "template"' in draft_resp.text
    assert "guardrail rejected the model draft" in draft_resp.text
