"""Same-origin API for the keyless Eyewall screening demo."""
import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import gemini, review
from .accessibility import screen as accessibility_screen
from .cap import DEPARTMENTS, build_cap, validate
from .config import ROOT
from .exposure import compute_exposure
from .waterlevel import WaterLevelInput, compose, from_landfall_timing

app = FastAPI(title="Eyewall", version="0.2.0")
# Same-origin only unless EYEWALL_ALLOWED_ORIGINS is configured.
_rate = defaultdict(deque)

_cors_cache = {}


class OptInCORSMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_origins = os.getenv("EYEWALL_ALLOWED_ORIGINS", "").strip()
        if not raw_origins:
            await self.app(scope, receive, send)
            return

        if raw_origins not in _cors_cache:
            origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
            _cors_cache[raw_origins] = CORSMiddleware(
                self.app,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        await _cors_cache[raw_origins](scope, receive, send)


app.add_middleware(OptInCORSMiddleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    raw_origins = os.getenv("EYEWALL_ALLOWED_ORIGINS", "").strip()
    allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    connect_src = "connect-src 'self'"
    if allowed_origins:
        connect_src += " " + " ".join(allowed_origins)

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        # app.js loads tiles from the bare host tile.openstreetmap.org; a
        # wildcard form (https://*.tile.openstreetmap.org) does NOT match an
        # apex host and silently blanks the map. Both forms are listed so a
        # future switch to a numbered/regional tile host keeps working.
        "img-src 'self' data: https://tile.openstreetmap.org https://*.tile.openstreetmap.org; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        f"script-src 'self' https://unpkg.com; {connect_src}; "
        "form-action 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


class DraftRequest(BaseModel):
    surge: float = Field(ge=0, le=8)
    lang: str = Field(pattern="^(en|hi|or)$")
    exposure: dict
    include_grounding: bool = False


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject|edit)$")
    reviewer: str = Field(min_length=1, max_length=120)
    edited_text: str | None = None
    note: str | None = None


@app.get("/api/health")
def health():
    # Gemini state is derived from live discovery, not from the mere presence of
    # an environment variable: a key that cannot list models is not "configured"
    # in any way a user can rely on.
    return {"status": "ok", "version": app.version,
            "gemini": gemini.status(),
            "gee": {"configured": False, "cached_evidence": []},
            "exposure_engine": "server"}


@app.get("/api/exposure")
def exposure(surge: float = 3.0):
    if not 0 <= surge <= 8:
        raise HTTPException(422, "surge must be between 0 and 8 metres")
    return compute_exposure(surge)


@app.get("/api/accessibility")
def accessibility(surge: float = 3.5):
    """Road-network screening: what floods, what gets cut off, where the chokepoints are."""
    if not 0 <= surge <= 8:
        raise HTTPException(422, "surge must be between 0 and 8 metres")
    return accessibility_screen(surge)


@app.get("/api/waterlevel")
def waterlevel(
    surge: float = 3.0,
    hours_to_landfall: float | None = None,
    tide_m: float = 0.0,
    tide_amplitude: float = 1.0,
    pressure_hpa: float = 1013.25,
    wind_speed: float = 0.0,
    fetch_km: float = 50.0,
    depth_m: float = 20.0,
    beach_slope: float = 0.02,
):
    """Total water level and its components.

    With ``hours_to_landfall`` the tide is derived from landfall timing; without
    it the caller supplies ``tide_m`` directly.
    """
    if not 0 <= surge <= 8:
        raise HTTPException(422, "surge must be between 0 and 8 metres")
    common = {
        "pressure_hpa": pressure_hpa,
        "wind_speed_ms": wind_speed,
        "fetch_km": fetch_km,
        "depth_m": depth_m,
        "beach_slope": beach_slope,
    }
    if hours_to_landfall is None:
        return compose(WaterLevelInput(surge_m=surge, tide_m=tide_m, **common))
    return from_landfall_timing(
        surge, hours_to_landfall, tide_amplitude_m=tide_amplitude, **common
    )


@app.get("/api/cap")
def cap(
    surge: float = 3.5,
    department: str = "disaster",
    areas: str = "",
    format: str = "xml",
):
    """CAP 1.2 exercise alert for the scenario, routed by department.

    Always emitted as ``status=Exercise``. ``format=xml`` returns the document a
    CAP consumer would ingest; ``format=json`` returns it with validation results.
    """
    if not 0 <= surge <= 8:
        raise HTTPException(422, "surge must be between 0 and 8 metres")
    if format not in {"xml", "json"}:
        raise HTTPException(422, "format must be 'xml' or 'json'")
    area_list = [a.strip() for a in areas.split(",") if a.strip()]
    doc = build_cap(
        surge,
        compute_exposure(surge),
        accessibility=accessibility_screen(surge),
        department=department,
        areas=area_list or None,
    )
    if format == "xml":
        return Response(content=doc, media_type="application/cap+xml")
    return {
        "xml": doc,
        "problems": validate(doc),
        "departments": DEPARTMENTS,
        "status": "Exercise",
    }


class RiskRequest(BaseModel):
    surge: float = Field(ge=0, le=8)
    exposure: dict


@app.post("/api/risk/read")
def risk_read(body: RiskRequest):
    """Structured risk assessment from Gemini, with the model's schema enforced."""
    return gemini.read_risk(body.exposure, body.surge)


@app.post("/api/vision/chip")
async def vision_chip(request: Request):
    """Multimodal read of an uploaded image chip (SAR, field photo, screenshot).

    Accepts image bytes directly so no user image is written to disk.
    """
    raw = await request.body()
    if not raw:
        raise HTTPException(422, "empty image body")
    if len(raw) > 4 * 1024 * 1024:
        raise HTTPException(413, "image larger than 4 MB")
    mime = request.headers.get("content-type", "image/png").split(";")[0].strip()
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, f"unsupported image type {mime!r}")
    return gemini.describe_sar_chip(raw, mime_type=mime)


