"""Evacuation accessibility tests.

The committed road extract is a *selected* subset, so the graph is fragmented
before any water arrives. These tests therefore assert on the **change** from the
unflooded baseline, which is the only quantity that means anything here.
"""
import pytest

from server import accessibility
from server.exposure import assets, flood_mask, meta


def _run(surge: float) -> dict:
    return accessibility.analyse(assets["roads"], flood_mask(surge), meta)


@pytest.fixture(scope="module")
def at_zero():
    return _run(0.0)


@pytest.fixture(scope="module")
def at_three_five():
    return _run(3.5)


class TestBaseline:
    """At zero surge nothing should be reported as newly isolated."""

    def test_no_road_is_stranded_without_flooding(self, at_zero):
        assert at_zero["newlyIsolatedRoadKm"] == pytest.approx(0.0, abs=1.0)

    def test_impassable_road_is_only_sea_level_cells(self, at_zero):
        # Tidal channels at or below sea level are genuinely impassable, but this
        # must stay small: a large number here would mean the mask, not the
        # scenario, is doing the work.
        assert at_zero["impassableRoadKm"] < 12.0

    def test_baseline_component_count_is_reported(self, at_zero):
        assert at_zero["componentsBaseline"] == at_zero["components"]


class TestMonotonicity:
    """More water cannot restore a road. These are the invariants that matter."""

    def test_impassable_length_increases_with_surge(self):
        lengths = [_run(s)["impassableRoadKm"] for s in (0.0, 2.0, 3.0, 3.5, 5.0)]
        assert lengths == sorted(lengths), lengths

    def test_isolated_facility_count_increases_with_surge(self):
        counts = [len(_run(s)["isolatedFacilities"]) for s in (0.0, 2.0, 3.0, 3.5, 5.0)]
        assert counts == sorted(counts), counts

    def test_components_never_decrease_with_surge(self):
        comps = [_run(s)["components"] for s in (0.0, 2.0, 3.5, 5.0)]
        assert comps == sorted(comps), comps

    def test_open_plus_impassable_equals_total(self, at_three_five):
        total = at_three_five["openRoadKm"] + at_three_five["impassableRoadKm"]
        assert total == pytest.approx(accessibility_total(), rel=0.02)


def accessibility_total() -> float:
    _adj, edges = accessibility.build_graph(assets["roads"])
    return sum(length for _a, _b, _n, length in edges)


class TestReportingHonesty:
    """The module must not imply precision or population it does not have."""

    def test_no_population_figure_is_ever_reported(self, at_three_five):
        """Check the data fields only.

        The notes legitimately mention population to say that no population layer
        exists, which is the disclosure we want. What must never appear is a
        population *number* presented as a measurement.
        """
        payload = {k: v for k, v in at_three_five.items() if k != "notes"}
        blob = str(payload).lower()
        for forbidden in ("people", "population", "persons", "households"):
            assert forbidden not in blob, f"{forbidden!r} appears in accessibility data"

    def test_isolation_is_labelled_as_a_change_from_baseline(self, at_three_five):
        joined = " ".join(at_three_five["notes"]).lower()
        assert "baseline" in joined
        assert "not routing" in joined

    def test_model_string_does_not_claim_routing(self, at_three_five):
        assert "not routing" in at_three_five["model"]

    def test_off_network_baseline_is_surfaced_not_hidden(self, at_three_five):
        # The partial road extract leaves facilities off-network before flooding.
        # That limitation must be visible, not silently folded into the hazard count.
        assert "facilitiesOffNetworkBaseline" in at_three_five

    def test_isolated_facilities_carry_a_reason(self, at_three_five):
        for item in at_three_five["isolatedFacilities"]:
            assert item["reason"] in {
                "inside the scenario footprint",
                "no dry road route to the main network",
            }


class TestChokepoints:
    def test_chokepoints_are_returned_and_ranked(self, at_three_five):
        chokes = at_three_five["chokepoints"]
        assert chokes, "expected at least one articulation edge"
        counts = [c["isolatesNodes"] for c in chokes]
        assert counts == sorted(counts, reverse=True)

    def test_chokepoint_shape_is_stable_for_the_api(self, at_three_five):
        for c in at_three_five["chokepoints"]:
            assert set(c) == {"from", "to", "lengthKm", "isolatesNodes"}
            assert len(c["from"]) == 2 and len(c["to"]) == 2


class TestGraphHelpers:
    def test_nodes_collapse_digitisation_jitter(self):
        assert accessibility._key(20.1234567, 86.7654321) == accessibility._key(
            20.1234564, 86.7654329
        )

    def test_distinct_junctions_stay_distinct(self):
        assert accessibility._key(20.1, 86.7) != accessibility._key(20.2, 86.8)

    def test_haversine_matches_a_known_distance(self):
        # ~0.1 degree of latitude is ~11.1 km anywhere.
        d = accessibility.haversine_km((20.0, 86.0), (20.1, 86.0))
        assert d == pytest.approx(11.1, abs=0.2)

    def test_empty_road_list_does_not_crash(self):
        result = accessibility.analyse([], flood_mask(3.0), meta)
        assert result["impassableRoadKm"] == 0.0
        assert result["isolatedFacilities"] == []

    def test_fully_flooded_grid_is_handled(self):
        """Every cell wet must not crash or hang.

        Roads outside the analysis window are legitimately unaffected by a mask
        that only covers the grid, so a small remainder of open road is correct
        here rather than a bug.
        """

        class AllWet:
            def __getitem__(self, _i):
                return 1

        result = accessibility.analyse(assets["roads"], AllWet(), meta)
        total = accessibility_total()
        assert result["impassableRoadKm"] > 0
        # The overwhelming majority must be impassable; only out-of-window road survives.
        assert result["openRoadKm"] < total * 0.2
        assert isinstance(result["isolatedFacilities"], list)
