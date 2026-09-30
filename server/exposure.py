"""Canonical screening-level sea-connected bathtub exposure calculation."""
from array import array
from datetime import datetime, timezone
import json
import math

from .config import DATA

meta = json.loads((DATA / "grid.json").read_text(encoding="utf-8"))
assets = json.loads((DATA / "assets.json").read_text(encoding="utf-8"))
raw = (DATA / "elev.i16").read_bytes()
elev = array("h")
elev.frombytes(raw)
if __import__("sys").byteorder != "little":
    elev.byteswap()


def cell_at(lat, lon):
    c = math.floor((lon-meta["west"])/(meta["east"]-meta["west"])*meta["cols"])
    r = math.floor((meta["north"]-lat)/(meta["north"]-meta["south"])*meta["rows"])
    return r*meta["cols"]+c if 0 <= r < meta["rows"] and 0 <= c < meta["cols"] else -1


def haversine_km(a, b):
    dlat, dlon = math.radians(b[0]-a[0]), math.radians(b[1]-a[1])
    h = math.sin(dlat/2)**2 + math.cos(math.radians(a[0]))*math.cos(math.radians(b[0]))*math.sin(dlon/2)**2
    return 2*6371*math.asin(math.sqrt(h))


def compute_exposure(surge):
    rows, cols = meta["rows"], meta["cols"]
    mask = bytearray(rows*cols)
    stack = []
    for i, height in enumerate(elev):
        if height <= 0:
            mask[i] = 1
            stack.append(i)
    while stack:
        i = stack.pop()
        c = i % cols
        for j in (i-cols, i+cols, i-1, i+1):
            if j < 0 or j >= len(mask) or (j == i-1 and c == 0) or (j == i+1 and c == cols-1):
                continue
            if not mask[j] and elev[j] < surge:
                mask[j] = 1
                stack.append(j)
    cell_area = (111320*(meta["north"]-meta["south"])/rows) * (111320*math.cos(math.radians((meta["north"]+meta["south"])/2))*(meta["east"]-meta["west"])/cols) / 1e6
    area = sum(1 for i, wet in enumerate(mask) if wet and elev[i] > 0) * cell_area
    inundated = []
    counts = {"hospital": 0, "shelter": 0, "power": 0}
    for p in assets["points"]:
        i = cell_at(p["lat"], p["lon"])
        if i >= 0 and mask[i]:
            counts[p["kind"]] += 1
            inundated.append({"name": p["name"], "kind": p["kind"]})
    wet_power = [(p["lat"], p["lon"]) for p in assets["points"] if p["kind"] == "power"
                 and (lambda idx: idx >= 0 and mask[idx])(cell_at(p["lat"], p["lon"]))]
    wet_buckets = {}
    for line in assets["grid"]:
        for v in line["path"]:
            idx = cell_at(*v)
            if idx >= 0 and mask[idx]:
                wet_buckets.setdefault((math.floor(v[0] * 100), math.floor(v[1] * 100)), []).append(v)
    flagged = []
    for p in assets["points"]:
        if p["kind"] == "power":
            continue
        idx = cell_at(p["lat"], p["lon"])
        if idx >= 0 and mask[idx]:
            continue
        nearby = list(wet_power)
        lat_bucket, lon_bucket = math.floor(p["lat"] * 100), math.floor(p["lon"] * 100)
        for lat_offset in range(-3, 4):
            for lon_offset in range(-3, 4):
                nearby.extend(wet_buckets.get((lat_bucket+lat_offset, lon_bucket+lon_offset), ()))
        if any(haversine_km((p["lat"],p["lon"]), v) < 2 for v in nearby):
            flagged.append({"name":p["name"], "reason":"power-dependency"})
    def line_km(lines):
        total = 0.0
        for line in lines:
            path = line["path"]
            for a, b in zip(path, path[1:]):
                i, j = cell_at(*a), cell_at(*b)
                if i >= 0 and j >= 0 and mask[i] and mask[j]:
                    total += haversine_km(a,b)
        return total
    return {"surge": surge, "areaKm2": round(area, 2), "medical": counts["hospital"],
            "shelter": counts["shelter"], "power": counts["power"],
            "roadKm": round(line_km(assets["roads"]), 2), "gridKm": round(line_km(assets["grid"]), 2),
            "flagged": flagged, "inundated": inundated,
            "model": "sea-connected bathtub screening (not hydrodynamic)",
            "computedAt": datetime.now(timezone.utc).isoformat()}