@app.get("/api/quota")
def quota():
    """Remaining Gemini calls today, so the UI can be honest about the budget."""
    return {"daily_budget": gemini.DAILY_BUDGET,
            "remaining_today": gemini.ledger().remaining(),
            "configured": gemini.configured()}


@app.get("/api/weather")
async def weather():
    url = "https://api.open-meteo.com/v1/forecast?latitude=20.22&longitude=86.55&current=precipitation&hourly=precipitation&forecast_days=2"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Open-Meteo forecast is unavailable") from exc


@app.post("/api/advisory/draft")
async def draft(request: Request, body: DraftRequest):
    now = time.monotonic()
    bucket = _rate[request.client.host if request.client else "unknown"]
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= 10:
        raise HTTPException(429, "Draft limit reached; try again shortly", headers={"Retry-After":"60"})
    bucket.append(now)
    result = gemini.draft_advisory(body.exposure, body.surge, body.lang)
    text = result["text"]
    draft_id = review.create_draft(body.surge, body.lang, body.exposure, text)
    async def events():
        for token in text.split(" "):
            yield "data: " + json.dumps({"text":token + " "}, ensure_ascii=False) + "\n\n"
        done = {"draftId": draft_id, "model": result.get("model"), "mode": result["mode"],
                "reviewRequired": True, "guardrail": result.get("guardrail"),
                "cached": result.get("cached", False), "note": result.get("note")}
        yield "event: done\ndata: " + json.dumps(done, ensure_ascii=False) + "\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-cache"})


@app.get("/api/review/queue")
def get_queue():
    return review.queue()


def _writes_allowed() -> bool:
    return os.getenv("EYEWALL_ALLOW_WRITES", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


@app.post("/api/review/{draft_id}/decision")
def make_decision(draft_id: str, body: DecisionRequest):
    if not _writes_allowed():
        raise HTTPException(403, "Public writes are disabled")
    result = review.decide(draft_id, body.decision, body.reviewer, body.edited_text, body.note)
    if result is None:
        raise HTTPException(404, "Draft not found")
    return result


@app.get("/api/audit/export")
def audit_export():
    return {"entries":review.export_audit(), "verification":review.verify_audit()}


@app.post("/api/sar/refresh", status_code=202)
def sar_refresh():
    if not _writes_allowed():
        raise HTTPException(403, "Public writes are disabled")
    raise HTTPException(409, "Earth Engine integration is unavailable: service-account credentials and export pipeline are not configured")


@app.get("/api/sar/evidence")
def sar_evidence():
    return {"storms":[]}


# Serve the existing no-build static site from repository root. API routes above
# take precedence; root index.html continues to support GitHub Pages.
app.mount("/data", StaticFiles(directory=Path(ROOT) / "data"), name="data")
app.mount("/", StaticFiles(directory=Path(ROOT) / "static", html=True), name="static")
