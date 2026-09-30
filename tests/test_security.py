"""Security-header regression tests.

The tile-host assertion exists because a CSP wildcard (`https://*.tile.openstreetmap.org`)
does not match an apex host (`https://tile.openstreetmap.org`). That mismatch shipped
once and silently blanked the entire basemap while every other test stayed green.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from server.main import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def _csp() -> str:
    response = client.get("/api/health")
    assert response.status_code == 200
    return response.headers["Content-Security-Policy"]


def test_security_headers_present():
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_csp_allows_every_external_host_the_frontend_actually_uses():
    """Every https host referenced by static/app.js must be permitted by the CSP.

    Parses the real frontend rather than hardcoding expectations, so this test
    fails if someone adds a new data source without updating the policy.
    """
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    csp = _csp()

    # Split the policy into directive -> sources
    directives = {}
    for part in csp.split(";"):
        bits = part.split()
        if bits:
            directives[bits[0].strip().lower()] = bits[1:]

    hosts = set(re.findall(r"https://([A-Za-z0-9._-]+)", app_js))
    assert hosts, "expected at least one external host in app.js"

    for host in sorted(hosts):
        url = f"https://{host}/"
        # Which directive governs this host depends on how it is used.
        if "/{z}/{x}/{y}" in app_js and host in app_js.split("tileLayer")[1][:200]:
            directive = "img-src"
        else:
            directive = "connect-src"
        sources = directives.get(directive, [])
        allowed = any(
            s == url
            or s == f"https://{host}"
            or (s.startswith("https://*.") and host.endswith(s[len("https://*"):]))
            for s in sources
        )
        # 'self' permits same-origin only; skip hosts already covered by it.
        assert allowed, (
            f"CSP {directive} does not allow {url} which static/app.js calls. "
            f"{directive} sources are: {sources}"
        )


def test_csp_allows_the_osm_tile_apex_host_specifically():
    """Explicit guard for the exact regression: apex host vs wildcard."""
    csp = _csp()
    img_src = csp.split("img-src", 1)[1].split(";", 1)[0]
    assert "https://tile.openstreetmap.org" in img_src.split(), (
        "img-src must list the bare host https://tile.openstreetmap.org; "
        "a https://*.tile.openstreetmap.org wildcard does not match it"
    )
