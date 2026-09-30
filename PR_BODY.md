# Summary

Adds a keyless FastAPI wrapper for the existing static Eyewall prototype, a screening exposure mirror, template-only advisory SSE, local review and hash-chained audit storage, basic security headers, and regression/API tests. Removes the browser Gemini key field and browser-to-Gemini calls.

## Motivation

The prior frontend requested Gemini on every slider recompute and exposed the API key in the browser URL. It also injected third-party OSM feature names as HTML. The update removes those paths and makes unavailable Google capabilities explicit.

## Defect status

| ID | Status | Notes |
|---|---|---|
| D1 | Fixed | Removed browser key input and direct Gemini requests. |
| D2 | Fixed | Exposure slider is debounced; drafting only runs from an explicit button. |
| D3 | Fixed | Facility names and Leaflet popup values are rendered as text. |
| D4 | Fixed | Gemini model discovery and drafting implemented server-side (verified model gemini-3.7-flash). |
| D5 | Partial | Loading messages/progress added; not a full progress bar. |
| D6 | Partial | Inline dismissible errors added; tile-specific error detection is missing. |
| D7 | Not fixed | Leaflet remains loaded from unpkg; no local vendor bundle is available. |
| D8 | Partial | Slider labels, live values, focus styles, reduced-motion handling and manual track scrubber added; full contrast and color-blind audits remain. |
| D9 | Fixed | README now documents the actual frontend. |
| D10 | Partial | gee_service documents that integration is absent; no Earth Engine implementation. |
| D11 | Fixed | pytest tests (169 passed) and CI added; ruff checks clean. |
| D12 | Not fixed | No reference masks or observed flood data are available. |

## Real vs. illustrative

- Local processed elevation, OSM assets, and historical IBTrACS records are real source-derived data, with source limitations in DATA_SOURCES.md.
- Flood extents and exposure are screening outputs from the sea-connected bathtub method.
- Server-side Gemini drafting and risk assessment use model discovery (verified model `gemini-3.7-flash`, verified 30 September 2026) with number guardrail and deterministic template fallback.
- No Sentinel-1 export or Earth Engine service is implemented.
- Review decisions and audit entries are local SQLite records. No message is sent.

## Test evidence

Actual local command results:

    node --check app.js
    (exit 0)

    python3 -m pytest -q
    169 passed in 4.51s

    python3 -m ruff check .
    All checks passed!

CI installs ruff from requirements.txt and runs `python -m pytest -q` and `ruff check .`.

## Reviewer's guide

1. server/exposure.py — screening calculation mirror.
2. server/review.py — SQLite queue and audit-chain verification.
3. server/main.py — API contracts, rate limit and security headers.
4. app.js and index.html — browser key removal, explicit draft action, accessible controls.
5. tests/ — fixture, API, rate-limit, security, CORS, writes gate, and audit tests.

## Migration notes

The existing root index.html remains in place for GitHub Pages. FastAPI serves the synchronized static/index.html, static/app.js, and static/style.css copies. The #gemkey input and all browser Gemini calls were removed. Server-side Gemini integration uses runtime model discovery and falls back to a deterministic template when the key, quota, or network is unavailable.

## Checklist

- [x] No browser-side Gemini key or request
- [x] Local review decision and audit chain
- [x] Existing elevation/assets/tracks and prep.py behavior unchanged
- [x] Keyless server startup path implemented
- [x] Test and CI scaffolding added
- [x] Gemini server integration and model discovery (verified `gemini-3.7-flash`)
- [ ] Leaflet vendor bundle and complete CSP
- [ ] Earth Engine integration and cached SAR exports
- [ ] Event validation with georeferenced reference masks
- [ ] Full accessibility and browser E2E audit
- [x] Conventional commit series, branch push, and hosted PR
