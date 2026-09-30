"""Total water level: what a storm-surge height is actually made of.

The console previously exposed a bare "surge" slider, which invites the first
question any physical oceanographer asks: *what is that number made of?* Total
water level at the coast is the sum of independent contributions, and separating
them is what makes a scenario defensible and adjustable.

    total = still-water surge + astronomical tide + pressure setup + wave setup

Each term here is a transparent formula over user-supplied inputs, not a model.
The point is explainability at T-48h, not replacing INCOIS's ADCIRC forecast.

What this module deliberately does **not** do:

* It does not fetch live tide predictions or observed pressure. Those need a tide
  station and a barometer feed; inventing them would be worse than omitting them.
* It does not claim the terms are independent. They interact, and the interaction
  is why operational agencies run coupled hydrodynamic models.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

# Standard atmosphere in hectopascals, and the seawater density used for the
# inverse barometer. 1 hPa of pressure deficit lifts water roughly 1 cm.
STD_PRESSURE_HPA = 1013.25
SEAWATER_DENSITY = 1025.0      # kg/m^3
GRAVITY = 9.80665              # m/s^2


@dataclass
class WaterLevelInput:
    """Scenario inputs. Every field is something a forecaster can read off."""

    surge_m: float = 3.0                 # still-water surge from a forecast or scenario
    tide_m: float = 0.0                  # astronomical tide relative to MSL, signed
    pressure_hpa: float = STD_PRESSURE_HPA
    wind_speed_ms: float = 0.0
    fetch_km: float = 50.0
    depth_m: float = 20.0
    # Beach slope is what converts offshore setup into run-up at the shoreline.
    beach_slope: float = 0.02


def inverse_barometer(pressure_hpa: float) -> float:
    """Pressure setup in metres: a pressure deficit lifts the sea surface.

    A drop of 1 hPa below standard raises water about 1 cm. Stated as a formula
    rather than a lookup so the assumption is inspectable.
    """
    # dP in hPa -> Pa is a factor of 100; then dP = rho * g * dh.
    deficit_hpa = STD_PRESSURE_HPA - float(pressure_hpa)
    return deficit_hpa * 100.0 / (SEAWATER_DENSITY * GRAVITY)


def wind_setup(wind_speed_ms: float, fetch_km: float, depth_m: float) -> float:
    """Wind setup at the coast, from the standard wind-stress balance.

        setup = (tau * fetch) / (rho * g * depth),  tau = rho_air * Cd * U^2

    Uses a fixed drag coefficient, which is a real simplification: Cd rises with
    wind speed in reality. Stated here so nobody has to reverse-engineer it.
    """
    drag_coefficient = 0.0025
    air_density = 1.225
    wind = max(0.0, float(wind_speed_ms))
    if wind <= 0 or depth_m <= 0 or fetch_km <= 0:
        return 0.0
    stress = air_density * drag_coefficient * wind**2
    return (stress * fetch_km * 1000.0) / (SEAWATER_DENSITY * GRAVITY * depth_m)


def wave_setup(wind_speed_ms: float, fetch_km: float, beach_slope: float) -> float:
    """Wave setup at the shoreline, from deep-water wave height and slope.

    Deep-water height from a fetch-limited approximation. Unlike the others this
    is a screening estimate with a wide error bar and is labelled accordingly.
    """
    if wind_speed_ms <= 0 or fetch_km <= 0 or beach_slope <= 0:
        return 0.0
    g = GRAVITY
    # Fetch-limited significant wave height.
    height = 0.0016 * math.sqrt((g * fetch_km * 1000.0) / (wind_speed_ms**2)) * (
        wind_speed_ms**2 / g
    )
    # Shoreline setup is roughly a fifth of deep-water height, scaled by slope.
    return 0.2 * height * min(1.0, beach_slope / 0.02)


def compose(inp: WaterLevelInput) -> dict:
    """Return every contribution separately, plus the total.

    Reporting the terms is the whole point: a reviewer can disagree with one
    component and still use the rest.
    """
    barometer = inverse_barometer(inp.pressure_hpa)
    wind = wind_setup(inp.wind_speed_ms, inp.fetch_km, inp.depth_m)
    wave = wave_setup(inp.wind_speed_ms, inp.fetch_km, inp.beach_slope)
    total = inp.surge_m + inp.tide_m + barometer + wind + wave

    components = {
        "surge": round(inp.surge_m, 3),
        "tide": round(inp.tide_m, 3),
        "pressureSetup": round(barometer, 4),
        "windSetup": round(wind, 4),
        "waveSetup": round(wave, 4),
    }

    # Which term dominates tells a reviewer where the uncertainty actually lives.
    dominant = max(components, key=lambda k: abs(components[k]))
    non_surge = sum(
        abs(v) for k, v in components.items() if k != "surge"
    )

    return {
        "totalM": round(total, 3),
        "components": components,
        "dominantTerm": dominant,
        "nonSurgeContributionM": round(non_surge, 3),
        "inputs": asdict(inp),
        "model": (
            "Sum of independent contributions (surge + tide + inverse barometer + "
            "wind setup + wave setup). An explainable decomposition, not a coupled "
            "hydrodynamic simulation."
        ),
        "limitations": [
            (
                "Terms are treated as independent; in reality they interact, which is "
                "why operational agencies run coupled models."
            ),
            "Drag coefficient is fixed at 0.0025 and does not vary with wind speed.",
            "Wave setup is a fetch-limited screening estimate with a wide error bar.",
            "No live tide prediction or barometric observation is used unless supplied.",
        ],
        "authority": "Official storm-surge guidance is issued by INCOIS; warnings by IMD.",
    }


# M2, the semi-diurnal constituent that dominates India's east coast.
M2_PERIOD_HOURS = 12.42


def tide_phase(
    hours_to_landfall: float,
    period_hours: float = M2_PERIOD_HOURS,
    amplitude_m: float = 1.0,
    phase_hours: float = M2_PERIOD_HOURS / 4,
) -> float:
    """Sinusoidal tide height, so a scenario can be moved across the tidal cycle.

    The semi-diurnal period of 12.42 h is the M2 constituent, the dominant one on
    most of India's east coast. Real tide prediction needs harmonic constituents
    from a tide station; this exists so the console can show *why* landfall timing
    matters, and is labelled as an approximation.

    ``phase_hours`` defaults to a quarter period, which places landfall at high
    water. That is the conservative case, and it is a default rather than a
    prediction: pass an explicit phase to model a different landfall timing.
    """
    return amplitude_m * math.sin(2 * math.pi * (hours_to_landfall + phase_hours) / period_hours)


def from_landfall_timing(
    surge_m: float,
    hours_to_landfall: float,
    pressure_hpa: float = STD_PRESSURE_HPA,
    wind_speed_ms: float = 0.0,
    tide_amplitude_m: float = 1.0,
    **kwargs,
) -> dict:
    """Compose a scenario with the tide phase derived from landfall timing.

    This is the argument that makes the whole module worth having: the same storm
    landing at high versus low water produces materially different inundation, and
    a single surge slider cannot express that.
    """
    inp = WaterLevelInput(
        surge_m=surge_m,
        tide_m=tide_phase(hours_to_landfall, amplitude_m=tide_amplitude_m),
        pressure_hpa=pressure_hpa,
        wind_speed_ms=wind_speed_ms,
        **kwargs,
    )
    result = compose(inp)
    result["landfall"] = {
        "hoursToLandfall": hours_to_landfall,
        "tideApproximation": "M2 sinusoid (12.42 h); not a tide-station prediction",
    }
    return result
