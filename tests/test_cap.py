"""CAP 1.2 output tests.

Two classes of assertion matter here:

1. **Schema shape** — the document must be valid CAP 1.2, because the point of
   emitting XML rather than JSON is that a real aggregator could ingest it.
2. **Safety** — a prototype must never be able to emit something a consumer could
   mistake for an official warning. These tests fail loudly if that changes.
"""
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import pytest

from server.cap import DEPARTMENTS, NS, build_cap, validate

EXPOSURE = {
    "surge": 3.5, "areaKm2": 275.73, "medical": 5, "shelter": 4, "power": 8,
    "roadKm": 32.41, "gridKm": 32.02,
}
ACCESSIBILITY = {"impassableRoadKm": 61.51, "isolatedFacilities": [{"name": "x"}] * 16}


def _xml(**kwargs) -> str:
    defaults = {"surge": 3.5, "exposure": EXPOSURE, "accessibility": ACCESSIBILITY}
    return build_cap(**{**defaults, **kwargs})


class TestSchemaValidity:
    def test_output_passes_our_own_validator(self):
        assert validate(_xml()) == []

    def test_well_formed_and_namespaced(self):
        root = ET.fromstring(_xml())
        assert root.tag == f"{{{NS}}}alert"

    def test_has_the_xml_declaration(self):
        assert _xml().startswith('<?xml version="1.0" encoding="UTF-8"?>')

    @pytest.mark.parametrize(
        "element",
        ["identifier", "sender", "sent", "status", "msgType", "scope"],
    )
    def test_top_level_required_elements_present(self, element):
        assert ET.fromstring(_xml()).find(f"{{{NS}}}{element}") is not None

    @pytest.mark.parametrize(
        "element",
        ["category", "event", "urgency", "severity", "certainty", "area"],
    )
    def test_info_required_elements_present(self, element):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        assert info.find(f"{{{NS}}}{element}") is not None

    def test_category_is_the_cap_vocabulary_value(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        assert info.findtext(f"{{{NS}}}category") == "Met"

    def test_timestamps_are_iso8601_with_offset(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        for field in ("effective", "expires"):
            value = info.findtext(f"{{{NS}}}{field}")
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")

    @pytest.mark.parametrize("field", ["sent"])
    def test_top_level_sent_is_xs_datetime(self, field):
        """CAP 1.2's cap:dateTimeType restricts xs:dateTime.

        xs:dateTime requires the UTC offset to carry a colon ("+00:00"). The
        natural-looking strftime("%z") emits "+0000", which is well-formed XML
        but fails a conforming parser, so the document would be rejected by a
        real CAP aggregator while every other test stayed green.
        """
        value = ET.fromstring(_xml()).findtext(f"{{{NS}}}{field}")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})", value), (
            f"<{field}> is {value!r}; xs:dateTime needs +hh:mm, not +hhmm"
        )

    def test_info_timestamps_are_xs_datetime(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        for field in ("effective", "expires"):
            value = info.findtext(f"{{{NS}}}{field}")
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})", value), (
                f"<{field}> is {value!r}; xs:dateTime needs +hh:mm, not +hhmm"
            )

    def test_expires_is_after_effective(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        eff = datetime.strptime(info.findtext(f"{{{NS}}}effective"), "%Y-%m-%dT%H:%M:%S%z")
        exp = datetime.strptime(info.findtext(f"{{{NS}}}expires"), "%Y-%m-%dT%H:%M:%S%z")
        assert exp > eff


class TestSafetyInvariants:
    """The claims the project makes about never emitting a live warning."""

    def test_status_is_always_exercise(self):
        for surge in (0.0, 1.0, 3.5, 6.0):
            root = ET.fromstring(_xml(surge=surge))
            assert root.findtext(f"{{{NS}}}status") == "Exercise"

    def test_sender_name_names_the_project_and_flags_exercise(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        sender = info.findtext(f"{{{NS}}}senderName") or ""
        assert "Eyewall" in sender
        assert "EXERCISE" in sender.upper()

    def test_sender_name_cannot_be_mistaken_for_imd(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        sender = (info.findtext(f"{{{NS}}}senderName") or "").lower()
        assert "imd" not in sender or "not" in sender

    def test_validator_rejects_a_non_exercise_status(self):
        """Prove the guard actually fires rather than only being documented."""
        tampered = _xml().replace("<status>Exercise</status>", "<status>Actual</status>")
        problems = validate(tampered)
        assert any("Exercise" in p for p in problems), problems

    def test_description_names_the_warning_authority(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        text = (info.findtext(f"{{{NS}}}description") or "").upper()
        assert "IMD" in text and "OSDMA" in text

    def test_description_states_it_is_screening_level(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        text = (info.findtext(f"{{{NS}}}description") or "").lower()
        assert "screening" in text
        assert "not a hydrodynamic" in text


class TestSeverityBanding:
    def test_severity_increases_with_surge(self):
        order = {"Minor": 0, "Moderate": 1, "Severe": 2, "Extreme": 3}

        def severity(surge):
            info = ET.fromstring(_xml(surge=surge)).find(f"{{{NS}}}info")
            return order[info.findtext(f"{{{NS}}}severity")]

        values = [severity(s) for s in (0.5, 1.5, 3.0, 5.0)]
        assert values == sorted(values), values

    def test_urgency_reaches_immediate_at_high_surge(self):
        info = ET.fromstring(_xml(surge=5.0)).find(f"{{{NS}}}info")
        assert info.findtext(f"{{{NS}}}urgency") == "Immediate"

    def test_low_surge_is_not_extreme(self):
        info = ET.fromstring(_xml(surge=0.5)).find(f"{{{NS}}}info")
        assert info.findtext(f"{{{NS}}}severity") in {"Minor", "Moderate"}


class TestRouting:
    def test_every_department_is_addressable(self):
        for dept in DEPARTMENTS:
            info = ET.fromstring(_xml(department=dept)).find(f"{{{NS}}}info")
            assert info.findtext(f"{{{NS}}}instruction") == DEPARTMENTS[dept]

    def test_unknown_department_falls_back_rather_than_failing(self):
        info = ET.fromstring(_xml(department="nonexistent")).find(f"{{{NS}}}info")
        assert info.findtext(f"{{{NS}}}instruction") == DEPARTMENTS["disaster"]

    def test_department_is_queryable_via_event_code(self):
        root = ET.fromstring(_xml(department="power"))
        codes = {
            c.get("valueName"): c.text
            for c in root.findall(f"{{{NS}}}eventCode")
        }
        assert codes["department"] == "power"

    def test_areas_are_listed(self):
        root = ET.fromstring(_xml(areas=["Rajkanika block", "Rajnagar block"]))
        descs = [
            a.findtext(f"{{{NS}}}areaDesc")
            for a in root.findall(f"{{{NS}}}info/{{{NS}}}area")
        ]
        assert descs == ["Rajkanika block", "Rajnagar block"]

    def test_default_area_names_the_district_not_invented_blocks(self):
        root = ET.fromstring(_xml())
        desc = root.find(f"{{{NS}}}info/{{{NS}}}area").findtext(f"{{{NS}}}areaDesc")
        assert "Kendrapara" in desc


class TestNumberFidelity:
    """The XML must carry the engine's numbers, not paraphrases of them."""

    def test_description_contains_the_computed_area(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        assert "276" in info.findtext(f"{{{NS}}}description")

    def test_description_carries_accessibility_when_supplied(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        text = info.findtext(f"{{{NS}}}description")
        assert "62" in text or "61" in text   # 61.51 km rounds to 62
        assert "16" in text

    def test_headline_truncates_to_the_cap_limit(self):
        info = ET.fromstring(_xml()).find(f"{{{NS}}}info")
        assert len(info.findtext(f"{{{NS}}}headline")) <= 160

    def test_identifier_is_stable_within_the_same_minute(self):
        fixed = datetime(2026, 9, 30, 14, 5, 0, tzinfo=UTC)
        a = ET.fromstring(_xml(now=fixed)).findtext(f"{{{NS}}}identifier")
        b = ET.fromstring(_xml(now=fixed)).findtext(f"{{{NS}}}identifier")
        assert a == b, "pressing the button twice must not mint a new alert id"

    def test_identifier_changes_with_surge(self):
        fixed = datetime(2026, 9, 30, 14, 5, 0, tzinfo=UTC)
        a = ET.fromstring(_xml(surge=3.0, now=fixed)).findtext(f"{{{NS}}}identifier")
        b = ET.fromstring(_xml(surge=4.0, now=fixed)).findtext(f"{{{NS}}}identifier")
        assert a != b


class TestRobustness:
    def test_missing_optional_exposure_keys_do_not_crash(self):
        xml = build_cap(3.0, {})
        assert validate(xml) == []

    def test_no_accessibility_block_still_produces_valid_xml(self):
        xml = build_cap(3.0, EXPOSURE, accessibility=None)
        assert validate(xml) == []

    def test_odd_language_and_area_strings_are_escaped(self):
        xml = _xml(language="en", areas=["Block & <script>alert(1)</script>"])
        # Must parse, and the payload must survive as text rather than markup.
        root = ET.fromstring(xml)
        desc = root.find(f"{{{NS}}}info/{{{NS}}}area").findtext(f"{{{NS}}}areaDesc")
        assert "<script>" in desc
        assert len(root.findall(".//{http://www.w3.org/1999/xhtml}script")) == 0

    def test_validator_reports_malformed_xml(self):
        problems = validate("<alert><unclosed>")
        assert problems and "not well-formed" in problems[0]

    def test_validator_reports_a_missing_info_block(self):
        problems = validate(f'<?xml version="1.0"?><alert xmlns="{NS}"><status>Exercise</status></alert>')
        assert any("info" in p for p in problems)
