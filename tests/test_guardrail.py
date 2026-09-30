"""The number guardrail is the project's central safety claim, so it gets the
most adversarial tests in the suite: the cases below are written as a hostile
model response, not a cooperative one.
"""
import pytest

from server import guardrail

EXPOSURE = {
    "surge": 3.0,
    "areaKm2": 127.32,
    "medical": 4,
    "shelter": 1,
    "power": 6,
    "roadKm": 13.88,
    "gridKm": 10.72,
}


def test_clean_advisory_passes():
    text = (
        "Screening scenario for Kendrapara district: a 3.0 m surge puts about 127 sq km "
        "of land in the screening scenario, including 4 health facilities, 1 shelter-capacity "
        "proxy and 6 power assets. 14 km of road and 11 km of transmission line intersect the "
        "scenario. Draft for human review; official warnings come from IMD and OSDMA."
    )
    result = guardrail.check(text, EXPOSURE, extra_allowed={3.0})
    assert result.ok, result.reason


def test_rounding_of_real_values_is_allowed():
    """127.32 -> "127", 13.88 -> "13.9" and 10.72 -> "11" are all legitimate."""
    text = "About 127 sq km flooded, 13.9 km of road, 11 km of line, 6 power assets."
    assert guardrail.check(text, EXPOSURE).ok


def test_invented_number_is_rejected():
    text = "A 3.0 m surge floods 127 sq km and affects 85000 hectares of cropland."
    result = guardrail.check(text, EXPOSURE, extra_allowed={3.0})
    assert not result.ok
    assert any("85000" in v for v in result.violations), result.violations


def test_invented_casualty_figure_is_rejected():
    """The classic failure: the model helpfully estimates human impact."""
    text = "Approximately 2400 people are at risk and 30 deaths are expected."
    result = guardrail.check(text, EXPOSURE)
    assert not result.ok
    assert any("invented impact" in v for v in result.violations), result.violations


def test_population_figure_allowed_when_payload_actually_has_one():
    """With a real population layer, quoting it must not be flagged."""
    payload = {**EXPOSURE, "population_in_zone": 27400}
    text = "About 27400 people are road-isolated at this surge height."
    assert guardrail.check(text, payload).ok


def test_population_figure_rejected_when_payload_has_none():
    """Same sentence, no population layer -> must be rejected."""
    text = "About 27400 people are road-isolated at this surge height."
    result = guardrail.check(text, EXPOSURE)
    assert not result.ok
    assert any("invented impact" in v for v in result.violations)


def test_structural_constants_are_allowed():
    """T-minus windows and IMD thresholds are legitimate without being in the payload."""
    text = "Shelters should be pre-stocked 48 to 72 hours before landfall; winds above 64 kt expected."
    assert guardrail.check(text, EXPOSURE).ok


def test_thousands_separator_is_parsed():
    text = "Damage estimated at 1,234 crore."
    result = guardrail.check(text, EXPOSURE)
    assert not result.ok
    assert any("1,234" in v for v in result.violations)


def test_violations_are_deduplicated_and_ordered():
    text = "999 people affected. 999 people affected. 999 people affected."
    result = guardrail.check(text, EXPOSURE)
    assert not result.ok
    assert len(result.violations) == len(set(result.violations))


def test_number_count_is_reported_for_the_audit_trail():
    text = "3.0 m surge, 127 sq km, 4 hospitals."
    result = guardrail.check(text, EXPOSURE, extra_allowed={3.0})
    assert result.checked_numbers >= 3


def test_empty_text_passes_trivially():
    result = guardrail.check("", EXPOSURE)
    assert result.ok
    assert result.checked_numbers == 0


class TestCalendarAndClockReferences:
    """Landfall times and reference dates are not exposure magnitudes.

    Regression: the digit scanner split "03:00" into "00"/"30" and "2019-05-03"
    into "2019", so any advisory naming a landfall time was rejected and
    silently replaced by the template. The model path then never survived.
    """

    @pytest.mark.parametrize("text", [
        "Landfall is expected around 03:00 and the window closes by 11:30.",
        "The reference event was Cyclone Fani, which made landfall on 2019-05-03.",
        "At 03:00 on 2019-05-03 the surge peaked.",
        "Fani struck on 3 May 2019 in the morning hours.",
        "Cyclone Fani (May 2019) was the benchmark.",
        "The comparison uses the 03/05/2019 landfall.",
        "In 2019 the district was hit twice.",
    ])
    def test_dates_and_times_are_accepted(self, text):
        result = guardrail.check(text, EXPOSURE)
        assert result.ok, result.violations

    def test_a_landfall_window_still_does_not_let_a_real_magnitude_through(self):
        """The exemption must not become a hole."""
        text = "Landfall at 03:00, with 18400 people at risk."
        result = guardrail.check(text, EXPOSURE)
        assert not result.ok
        assert any("18400" in v for v in result.violations), result.violations

    def test_physical_magnitudes_are_still_rejected_by_design(self):
        """A model that invents a wind speed has invented a number.

        Unlike calendar references, "45 m/s" is a quantity the payload must back.
        """
        result = guardrail.check("Winds of 45 m/s are expected.", EXPOSURE)
        assert not result.ok
        assert any("45" in v for v in result.violations)


class TestPopulationRuleIsSentenceScoped:
    """Regression: the rule used a 24-character tail, so the verdict depended on
    word lengths. "32 km of road is affected" was rejected as an invented
    population figure while "276 sq km of land is affected" passed, purely
    because "affected" fell at character 22 in one and 25 in the other.
    """

    @pytest.mark.parametrize("text", [
        "About 127 sq km of land is affected by the screening scenario.",
        "14 km of road is affected, along with 6 power assets.",
        "4 health facilities and 1 shelter-capacity proxy are affected.",
        "Roughly 127 sq km of land, 14 km of road and 6 power assets are affected.",
    ])
    def test_grounded_impact_sentences_are_accepted(self, text):
        result = guardrail.check(text, EXPOSURE, extra_allowed={3.0})
        assert result.ok, result.violations

    @pytest.mark.parametrize("text", [
        "An estimated 24000 residents are affected.",
        "Approximately 240 people are at risk and 30 deaths are expected.",
        "Some 850 households will lose their homes.",
        "1200 villagers are cut off.",
    ])
    def test_sentences_about_people_are_rejected(self, text):
        result = guardrail.check(text, EXPOSURE)
        assert not result.ok, "a sentence about people must not pass unbacked"
        assert any("invented impact" in v for v in result.violations), result.violations

    def test_evidence_is_independent_of_surrounding_word_length(self):
        """The two sentences differ only in the length of the words before the
        impact word, which is exactly what used to flip the verdict."""
        a = guardrail.check("About 127 sq km of land is affected.", EXPOSURE, extra_allowed={3.0})
        b = guardrail.check("About 127 sq km of very flat land is affected.", EXPOSURE, extra_allowed={3.0})
        assert a.ok == b.ok, (a.violations, b.violations)
