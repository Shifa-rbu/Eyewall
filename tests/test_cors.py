from fastapi.testclient import TestClient

from server.main import app


def test_cors_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EYEWALL_ALLOWED_ORIGINS", raising=False)
    client = TestClient(app)
    response = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "connect-src 'self';" in csp


def test_cors_enabled_for_configured_origin(monkeypatch):
    monkeypatch.setenv("EYEWALL_ALLOWED_ORIGINS", "https://example.com, https://app.example.com")
    client = TestClient(app)
    response = client.get("/api/health", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://example.com"
    csp = response.headers["Content-Security-Policy"]
    assert "connect-src 'self' https://example.com https://app.example.com;" in csp


def test_cors_blocks_unconfigured_origin(monkeypatch):
    monkeypatch.setenv("EYEWALL_ALLOWED_ORIGINS", "https://example.com")
    client = TestClient(app)
    response = client.get("/api/health", headers={"Origin": "https://malicious.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    csp = response.headers["Content-Security-Policy"]
    assert "connect-src 'self' https://example.com;" in csp
