---
title: Eyewall · Odisha cyclone screening
emoji: 🌊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Eyewall

An open, same-origin FastAPI and static map demo for cyclone-coast preparation in the Kendrapara–Paradip delta, Odisha.

**Application source commit:** `@SOURCE_COMMIT@`
**Runtime:** Docker Space, port 7860

## What this Space serves

- `/` — the map console and local screening interface.
- `/api/health` — service status, including the `gee` capability block.
- `/api/exposure?surge=3.5` — screening exposure from the sea-connected bathtub scenario.
- `/api/accessibility?surge=3.5` — road-network screening for impassable distance, chokepoints, and isolation.
- `/api/waterlevel?surge=3.5` — a decomposed total-water-level estimate.
- `/api/cap?surge=3.5&format=xml` — a CAP 1.2 exercise alert; its status is always `Exercise`.

Public writes are disabled by default. In this deployment, `POST /api/sar/refresh` returns **403** with “Public writes are disabled.” Do not enable public writes for a demonstration Space.

## Limits

The flood layer and water-level outputs are screening scenarios, not hydrodynamic forecasts. Earth Engine / Sentinel-1 retrieval is not implemented. The app does not provide population figures or automatic dispatch. Mapped facilities and roads can be incomplete; use official IMD and OSDMA guidance and local verification.

Gemini drafting is optional and server-side. Without a usable server key, drafts use the local template. Model output is a draft for human review, never an issued warning.

This public Space uses ephemeral storage. The review queue, audit history, and Gemini quota ledger can reset when the Space restarts or sleeps. Do not use it as an operational record system.
