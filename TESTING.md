# Testing matrix

Run locally:

    py -m pytest -q
    py -m ruff check .

Current automated coverage checks exposure fixtures at 0, 3, and 5 metres, monotonic area, coordinate helpers, review approval/rejection/edit records, local-only review I/O, and audit tamper detection.

Not yet covered: browser/server parity, API-level rate limiting, full SSE consumption, CSP/static mount and key leak assertions, accessibility contrast audits, Playwright browser smoke, Google adapter discovery, or SAR processing. Playwright requires a separately installed browser and is not in CI.
