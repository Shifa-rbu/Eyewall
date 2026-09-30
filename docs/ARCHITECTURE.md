# Architecture and trust boundary

The browser serves the vanilla JavaScript map, historical data, and screening calculation. It has no credential input and makes no direct Gemini request. The server serves the app and processed data from separate read-only static mounts and handles the exposure endpoint, template SSE drafts, SQLite review decisions, and audit export.

The browser sends the computed exposure summary only to the same-origin advisory endpoint. The server stores the draft and sends tokens from the local template. Gemini drafting is not implemented, even if a key is present. No review decision triggers outbound network activity or a message dispatch.

SQLite holds drafts, decisions, and a SHA-256 hash chain over canonical JSON payloads. This detects edits to the audit sequence; it is not a signed or externally anchored ledger.

The only external browser requests still in use are Leaflet from unpkg and OpenStreetMap tiles. The Open-Meteo request runs server-side. Leaflet has not yet been vendored locally.

## Data flow

    data/ ──> browser flood mask ──> map and displayed estimates
       └──> FastAPI exposure endpoint (independent mirror)
    user button ──> POST /api/advisory/draft ──> template + SQLite draft
    reviewer ──> decision endpoint ──> SQLite decision + audit record

## Trust boundary

Secrets are intended for server environment configuration. The current Gemini and Earth Engine adapters are absent, so the health endpoint reports them unavailable. Do not treat the presence of environment variables as proof that an integration works. Static files are served from static/ and data/ only; the project root, .env, raw inputs, and database are not mounted.
