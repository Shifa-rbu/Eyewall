"""Evacuation accessibility: which roads stop working, and what that isolates.

The problem statement's stated purpose is pre-landfall evacuation planning, not
inundation mapping. Extent alone is not a decision; the decision is *which routes
survive and what becomes unreachable*.

Method, deliberately simple and inspectable:

1. Build a graph from the road network already in `data/assets.json`. Nodes are
   road vertices; edges are consecutive vertices along each way.
2. Remove every edge that the flood mask has broken. An edge is impassable when
   either endpoint is inundated, because a road submerged at one end cannot be
   driven.
3. Take the largest surviving component as the connected network and report what
   is no longer joined to it.
4. Find articulation edges (bridges) whose loss would split a component further.
   These are the chokepoints a district needs to keep clear.

What this module does **not** do is estimate travel time or population. We have no
travel-time surface and the exposure payload carries no population layer, so a
person count here would be invented. Counts are reported as facilities and road
kilometres, which are measured. When a population layer lands, this module gains a
`populations` argument rather than a guess.
"""
from __future__ import annotations

import math
from itertools import pairwise

# Nodes closer than this are treated as the same junction. At ~0.4 degree window
# a 1e-5 step is roughly a metre; 5e-5 collapses digitisation jitter without
# merging genuinely distinct junctions.
NODE_PRECISION = 5

_MODEL = "road graph minus flood mask (connectivity screening, not routing)"


def _key(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat, NODE_PRECISION), round(lon, NODE_PRECISION))


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    d_lat = (b[0] - a[0]) * math.pi / 180
    d_lon = (b[1] - a[1]) * math.pi / 180
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(a[0] * math.pi / 180) * math.cos(b[0] * math.pi / 180) * math.sin(d_lon / 2) ** 2
    )
    return 2 * 6371 * math.asin(math.sqrt(h))


class _DisjointSet:
    """Union-find over road nodes, used for connected-component labelling."""

    def __init__(self) -> None:
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def build_graph(roads: list[dict]) -> tuple[dict, list[tuple]]:
    """Return (adjacency, edge list) for the road network.

    Parallel edges between the same node pair are preserved in the edge list but
    collapsed in the adjacency, which is what connectivity actually cares about.
    """
    adjacency: dict[tuple, set] = {}
    edges: list[tuple] = []

    for road in roads:
        path = road.get("path") or []
        for a, b in pairwise(path):
            ka, kb = _key(*a), _key(*b)
            if ka == kb:
                continue
            adjacency.setdefault(ka, set()).add(kb)
            adjacency.setdefault(kb, set()).add(ka)
            edges.append((ka, kb, road.get("name") or "unnamed", haversine_km(a, b)))

    return adjacency, edges


def _is_impassable(a, b, mask, meta) -> bool:
    """True when either endpoint of the edge is under water."""
    from .exposure import cell_at

    for node in (a, b):
        idx = cell_at(node[0], node[1])
        if idx >= 0 and mask[idx]:
            return True
    return False


def _bridges(adjacency: dict) -> list[tuple]:
    """Articulation edges: removing one splits its component in two.

    Iterative Tarjan bridge-finding, so a long road chain cannot blow the
    recursion limit.
    """
    index_of: dict = {}
    low: dict = {}
    found: list[tuple] = []
    counter = 0

    for root, neighbours in adjacency.items():
        if root in index_of:
            continue
        stack = [(root, None, iter(sorted(neighbours, key=repr)))]
        index_of[root] = low[root] = counter
        counter += 1

        while stack:
            node, parent, it = stack[-1]
            advanced = False

            for nxt in it:
                if nxt == parent:
                    continue
                if nxt in index_of:
                    low[node] = min(low[node], index_of[nxt])
                    continue
                index_of[nxt] = low[nxt] = counter
                counter += 1
                stack.append((nxt, node, iter(sorted(adjacency[nxt], key=repr))))
                advanced = True
                break
            if advanced:
                continue

            stack.pop()
            if parent is not None:
                low[parent] = min(low[parent], low[node])
                # A child whose low value never reaches the parent means the edge
                # is the only way back up.
                if low[node] > index_of[parent]:
                    found.append((parent, node))

    return found


