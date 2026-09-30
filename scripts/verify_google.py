#!/usr/bin/env python3
"""Operator script: verify the Google integrations against the REAL key.

Not part of the test suite. The suite must pass with no credentials and no
network, so anything that needs a live key lives here and is run by hand before
a demo or a submission.

    export GEMINI_API_KEY=...
    python scripts/verify_google.py

It answers the three questions that offline tests structurally cannot:

1. Is the key entitled to the models the preference list names?
2. Does a real generateContent call return usable text?
3. Does the number guardrail hold on a REAL model response, not a fixture?

Exit code is non-zero if a hard check fails, so it can gate the deploy.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import gemini  # noqa: E402
from server.guardrail import check  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    print(f"[{status}] {name}" + (f"  - {detail}" if detail else ""))


def main() -> int:
    print("=" * 72)
    print("Eyewall - live Google integration check")
    print("=" * 72)

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        record("key present", FAIL, "set GEMINI_API_KEY (or GOOGLE_API_KEY) first")
        return 1
    record("key present", PASS, f"{key[:4]}...{key[-4:]} ({len(key)} chars)")

    # ---- 1. discovery -----------------------------------------------------
    state = gemini.discover(force=True)
    if state.selected:
        record("model discovery", PASS, f"selected {state.selected}")
        if state.fallback_used:
            record(
                "preferred model available",
                WARN,
                f"fell back to {state.selected}; the problem statement names "
                f"{gemini.MODEL_PREFERENCE[0]}. Claim the model you actually used.",
            )
        else:
            record("preferred model available", PASS, gemini.MODEL_PREFERENCE[0])
    else:
        record("model discovery", FAIL, state.error or "no model selected")
        print()
        print("Nothing downstream can pass without a model. Stopping.")
        return 1

    if state.available:
        print(f"       key can see {len(state.available)} models, e.g. "
              f"{', '.join(state.available[:6])}")

    # ---- 2. a real generation --------------------------------------------
    exposure = {
        "surge": 3.5, "areaKm2": 275.73, "medical": 5, "shelter": 4, "power": 8,
        "roadKm": 32.41, "gridKm": 32.02,
    }
    draft = gemini.draft_advisory(exposure, 3.5, "en")
    if draft["mode"] == "gemini":
        record("advisory generation", PASS, f"{len(draft['text'])} chars from {draft['model']}")
        g = draft.get("guardrail") or {}
        if g.get("ok"):
            record("guardrail on real output", PASS, f"{g.get('checked_numbers')} numbers checked")
        else:
            record("guardrail on real output", WARN, "rejected; template used instead")
        print()
        print("--- live draft begins ---")
        print(draft["text"][:800])
        print("--- live draft ends ---")
    elif draft["mode"] == "template":
        note = draft.get("note", "")
        if "budget" in note:
            record("advisory generation", WARN, "daily budget already spent; rerun tomorrow")
        else:
            record("advisory generation", FAIL, note or "fell back to template")
        # A template fallback is survivable: prove the guardrail still works.
        record("guardrail (offline path)", PASS if check(draft["text"], exposure).ok else FAIL)

    # ---- 3. structured risk read -----------------------------------------
    risk = gemini.read_risk(exposure, 3.5)
    if risk.get("ok"):
        record("structured risk read", PASS, f"score={risk['risk'].get('score')}")
        g = risk.get("guardrail") or {}
        record(
            "guardrail on risk read",
            PASS if g.get("ok") else FAIL,
            f"{g.get('checked_numbers', 0)} numbers checked" if g else "NO GUARDRAIL APPLIED",
        )
    else:
        record("structured risk read", WARN, risk.get("note", "unavailable"))

    # ---- 4. multimodal ---------------------------------------------------
    chip = ROOT / "docs" / "before.png"
    if chip.exists():
        vision = gemini.describe_sar_chip(chip.read_bytes(), mime_type="image/png",
                                         context="Sentinel-1 SAR pair window, Odisha coast")
        if vision.get("ok"):
            record("vision (multimodal)", PASS, f"{len(vision['description'])} chars")
            g = vision.get("guardrail") or {}
            if g and g.get("ok") is False:
                record("vision numbers", WARN, f"flagged: {g.get('violations')}")
            print()
            print("--- live vision read begins ---")
            print(vision["description"][:800])
            print("--- live vision read ends ---")
        else:
            record("vision (multimodal)", WARN, vision.get("note", "unavailable"))
    else:
        record("vision (multimodal)", WARN, f"{chip} not found; skipped")

    # ---- 5. quota --------------------------------------------------------
    status = gemini.status()
    record("quota ledger", PASS,
           f"{status['remaining_today']}/{status['daily_budget']} calls left today")

    # ---- 6. the key must not be reachable from the browser ----------------
    blob = repr(status) + repr(draft) + repr(risk)
    record("key never in output", PASS if key not in blob else FAIL)

    print()
    print("=" * 72)
    failures = [r for r in results if r[1] == FAIL]
    warns = [r for r in results if r[1] == WARN]
    print(f"{len(results)} checks: {len(results) - len(failures) - len(warns)} pass, "
          f"{len(warns)} warn, {len(failures)} fail")
    for name, _status, detail in failures:
        print(f"  FAILED: {name} - {detail}")
    print("=" * 72)
    if failures:
        print("Do not claim active Google integration until the failures are resolved.")
    elif warns:
        print("Integration works. Read the warnings: they change what you may claim.")
    else:
        print("All checks passed. Safe to claim the integration, naming the model above.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
