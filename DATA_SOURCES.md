# Data sources

This document distinguishes sources used by the current reproducible pipeline from sources proposed for later evidence or MVP work. Planned sources are not currently integrated.

## Used now

### NASA SRTM / USGS

- **Use:** `prep.py` reads a local compressed SRTM HGT tile, crops it to the configured Kendrapara–Paradip bounding box, subsamples it, and writes `data/elev.i16` plus `data/grid.json`.
- **Processing status:** Processed elevation output is committed under `data/`. The source input is expected locally at `raw/elev.hgt.gz` and is ignored by Git.
- **Attribution:** NASA Shuttle Radar Topography Mission (SRTM), distributed through the U.S. Geological Survey (USGS).
- **License / access note:** SRTM elevation data distributed by USGS are U.S. Government data and are generally public domain. Users should verify the terms applicable to their downloaded distribution and preserve source attribution.
- **Limitations:** This is terrain elevation, not a water-level forecast, hydrodynamic model, flood-depth map, or validation of local drainage, embankments, buildings, or protective infrastructure.

### OpenStreetMap contributors

- **Use:** `prep.py` reads a local OSM XML extract and produces selected medical, shelter-capacity proxy, and power points; selected road lines; and transmission-line lines in `data/assets.json`.
- **Processing status:** Processed feature output is committed under `data/`. The source input is expected locally at `raw/osm.xml` and is ignored by Git.
- **Attribution:** © OpenStreetMap contributors.
- **License:** Open Database License (ODbL) 1.0; see the OpenStreetMap copyright and license information for attribution and share-alike requirements.
- **Limitations:** OSM is a dated public extract and not a complete infrastructure registry. It may omit, misclassify, duplicate, or inaccurately locate facilities, roads, substations, or transmission lines. The pipeline's shelter-capacity proxy is not a verified list of operational shelters or their capacity.

### NOAA IBTrACS

- **Use:** `prep.py` reads `raw/ibtracs.csv`, filters a named storm set, and writes historical track points and available wind fields to `data/tracks.json`.
- **Processing status:** Processed historical tracks are committed under `data/`. The source input is expected locally at `raw/ibtracs.csv` and is ignored by Git.
- **Attribution:** NOAA National Centers for Environmental Information, International Best Track Archive for Climate Stewardship (IBTrACS).
- **License / access note:** NOAA materials are generally public-domain U.S. Government works, but IBTrACS incorporates international-agency inputs. Consult the current NOAA/IBTrACS documentation and terms for the specific download and retain the dataset citation.
- **Limitations:** IBTrACS is retrospective historical track data, not an official warning, live feed, forecast, observed local impact record, or verification of damage or outages.

## Planned or evidence-stage

### Open-Meteo

Planned for labelled forecast context. It is not currently integrated, and Eyewall will not describe it as observations. Any future use must follow Open-Meteo's then-current attribution and licensing terms.

### Sentinel-1 through Google Earth Engine

The repository includes a Google Earth Engine Code Editor script for historical Sentinel-1 evidence around Cyclone Fani. It is not a live feed and does not export imagery, credentials, or processed Sentinel-1 outputs from this repository. Any future use must follow Copernicus Sentinel data terms and Google Earth Engine terms.

### Gemini

Planned for bounded advisory drafting and interpretation for human review. Gemini is not currently integrated. Any future integration must use an appropriate API configuration, protect credentials, and ensure a human-review queue; no external message is sent automatically.

### Leaflet

Leaflet is a possible future map-rendering dependency only. It is not currently present in this repository or integrated into the project.
