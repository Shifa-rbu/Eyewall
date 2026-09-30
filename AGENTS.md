# AGENTS.md — read this before changing anything

## Acceptance gate — run before every commit
    python -m ruff check .     # must print exactly: All checks passed!
    python -m pytest -q        # must report 0 failed, 0 errors

Baseline is **161 passed**. The count must never drop below 161. If it rises, you added
tests, which is good. Takes about 13 seconds. Never weaken this gate to make it pass.

## Hard rules — never violate
1. Gemini drafts text; a person reviews it. Never send a warning automatically.
2. Never invent a number. Every figure must exist in the computed payload. Invented
   population, casualty, area or damage figures are a hard failure.
3. API keys stay server-side. Never in browser code or committed files.
4. Label the flood layer and water-level output as approximate screening, not a forecast.
5. Point users to IMD/OSDMA and keep uncertainty visible.

## Already built — do not rebuild, do not re-verify
- `server/guardrail.py`       number + population guardrail, adversarially tested
- `server/gemini.py`          model discovery, daily quota ledger, input-hash cache,
                              template fallback on every failure path
- `server/accessibility.py`   road graph, union-find, iterative Tarjan bridges
- `server/waterlevel.py`      surge + tide + barometer + wind + wave decomposition
- `server/cap.py`             CAP 1.2 XML, `status=Exercise` always, 7 departments
- `server/main.py`            15 `/api` routes, strict CSP, security headers
- `tests/test_security.py`    CSP regression: every host `app.js` calls must be permitted
- `scripts/verify_google.py`  live-key checker, run by hand, not in CI
- `deploy/firebase/build_site.sh`, `firebase.json`   static hosting

## Not built — do not claim otherwise
- Earth Engine / Sentinel-1 retrieval (`/api/sar/refresh` returns 409 by design)
- Automatic message dispatch
- Opt-in CORS for a separately hosted frontend
- Gating of the two public write endpoints
- Any AI panel in the interface
- No fixed Gemini model id has been validated against the live API

## File ownership — never edit a file you do not own
- **Khudaija:** `server/**`, `tests/**`, `scripts/**`, `docs/**`, `Dockerfile`,
  `docker-compose.yml`, `requirements.txt`, `.env.example`, `.github/**`,
  and exactly one frontend file: `static/ai.js`
- **Jeeya:** `app.js`, `static/app.js`, `static/ai.html`, `index.html`, `style.css`,
  `firebase.json`, `deploy/**`, `README.md`, `DESCRIPTION.md`, `DATA_SOURCES.md`,
  `TESTING.md`, `PR_BODY.md`, `validation/**`

If a task needs a change outside your files, stop and report it. Never edit across the fence.

Other invariants:
- `app.js` and `static/app.js` must stay byte-identical: `diff -q app.js static/app.js`
  must print nothing.
- Never `git add -A` or `git add .` — always name explicit paths.
- `git pull --rebase` before every push.

## AI panel contract — agreed, do not change unilaterally
The panel is the one feature both people touch, so it is split by file.
`static/ai.html` (Jeeya) provides these elements with exactly these ids and nothing else:
    #ai-status    capability + model line        #ai-quota   remaining calls today
    #ai-advisory  advisory text output           #ai-aimode  draft mode label
    #ai-risk      structured risk output         #ai-error   notice / error line

`static/ai.js` (Khudaija) reads and writes those elements' `textContent` / `value` only.
It must not create or restyle them. `static/ai.html` must contain no `fetch` and no URL.
Both use `const API_BASE = (window.EYEWALL_API_BASE || "")` and keep every route relative
(`"/api/..."`), so neither file introduces an external host. If either person needs a
change to this contract, ask before editing.

## Known traps
1. **Gemini model ids are unvalidated against the live API.** Discovery walks
   `3.7 → 3.8 → 3.6 → 3.5 → 3.5-flash-lite` and degrades to a template rather than
   crashing, so a wrong id looks like success. Run `scripts/verify_google.py` with a real
   key before claiming anything about the integration.
2. **No external host literals in `app.js`.** `tests/test_security.py` scans the frontend
   for `https://host` and asserts the server CSP permits each one found. Hardcoding an API
   URL there turns the security test red. Read the base from `window.EYEWALL_API_BASE`.
3. **The CSP wildcard trap is already fixed.** A `https://*.tile.openstreetmap.org`
   wildcard does not match the apex host `https://tile.openstreetmap.org`. Both forms are
   listed deliberately; do not "tidy" one away.
4. **Rate limiter leaks between tests.** `main._rate` is an in-process 10-per-minute
   limiter. Tests that exercise `/api/advisory/draft` must reset it, or they collide.
5. **`read_risk` must stay guardrailed.** It once shipped without the number check and
   served invented population figures with `ok=True`. `tests/test_gemini_offline.py` now
   covers this; do not remove those tests.

## Checkpoint discipline — the repo is the memory, not the chat
After every green gate, commit that task alone with explicit paths, then append one line
to `HANDOFF.md`. Uncommitted work cannot be recovered; committed work always can.
When told "CHECKPOINT AND STOP": stop starting new work, commit if green or revert if
red, confirm the tree is green, rewrite `HANDOFF.md` (under 20 lines), commit it, and
reply with only the last green sha, the gate numbers and the one next step.