def _components(adjacency: dict) -> tuple[dict, dict]:
    """Label connected components. Returns (groups, node_to_root)."""
    ds = _DisjointSet()
    for node, neighbours in adjacency.items():
        for other in neighbours:
            ds.union(node, other)
    groups: dict = {}
    for node in adjacency:
        groups.setdefault(ds.find(node), set()).add(node)
    return groups, {node: ds.find(node) for node in adjacency}


def _open_graph(roads: list[dict], mask, meta) -> tuple[dict, float, float]:
    """Road network with flooded edges removed. Returns (adjacency, impassable_km, total_km)."""
    _all_adj, edges = build_graph(roads)
    open_adjacency: dict = {}
    impassable_km = 0.0
    total_km = 0.0
    for a, b, _name, length in edges:
        total_km += length
        if _is_impassable(a, b, mask, meta):
            impassable_km += length
            continue
        open_adjacency.setdefault(a, set()).add(b)
        open_adjacency.setdefault(b, set()).add(a)
    return open_adjacency, impassable_km, total_km


def analyse(roads: list[dict], mask, meta, baseline_mask=None) -> dict:
    """What the flood breaks in the road network.

    Connectivity is reported as a **change from the unflooded baseline**, not as an
    absolute. The committed `assets.json` holds a *selected* road subset, so the
    graph is already fragmented before any water arrives; an absolute count would
    mostly measure that data limitation rather than the hazard.

    With no population layer, counts are facilities and road kilometres. A person
    figure here would be invented, so none is reported.
    """
    from .exposure import cell_at

    adjacency, impassable_km, total_km = _open_graph(roads, mask, meta)

    if baseline_mask is None:
        from .exposure import flood_mask

        baseline_mask = flood_mask(0.0)
    base_adjacency, _base_imp, _ = _open_graph(roads, baseline_mask, meta)

    if not adjacency:
        return {
            "model": _MODEL,
            "impassableRoadKm": round(impassable_km, 2),
            "openRoadKm": 0.0,
            "components": 0,
            "componentsBaseline": len(_components(base_adjacency)[0]),
            "newlyIsolatedRoadKm": 0.0,
            "chokepoints": [],
            "isolatedFacilities": [],
            "facilitiesTotal": len(_facility_points()),
            "notes": ["every mapped road segment is inside the scenario footprint"],
        }

    groups, root_of = _components(adjacency)
    base_groups, base_root_of = _components(base_adjacency)

    # The reference network is the largest component: by definition the part that
    # is still traversable as one piece.
    main_root = max(groups, key=lambda r: len(groups[r]))
    base_main_root = max(base_groups, key=lambda r: len(base_groups[r])) if base_groups else None

    # Road that flooding moved from connected to stranded.
    newly_isolated_km = 0.0
    for road in roads:
        for a, b in pairwise(road.get("path") or []):
            ka, kb = _key(*a), _key(*b)
            if root_of.get(ka) == main_root and root_of.get(kb) == main_root:
                continue  # still on the main network
            if _is_impassable(ka, kb, mask, meta):
                continue  # counted as impassable, not as stranded
            was_connected = (
                base_main_root is not None
                and base_root_of.get(ka) == base_main_root
                and base_root_of.get(kb) == base_main_root
            )
            if was_connected or ka not in base_root_of or kb not in base_root_of:
                newly_isolated_km += haversine_km(a, b)

    chokepoints = []
    for a, b in _bridges(adjacency):
        far_side = len(groups.get(root_of.get(b), ()))
        if far_side >= 2:
            chokepoints.append(
                {
                    "from": [a[0], a[1]],
                    "to": [b[0], b[1]],
                    "lengthKm": round(haversine_km(a, b), 3),
                    "isolatesNodes": far_side,
                }
            )
    chokepoints.sort(key=lambda c: c["isolatesNodes"], reverse=True)

    # Facilities, measured. "Newly isolated" means connected before the flood and
    # not after; that is the hazard signal. Already-off-network facilities are
    # reported separately so the data limitation stays visible.
    newly_isolated: list[dict] = []
    already_off_network = 0
    for point in _facility_points():
        idx = cell_at(point["lat"], point["lon"])
        in_flood = idx >= 0 and bool(mask[idx])

        node = _nearest_node(adjacency, point["lat"], point["lon"]) or _nearest_node(
            base_adjacency, point["lat"], point["lon"]
        )
        if node is None:
            already_off_network += 1
            continue

        on_main_now = root_of.get(node) == main_root
        on_main_before = (
            base_main_root is not None and base_root_of.get(node) == base_main_root
        )

        if in_flood:
            newly_isolated.append(
                {"name": point["name"], "kind": point["kind"],
                 "reason": "inside the scenario footprint"}
            )
        elif on_main_before and not on_main_now:
            newly_isolated.append(
                {"name": point["name"], "kind": point["kind"],
                 "reason": "no dry road route to the main network"}
            )
        elif not on_main_before:
            already_off_network += 1

    return {
        "model": _MODEL,
        "impassableRoadKm": round(impassable_km, 2),
        "openRoadKm": round(total_km - impassable_km, 2),
        "components": len(groups),
        "componentsBaseline": len(base_groups),
        "newlyIsolatedRoadKm": round(newly_isolated_km, 2),
        "chokepoints": chokepoints[:10],
        "isolatedFacilities": newly_isolated,
        "facilitiesTotal": len(_facility_points()),
        "facilitiesOffNetworkBaseline": already_off_network,
        "notes": [
            (
                "Connectivity screening, not routing: no travel times and no road "
                "capacity are modelled."
            ),
            (
                "Connectivity is reported as a change from the unflooded baseline "
                "because the committed road extract is a selected subset, not the "
                "full network."
            ),
            (
                "No population layer is present, so counts are facilities and road "
                "kilometres only. A person figure here would be invented."
            ),
        ],
    }


