# prep.py — run once:  python3 prep.py
# Standard library only — nothing to install.
import array
import csv
import gzip
import json
import math
import xml.etree.ElementTree as ET

# ---- your choices (config, not results — the only things you "hardcode") ----
TILE_LAT, TILE_LON = 21, 86                 # top-left corner of tile N20E086
S, N, W, E = 20.05, 20.40, 86.35, 86.75     # Kendrapara-Paradip delta, Odisha
STEP = 2                                    # keep every 2nd pixel (~60 m); use 1 for 30 m
STORMS = {"FANI", "AMPHAN", "YAAS", "REMAL", "PHAILIN", "HUDHUD", "MOCHA", "BIPARJOY"}

# ---- 1) elevation: crop the real SRTM tile to your window ----
with gzip.open("raw/elev.hgt.gz") as _fh:
    raw = _fh.read()
n = math.isqrt(len(raw) // 2)               # 3601 -> ~30 m resolution
a = array.array("h")
a.frombytes(raw)                            # .hgt files are big-endian
a.byteswap()

r0, r1 = int((TILE_LAT - N) * (n - 1)), int((TILE_LAT - S) * (n - 1))
c0, c1 = int((W - TILE_LON) * (n - 1)), int((E - TILE_LON) * (n - 1))
grid = array.array("h")
for r in range(r0, r1 + 1, STEP):
    base = r * n
    for c in range(c0, c1 + 1, STEP):
        v = a[base + c]
        grid.append(0 if v < -100 else v)   # -9999 means "no data" -> treat as sea
rows, cols = (r1 - r0) // STEP + 1, (c1 - c0) // STEP + 1
with open("data/elev.i16", "wb") as _fh:     # little-endian on normal laptops
    grid.tofile(_fh)
with open("data/grid.json", "w") as _fh:
    json.dump({"south": S, "north": N, "west": W, "east": E,
               "rows": rows, "cols": cols}, _fh)
print("grid:", rows, "x", cols)

# ---- 2) infrastructure from the real OSM xml ----
# kinds: hospital = medical; shelter = evacuation-shelter capacity (Odisha uses schools/
# community halls as cyclone shelter-capacity proxies; tagged shelter-capacity proxies/assembly points included if present);
# power = grid nodes (substations are often mapped as areas -> we take their centre);
# grid = transmission lines (power=line), drawn as their own layer.
pts, roads, gridlines, nodes = [], [], [], {}
for _ev, el in ET.iterparse("raw/osm.xml", events=("end",)):
    if el.tag == "node":
        nodes[el.get("id")] = (el.get("lat"), el.get("lon"))
        t = {x.get("k"): x.get("v") for x in el.findall("tag")}
        kind = None
        if t.get("amenity") in ("hospital", "clinic", "doctors") or t.get("emergency") == "ambulance_station":
            kind = "hospital"
        elif (t.get("amenity") in ("school", "college")
              or t.get("amenity") in ("shelter", "community_centre")
              or t.get("emergency") == "assembly_point"):
            kind = "shelter"
        elif t.get("power") in ("substation", "plant", "terminal"):
            kind = "power"
        if kind:
            pts.append({"kind": kind, "name": t.get("name", "unnamed"),
                        "lat": float(el.get("lat")), "lon": float(el.get("lon"))})
        el.clear()                      # clear AFTER reading, keeps memory small
    elif el.tag == "way":
        t = {x.get("k"): x.get("v") for x in el.findall("tag")}
        if t.get("highway") in ("trunk", "primary", "secondary"):
            cs = [nodes[x.get("ref")] for x in el.findall("nd") if x.get("ref") in nodes]
            if len(cs) > 1:
                roads.append({"name": t.get("name", t.get("highway")),
                              "path": [[float(la), float(lo)] for la, lo in cs]})
        elif t.get("power") in ("line", "minor_line"):
            cs = [nodes[x.get("ref")] for x in el.findall("nd") if x.get("ref") in nodes]
            if len(cs) > 1:
                gridlines.append({"name": t.get("name", "transmission line"),
                                  "path": [[float(la), float(lo)] for la, lo in cs]})
        elif t.get("power") in ("substation", "plant", "terminal"):
            cs = [nodes[x.get("ref")] for x in el.findall("nd") if x.get("ref") in nodes]
            if cs:  # area-mapped substations -> use their centre point
                pts.append({"kind": "power", "name": t.get("name", "unnamed"),
                            "lat": sum(float(p[0]) for p in cs) / len(cs),
                            "lon": sum(float(p[1]) for p in cs) / len(cs)})
        el.clear()
    elif el.tag == "relation":
        el.clear()
with open("data/assets.json", "w") as _fh:
    json.dump({"points": pts, "roads": roads, "grid": gridlines}, _fh)
print("assets:", len(pts), "points,", len(roads), "roads,", len(gridlines), "transmission lines")

# ---- 3) real cyclone tracks (NOAA IBTrACS; the file has TWO header rows) ----
storms = {}
with open("raw/ibtracs.csv", encoding="utf-8") as _fh:
    rows_in = list(csv.DictReader(_fh))
for r in rows_in:
    name = (r.get("NAME") or "").strip()
    if name not in STORMS:
        continue
    try:
        lat, lon = float(r["LAT"]), float(r["LON"])
    except (ValueError, KeyError):
        continue                        # this skips the units header row
    try:
        kt = float(r["USA_WIND"] or r["WMO_WIND"])
    except (ValueError, KeyError):
        kt = None
    storms.setdefault(name, []).append(
        {"t": r["ISO_TIME"], "lat": lat, "lon": lon, "kt": kt})
out = [{"name": k, "pts": v} for k, v in storms.items()]
with open("data/tracks.json", "w") as _fh:
    json.dump(out, _fh)
print("storms:", sorted(storms))
