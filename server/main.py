"""Same-origin API for the keyless Eyewall screening demo."""
from collections import defaultdict, deque
import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx

from . import review
from .config import ROOT
from .exposure import compute_exposure

app = FastAPI(title="Eyewall", version="0.2.0")
# Same-origin only. No permissive CORS middleware is installed.
_rate = defaultdict(deque)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; style-src 'self' 'unsafe-inline' https://unpkg.com; script-src 'self' https://unpkg.com; connect-src 'self'; form-action 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
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
    # Google integrations are intentionally unavailable until implemented and
    # credential-tested; environment variables alone are not proof of service.
    return {"status":"ok", "version":app.version,
            "gemini":{"configured":False,"model":None,"available":[]},
            "gee":{"configured":False,"cached_evidence":[]},
            "exposure_engine":"server"}


@app.get("/api/exposure")
def exposure(surge: float = 3.0):
    if not 0 <= surge <= 8:
        raise HTTPException(422, "surge must be between 0 and 8 metres")
    return compute_exposure(surge)


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


def template_advisory(req):
    e = req.exposure
    if req.lang == "hi":
        return (f"चक्रवात परिदृश्य समीक्षा: {req.surge:.1f} मीटर सर्ज; लगभग {e.get('areaKm2', 0):.0f} वर्ग किमी भूमि प्रभावित। "
                "यह केवल मानव समीक्षा हेतु प्रारूप है। आधिकारिक चेतावनियों के लिए IMD/OSDMA देखें।")
    if req.lang == "or":
        return (f"ବାତ୍ୟା ପରିଦୃଶ୍ୟ ସମୀକ୍ଷା: {req.surge:.1f} ମିଟର ସର୍ଜ; ପ୍ରାୟ {e.get('areaKm2', 0):.0f} ବର୍ଗ କିମି ଭୂମି ପ୍ରଭାବିତ। "
                "ଏହା କେବଳ ମାନବ ସମୀକ୍ଷା ପାଇଁ ଖସଡ଼ା। ଅଧିକୃତ ସତର୍କତା ପାଇଁ IMD/OSDMA ଦେଖନ୍ତୁ।")
    return (f"CYCLONE SCENARIO REVIEW — {req.surge:.1f} m surge; about {e.get('areaKm2', 0):.0f} km² of land screened as inundated. "
            f"Screened assets: {e.get('medical', 0)} medical, {e.get('shelter', 0)} shelter proxies, {e.get('power', 0)} power. "
            "Draft for human review only. This is not an official forecast or evacuation instruction; consult IMD/OSDMA.")


@app.post("/api/advisory/draft")
async def draft(request: Request, body: DraftRequest):
    now = time.monotonic()
    bucket = _rate[request.client.host if request.client else "unknown"]
    while bucket and now - bucket[0] >= 60:
        bucket.popleft()
    if len(bucket) >= 10:
        raise HTTPException(429, "Draft limit reached; try again shortly", headers={"Retry-After":"60"})
    bucket.append(now)
    text = template_advisory(body)
    draft_id = review.create_draft(body.surge, body.lang, body.exposure, text)
    async def events():
        for token in text.split(" "):
            yield "data: " + json.dumps({"text":token + " "}, ensure_ascii=False) + "\n\n"
        done = {"draftId":draft_id,"model":None,"mode":"template","reviewRequired":True}
        yield "event: done\ndata: " + json.dumps(done) + "\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-cache"})


@app.get("/api/review/queue")
def get_queue():
    return review.queue()


@app.post("/api/review/{draft_id}/decision")
def make_decision(draft_id: str, body: DecisionRequest):
    result = review.decide(draft_id, body.decision, body.reviewer, body.edited_text, body.note)
    if result is None:
        raise HTTPException(404, "Draft not found")
    return result


@app.get("/api/audit/export")
def audit_export():
    return {"entries":review.export_audit(), "verification":review.verify_audit()}


@app.post("/api/sar/refresh", status_code=202)
def sar_refresh():
    raise HTTPException(409, "Earth Engine integration is unavailable: service-account credentials and export pipeline are not configured")


@app.get("/api/sar/evidence")
def sar_evidence():
    return {"storms":[]}


# Serve the existing no-build static site from repository root. API routes above
# take precedence; root index.html continues to support GitHub Pages.
app.mount("/data", StaticFiles(directory=Path(ROOT) / "data"), name="data")
app.mount("/", StaticFiles(directory=Path(ROOT) / "static", html=True), name="static")