_FACILITIES: list[dict] | None = None


def _facility_points() -> list[dict]:
    """Facilities from the processed asset file, cached after first read."""
    global _FACILITIES
    if _FACILITIES is None:
        import json
        from pathlib import Path

        from .config import ROOT

        data = json.loads((Path(ROOT) / "data" / "assets.json").read_text(encoding="utf-8"))
        _FACILITIES = data.get("points", [])
    return _FACILITIES


def _nearest_node(adjacency: dict, lat: float, lon: float, max_km: float = 3.0):
    """Closest road node to a facility, or None when the facility is off-network."""
    best, best_d = None, max_km
    for node in adjacency:
        d = haversine_km((lat, lon), node)
        if d < best_d:
            best, best_d = node, d
    return best


def _grid_meta() -> dict:
    """Grid metadata, read from the same file the exposure engine uses."""
    from .exposure import meta

    return meta

_ROADS: list[dict] | None = None


def _road_paths() -> list[dict]:
    """Road geometries from the processed asset file, cached after first read."""
    global _ROADS
    if _ROADS is None:
        import json
        from pathlib import Path

        from .config import ROOT

        data = json.loads((Path(ROOT) / "data" / "assets.json").read_text(encoding="utf-8"))
        _ROADS = data.get("roads", [])
    return _ROADS


def screen(surge: float) -> dict:
    """Public entry point: run the whole accessibility screen for a surge height.

    Callers pass a surge in metres and get the report. Loading the road set and
    deriving the inundation mask is deliberately kept inside this module so the
    API layer cannot accidentally disagree with the exposure engine about which
    cells are wet.
    """
    from .exposure import flood_mask

    return analyse(_road_paths(), flood_mask(surge), _grid_meta())
