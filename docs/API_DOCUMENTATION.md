# Eyewall Server & API Documentation

This document describes how to run, configure, and manage the Eyewall backend API server, its environment variables, persisted daily quota ledger, and Gemini fallback mechanisms.

---

## 1. API Operation

### Running the API Locally

To start the local FastAPI server using `uvicorn` under the default development configuration:

```bash
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Or using python:

```bash
python3 -m uvicorn server.main:app --reload --port 8000
```

### Server Configuration Overview
- **Framework**: FastAPI / Starlette
- **Default Port**: 8000 (configurable via uvicorn parameters)
- **Static Assets**: Serves `data/` at `/data` and `static/` at `/`
- **Security**: Built-in HTTP security headers (`Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`).

---

## 2. Environment Variables

The server configuration is controlled via environment variables:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | String | Unset | Server-side Gemini API key used for model discovery and content generation. Never exposed to browser. |
| `EYEWALL_ALLOWED_ORIGINS` | String (Comma-separated) | Unset | Opt-in CORS allowed origins (e.g. `https://example.com,https://app.example.com`). Also dynamically appends origins to the CSP `connect-src` header. When unset, CORS is disabled and `connect-src` is `'self'`. |
| `EYEWALL_ALLOW_WRITES` | String / Flag | `false` (Unset) | Controls access to public write endpoints (`POST /api/review/{draft_id}/decision` and `POST /api/sar/refresh`). When unset/disabled, endpoints return HTTP 403 Forbidden. |
| `EYEWALL_GEMINI_MODEL` | String | Unset | Optional model pin override (e.g. `gemini-3.7-flash`). When set, model discovery verifies its availability before selection. |
| `EYEWALL_GEMINI_DAILY_BUDGET` | Integer | `15` | Conservative daily limit on Gemini API calls to prevent exhausting free-tier API quota during development or live demos. |

---

## 3. Persisted Quota Ledger

### Purpose & Architecture
The Gemini free tier has strict daily request quotas. To prevent application crashes or blowing API quotas during dev server reloads (`uvicorn --reload`), Eyewall uses a file-persisted quota ledger (`server.gemini.QuotaLedger`).

### Persistence Details
- **File Location**: `.runtime/gemini_quota.json` (relative to repository root).
- **Structure**:
  ```json
  {
    "date": "2026-09-30",
    "used": 3
  }
  ```
- **Tracking & Reset**: Daily reset is automatic based on the current UTC date (`YYYY-MM-DD`). If the date in the ledger matches today, `used` is read; otherwise, a new ledger entry for today starts at `used = 0`.
- **Remaining Quota**: Computed as `max(0, budget - used)`.
- **Exhaustion Behavior**: When `used >= budget`, `ledger().consume()` returns `False`. The backend immediately falls back to the deterministic template advisory (`mode: "template"`), returning a note: `"daily Gemini budget exhausted; using template"`. No remote API call is initiated.

---

## 4. Gemini Fallback Chain

### Model Discovery Preference Order
When `GEMINI_API_KEY` is provided, model discovery probes available models against a strict preference hierarchy:

1. `gemini-3.7-flash` (Primary model named in problem specification)
2. `gemini-3.8-flash` (Newest stable Flash model)
3. `gemini-3.6-flash`
4. `gemini-3.5-flash`
5. `gemini-3.5-flash-lite` (Largest daily allowance fallback)

If `EYEWALL_GEMINI_MODEL` is set, that specific model is preferred if usable.

### Complete Fallback Path
At every stage of execution, failures degrade gracefully to the deterministic template generator (`server.templates.template_advisory`) without crashing:

```
[Request /api/advisory/draft]
         │
         ├── API Key missing? ──────────────> [Template Fallback] (note: "no GEMINI_API_KEY...")
         │
         ├── Discovery fails / no model? ───> [Template Fallback] (note: state.error)
         │
         ├── Daily Quota exhausted? ─────────> [Template Fallback] (note: "daily Gemini budget exhausted...")
         │
         ├── Gemini API error / timeout? ───> [Template Fallback] (note: "Gemini call failed...")
         │
         ├── Empty / blocked output? ───────> [Template Fallback] (note: "Gemini returned an empty...")
         │
         ├── Guardrail violation? ──────────> [Template Fallback] (note: "guardrail rejected...", guardrail.ok: false)
         │
         └── Success! ──────────────────────> [Gemini Output] (mode: "gemini", model: "gemini-3.7-flash", guardrail.ok: true)
```

### User & UI Visibility
- **Gemini Generation**: Displayed in UI as `Gemini (<model_name>)` only when `mode == "gemini"`.
- **Template Fallback**: Displayed as `Template` whenever `mode == "template"`. The word `Gemini` is never displayed for template fallbacks.
- **Guardrail Rejection**: When `guardrail.ok == false`, the rejected draft is suppressed, the UI falls back to the template, and a clear safety notice is displayed in `#ai-error`.
- **Live Model ID Validation**: Note that model strings in the discovery chain require live key verification via `python3 scripts/verify_google.py` with a valid `GEMINI_API_KEY` before claiming live Google API compatibility.
