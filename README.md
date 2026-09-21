# Eyewall — Anticipatory-Action Console for India's Cyclone Coasts

Eyewall is a planned anticipatory-action console for India's cyclone-prone coasts. It begins with a reproducible data workflow for the Kendrapara–Paradip delta in Odisha and is intended to support transparent, human-reviewed preparation for cyclone risk.

Eyewall is a decision-support prototype, not an official forecast, evacuation directive, hydrodynamic model, verified damage/outage model, insurance product, or autonomous warning system.

## Current status

The repository currently contains a data-preparation pipeline and its processed outputs. There is no completed or deployed frontend in this repository.

### Available now

- `prep.py`, a standard-library Python data-preparation script.
- Processed SRTM elevation data for the configured Kendrapara–Paradip window.
- Processed OpenStreetMap infrastructure data, including medical points, shelter-capacity proxy points, selected roads, and transmission lines.
- Processed historical NOAA IBTrACS cyclone-track data; `prep.py` explicitly reads `raw/ibtracs.csv` and prepares the selected named storms.
- A reproducible data-preparation workflow, provided the documented raw inputs are supplied locally.

### Planned MVP

- A screening-level inundation scenario, not a hydrodynamic simulation.
- Runtime exposure calculations, including road length intersecting scenario inundation and transmission-line length intersecting scenario inundation.
- Cyclone-track replay.
- Open-Meteo forecast context, not observations.
- Gemini advisory drafting.
- Voice output.
- CAP-inspired JSON containing a CAP-inspired advisory draft.
- A human-review queue; no external message is sent.
- GEE-exported Sentinel-1 evidence.
- A parametric trigger candidate for review, rather than an automated payout or directive.

## Overview

The present pipeline crops elevation data, extracts selected public-map features, and normalizes historical cyclone tracks. Those inputs are intended to support a screening-level inundation and exposure workflow for human interpretation. In particular, schools, colleges, community facilities, and assembly points are treated as a shelter-capacity proxy; they are not verified shelter capacity or an operational evacuation registry.

## Local setup

The prepared outputs already live under `data/`. To reproduce them, obtain the raw source inputs described in [DATA_SOURCES.md](DATA_SOURCES.md), place them under the ignored `raw/` directory, then run:

```bash
python3 prep.py
```

`prep.py` uses only the Python standard library. It expects these local files:

```text
raw/elev.hgt.gz
raw/osm.xml
raw/ibtracs.csv
```

The script overwrites the processed files in `data/`. Review its configured bounds and storm selection before using it for another area or analysis.

## Repository structure

```text
prep.py                    Reproducible preprocessing workflow
data/elev.i16              Processed elevation grid
data/grid.json             Grid extent and dimensions
data/assets.json           Processed OSM points and line features
data/tracks.json           Processed historical IBTrACS tracks
gee/sentinel1_fani.js      Historical Sentinel-1 Fani evidence script for GEE
DATA_SOURCES.md            Verified source and attribution notes
DESCRIPTION.md             Short project description
```

## Data limitations

- Elevation is a processed terrain input, not a flood-depth, storm-surge, or inundation forecast.
- OpenStreetMap is a dated public extract and not a complete infrastructure registry. Feature tags, geometry, names, completeness, and recency may be incomplete or wrong.
- The shelter-capacity proxy does not establish shelter availability, staffing, condition, accessibility, capacity, or evacuation suitability.
- Historical NOAA IBTrACS tracks are retrospective records. They are not live track data, forecast context, or official warnings.
- Any future screening-level inundation scenario and exposure calculation will be illustrative and must be reviewed with local context, authoritative information, and appropriate domain expertise.
- Any planned AI-generated CAP-inspired advisory draft requires a human-review queue; no external message is sent by Eyewall.

## Roadmap

1. Implement the planned MVP interface and its transparent screening-level inundation scenario.
2. Add runtime exposure calculations and cyclone-track replay.
3. Add clearly labelled Open-Meteo forecast context and GEE-exported Sentinel-1 historical evidence.
4. Add bounded Gemini advisory drafting, voice output, CAP-inspired JSON, and a human-review queue.
5. Validate assumptions with domain experts and affected local stakeholders before any operational use.

## Links

- Demo: <UNLISTED_YOUTUBE_URL>
- Pitch deck: <PITCH_DECK_URL>
- Project site: <GITHUB_PAGES_URL>
- Team: <TEAM_MEMBER_NAMES>

## Attribution

Eyewall's present prepared inputs draw on NASA SRTM / USGS elevation data, OpenStreetMap contributors, and NOAA IBTrACS historical cyclone data. See [DATA_SOURCES.md](DATA_SOURCES.md) for use, processing, attribution, licensing notes, and limitations.

## License

This repository is released under the [MIT License](LICENSE).
