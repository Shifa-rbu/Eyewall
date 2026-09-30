import pytest

from server.exposure import compute_exposure, cell_at, haversine_km, meta


@pytest.mark.parametrize(("surge", "area", "medical", "shelter", "power", "road", "grid", "flags"), [
    (0.0, 0, 0, 0, 1, 2, 0, 7),
    (3.0, 127, 4, 1, 6, 14, 11, 4),
    (5.0, 493, 8, 6, 10, 63, 55, 0),
])
def test_reference_exposure(surge, area, medical, shelter, power, road, grid, flags):
    result = compute_exposure(surge)
    assert result["areaKm2"] == pytest.approx(area, abs=max(1, area * .02))
    assert (result["medical"], result["shelter"], result["power"]) == (medical, shelter, power)
    assert result["roadKm"] == pytest.approx(road, abs=max(1, road * .02))
    assert result["gridKm"] == pytest.approx(grid, abs=max(1, grid * .02))
    assert len(result["flagged"]) == flags


def test_cell_at_bounds_and_haversine():
    assert cell_at(meta["south"] + 0.0001, meta["west"] + 0.0001) >= 0
    assert cell_at(meta["north"] + 0.0001, meta["west"]) == -1
    assert haversine_km((0, 0), (0, 1)) == pytest.approx(111.19, abs=.2)


def test_area_monotonic():
    areas = [compute_exposure(level)["areaKm2"] for level in (0, 3, 5)]
    assert areas == sorted(areas)
