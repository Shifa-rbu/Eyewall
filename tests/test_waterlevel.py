"""Total water level tests.

The numbers asserted here are physically checkable rules of thumb, which is the
point: a decomposition that cannot be spot-checked by hand is not explainable.
"""
import math

import pytest

from server.waterlevel import (
    M2_PERIOD_HOURS,
    STD_PRESSURE_HPA,
    WaterLevelInput,
    compose,
    from_landfall_timing,
    inverse_barometer,
    tide_phase,
    wave_setup,
    wind_setup,
)


class TestInverseBarometer:
    def test_standard_pressure_lifts_nothing(self):
        assert inverse_barometer(STD_PRESSURE_HPA) == pytest.approx(0.0)

    def test_one_hectopascal_is_about_one_centimetre(self):
        """The rule of thumb every forecaster carries in their head."""
        assert inverse_barometer(STD_PRESSURE_HPA - 1) == pytest.approx(0.0099, abs=0.0005)

    def test_a_deep_cyclone_lifts_about_three_quarters_of_a_metre(self):
        # 940 hPa is a severe cyclone. 1013.25 - 940 = 73.25 hPa -> ~0.73 m.
        assert inverse_barometer(940) == pytest.approx(0.729, abs=0.005)

    def test_high_pressure_pushes_water_down(self):
        assert inverse_barometer(1030) < 0

    def test_response_is_linear_in_pressure(self):
        """10 hPa lower means 10 cm more lift, and lower pressure lifts upward."""
        a, b = inverse_barometer(1000), inverse_barometer(990)
        assert b > a
        assert (b - a) == pytest.approx(10 * inverse_barometer(STD_PRESSURE_HPA - 1))


class TestWindSetup:
    def test_no_wind_no_setup(self):
        assert wind_setup(0, 50, 20) == 0.0

    def test_deeper_water_means_less_setup(self):
        assert wind_setup(30, 50, 40) < wind_setup(30, 50, 20)

    def test_longer_fetch_means_more_setup(self):
        assert wind_setup(30, 100, 20) > wind_setup(30, 50, 20)

    def test_quadratic_in_wind_speed(self):
        """Stress goes as U^2, so doubling the wind quadruples the setup."""
        assert wind_setup(40, 50, 20) == pytest.approx(4 * wind_setup(20, 50, 20), rel=1e-9)

    def test_magnitude_is_plausible_for_a_cyclone(self):
        # A 30 m/s wind over 50 km of 20 m water: metres, not centimetres or tens.
        assert 0.1 < wind_setup(30, 50, 20) < 3.0

    def test_degenerate_inputs_return_zero_rather_than_dividing_by_zero(self):
        assert wind_setup(30, 0, 20) == 0.0
        assert wind_setup(30, 50, 0) == 0.0


class TestWaveSetup:
    def test_no_wind_no_waves(self):
        assert wave_setup(0, 50, 0.02) == 0.0

    def test_steeper_beach_gives_more_setup(self):
        assert wave_setup(30, 50, 0.05) >= wave_setup(30, 50, 0.01)

    def test_grows_with_fetch(self):
        assert wave_setup(30, 100, 0.02) > wave_setup(30, 20, 0.02)

    def test_degenerate_slope_returns_zero(self):
        assert wave_setup(30, 50, 0.0) == 0.0


class TestTidePhase:
    def test_peak_at_landfall_by_default(self):
        """The default is the conservative case: landfall at high water."""
        assert tide_phase(0.0, amplitude_m=1.0) == pytest.approx(1.0)

    def test_half_a_period_later_is_low_water(self):
        assert tide_phase(M2_PERIOD_HOURS / 2, amplitude_m=1.0) == pytest.approx(-1.0)

    def test_full_period_returns_to_the_same_phase(self):
        a = tide_phase(0.0)
        b = tide_phase(M2_PERIOD_HOURS)
        assert a == pytest.approx(b)

    def test_stays_within_the_amplitude(self):
        for hour in range(25):
            assert abs(tide_phase(float(hour), amplitude_m=2.0)) <= 2.0 + 1e-9


class TestCompose:
    def test_terms_add_up_to_the_total(self):
        result = compose(WaterLevelInput(surge_m=3.0, tide_m=0.5, pressure_hpa=970, wind_speed_ms=25))
        total = sum(result["components"].values())
        assert result["totalM"] == pytest.approx(total, abs=0.002)

    def test_each_component_is_reported_separately(self):
        result = compose(WaterLevelInput(surge_m=3.0, pressure_hpa=970))
        assert set(result["components"]) == {
            "surge", "tide", "pressureSetup", "windSetup", "waveSetup"
        }

    def test_surge_is_named_dominant_when_it_is(self):
        result = compose(WaterLevelInput(surge_m=5.0, wind_speed_ms=5))
        assert result["dominantTerm"] == "surge"

    def test_dominant_term_switches_when_a_component_overtakes(self):
        """A weak surge with a spring tide should not be reported as surge-driven."""
        result = compose(WaterLevelInput(surge_m=0.2, tide_m=3.0))
        assert result["dominantTerm"] == "tide"

    def test_never_claims_to_be_a_hydrodynamic_model(self):
        result = compose(WaterLevelInput(surge_m=3.0))
        assert "not a coupled" in result["model"]
        assert any("independent" in note for note in result["limitations"])

    def test_points_at_the_warning_authority(self):
        result = compose(WaterLevelInput(surge_m=3.0))
        assert "INCOIS" in result["authority"] and "IMD" in result["authority"]

    def test_zero_scenario_is_exactly_zero(self):
        result = compose(WaterLevelInput(surge_m=0.0))
        assert result["totalM"] == 0.0


class TestLandfallTiming:
    def test_high_water_landfall_is_worse_than_low_water(self):
        """The argument for the whole module: timing changes the answer."""
        high = from_landfall_timing(3.0, 0.0, tide_amplitude_m=1.2)
        low = from_landfall_timing(3.0, M2_PERIOD_HOURS / 2, tide_amplitude_m=1.2)
        assert high["totalM"] > low["totalM"]
        assert high["totalM"] - low["totalM"] == pytest.approx(2.4, abs=0.05)

    def test_reports_the_tide_approximation_used(self):
        result = from_landfall_timing(3.0, 1.0)
        assert "M2" in result["landfall"]["tideApproximation"]

    def test_otherwise_identical_storm_total_varies_with_timing(self):
        totals = {
            from_landfall_timing(3.0, h, tide_amplitude_m=1.2)["totalM"]
            for h in (0.0, 3.105, 6.21)
        }
        assert len(totals) == 3

    def test_pressure_and_wind_are_optional(self):
        result = from_landfall_timing(3.0, 0.0)
        assert result["totalM"] > 3.0   # tide alone lifts it
        assert result["components"]["pressureSetup"] == 0.0

    def test_total_is_finite_across_boundary_inputs(self):
        for hours in (-48.0, 0.0, M2_PERIOD_HOURS, 240.0):
            assert math.isfinite(from_landfall_timing(3.0, hours)["totalM"])
