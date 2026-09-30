"""Gemini adapter behaviour with no key, no quota and no network.

These tests are the contract for the keyless demo: they must pass in CI and on a
judge's laptop with no credentials and no internet. Anything that needs a real
key lives in scripts/verify_google.py and is run manually by the operator.
"""
import json
from pathlib import Path

import pytest

from server import gemini


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(gemini, "_state", gemini.ModelState())


EXPOSURE = {"surge": 3.0, "areaKm2": 127.32, "medical": 4, "shelter": 1, "power": 6,
            "roadKm": 13.88, "gridKm": 10.72}


def test_not_configured_without_a_key():
    assert gemini.configured() is False


def test_discovery_reports_the_missing_key_rather_than_failing():
    state = gemini.discover(force=True)
    assert state.selected is None
    assert "GEMINI_API_KEY" in (state.error or "")


def test_draft_falls_back_to_template_and_never_raises():
    result = gemini.draft_advisory(EXPOSURE, 3.0, "en")
    assert result["mode"] == "template"
    assert result["model"] is None
    assert result["text"]
    assert "IMD" in result["text"]  # template must always name the authority


def test_draft_falls_back_in_odia_and_hindi():
    for lang in ("hi", "or"):
        result = gemini.draft_advisory(EXPOSURE, 3.0, lang)
        assert result["mode"] == "template"
        assert result["text"]


def test_status_never_leaks_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-TEST-VALUE")
    monkeypatch.setattr(gemini, "_state", gemini.ModelState())
    blob = json.dumps(gemini.status())
    assert "SECRET-TEST-VALUE" not in blob


def test_status_reports_budget_and_preference():
    status = gemini.status()
    assert status["daily_budget"] == gemini.DAILY_BUDGET
    assert status["preference"][0] == "gemini-3.7-flash"  # the model the problem statement names
    assert isinstance(status["configured"], bool)


def test_risk_read_degrades_without_a_key():
    result = gemini.read_risk(EXPOSURE, 3.0)
    assert result["ok"] is False
    assert "not configured" in result["note"]


def test_vision_degrades_without_a_key():
    result = gemini.describe_sar_chip(b"\x89PNG\r\n\x1a\n fake")
    assert result["ok"] is False


class TestQuotaLedger:
    """The free tier allows very few calls per day, so the ledger must be exact."""

    def test_budget_is_enforced(self, tmp_path: Path):
        ledger = gemini.QuotaLedger(tmp_path / "q.json", budget=2)
        assert ledger.remaining() == 2
        assert ledger.consume() is True
        assert ledger.consume() is True
        assert ledger.consume() is False       # refuses, does not raise
        assert ledger.remaining() == 0

    def test_counter_persists_across_instances(self, tmp_path: Path):
        path = tmp_path / "q.json"
        gemini.QuotaLedger(path, budget=5).consume()
        assert gemini.QuotaLedger(path, budget=5).remaining() == 4

    def test_a_corrupt_ledger_file_does_not_crash(self, tmp_path: Path):
        path = tmp_path / "q.json"
        path.write_text("{not json", encoding="utf-8")
        ledger = gemini.QuotaLedger(path, budget=3)
        assert ledger.remaining() == 3
        assert ledger.consume() is True

    def test_exhausted_budget_makes_drafting_degrade_not_fail(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "x")
        monkeypatch.setattr(gemini, "_state",
                            gemini.ModelState(selected="gemini-3.8-flash", discovered_at=1e12))
        monkeypatch.setattr(gemini, "_ledger", gemini.QuotaLedger(tmp_path / "q.json", budget=0))
        result = gemini.draft_advisory(EXPOSURE, 3.0, "en")
        assert result["mode"] == "template"
        assert "budget" in (result.get("note") or "")


class TestRealKeyConstraints:
    """Discovery must cope with a key that exposes only some generations.

    Verified against our real AI Studio key: it serves Flash generations from
    3.8 down to 3.5 and rejects Flash models below 3.5 (3.1 Lite, 3.0, 2.5, 2.0).
    The preference list therefore stops at 3.5-flash-lite and never probes older
    generations, and discovery picks the model the key actually offers rather
    than assuming a particular one exists.
    """

    def _list_models(self, monkeypatch, names: list[str]):
        """Pretend models.list() returned exactly these entries."""
        import httpx

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"models": [
                    {"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
                    for n in names
                ]}

        monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(gemini, "_state", gemini.ModelState())

    def test_key_with_only_3_6_and_3_5_selects_3_6(self, monkeypatch):
        self._list_models(monkeypatch, ["gemini-3.6-flash", "gemini-3.5-flash"])
        state = gemini.discover(force=True)
        assert state.selected == "gemini-3.6-flash"
        assert state.fallback_used is True
        assert state.error is None

    def test_full_key_prefers_the_model_the_problem_statement_names(self, monkeypatch):
        """Given a choice, 3.7 wins: the problem statement names it explicitly."""
        self._list_models(monkeypatch, [
            "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash",
        ])
        state = gemini.discover(force=True)
        assert state.selected == "gemini-3.7-flash"
        assert state.fallback_used is False

    def test_key_with_only_3_5_selects_3_5(self, monkeypatch):
        self._list_models(monkeypatch, ["gemini-3.5-flash"])
        state = gemini.discover(force=True)
        assert state.selected == "gemini-3.5-flash"
        assert state.fallback_used is True

    def test_never_selects_a_generation_below_3_5(self, monkeypatch):
        """Even if an older model is the only one offered, we do not use it."""
        self._list_models(monkeypatch, ["gemini-2.5-flash", "gemini-2.0-flash"])
        state = gemini.discover(force=True)
        assert state.selected is None
        assert "none of the preferred models" in (state.error or "")

    def test_preference_list_never_names_a_model_below_3_5(self):
        for model in gemini.MODEL_PREFERENCE:
            assert "gemini-2" not in model, f"{model} is below the 3.5 floor"
            assert model != "gemini-3.1-flash-lite", "3.1 Lite is below the 3.5 floor"

    def test_key_without_3_7_uses_the_newest_available(self, monkeypatch):
        """If 3.7 is not offered, we take 3.8 rather than failing."""
        self._list_models(monkeypatch, ["gemini-3.8-flash", "gemini-3.5-flash"])
        state = gemini.discover(force=True)
        assert state.selected == "gemini-3.8-flash"
        assert state.fallback_used is True

    def test_discovery_failure_still_leaves_template_path_working(self, monkeypatch):
        import httpx

        def boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(httpx, "get", boom)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(gemini, "_state", gemini.ModelState())
        result = gemini.draft_advisory(EXPOSURE, 3.0, "en")
        assert result["mode"] == "template"
        assert result["text"]


class TestModelOverride:
    """EYEWALL_GEMINI_MODEL pins one model and skips the preference walk."""

    def _list_models(self, monkeypatch, names):
        import httpx

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"models": [
                    {"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
                    for n in names
                ]}

        monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setattr(gemini, "_state", gemini.ModelState())

    def test_override_wins_when_available(self, monkeypatch):
        self._list_models(monkeypatch, ["gemini-3.8-flash", "gemini-3.7-flash"])
        monkeypatch.setattr(gemini, "MODEL_OVERRIDE", "gemini-3.7-flash")
        assert gemini.discover(force=True).selected == "gemini-3.7-flash"

    def test_override_falls_back_to_the_list_when_unavailable(self, monkeypatch):
        self._list_models(monkeypatch, ["gemini-3.6-flash"])
        monkeypatch.setattr(gemini, "MODEL_OVERRIDE", "gemini-3.1-pro-preview")
        state = gemini.discover(force=True)
        assert state.selected == "gemini-3.6-flash"
        assert state.error is None


class TestGuardrailCoverageOnEveryAIPath:
    """The hard rule is "the model never invents a number".

    That rule has to hold on *every* endpoint that returns model prose, not just
    the advisory one. These tests fail if a future path forgets the guardrail.
    """

    def _live(self, monkeypatch, text: str):
        monkeypatch.setattr(gemini, "_state",
                            gemini.ModelState(selected="gemini-3.7-flash", discovered_at=1e12))
        monkeypatch.setattr(gemini, "_api_key", lambda: "test-key")
        monkeypatch.setattr(gemini, "_cache_get", lambda k: None)
        monkeypatch.setattr(gemini, "_cache_put", lambda k, v: None)
        monkeypatch.setattr(gemini.ledger(), "consume", lambda: True)
        monkeypatch.setattr(gemini, "_generate", lambda *a, **k: {
            "candidates": [{"content": {"parts": [{"text": text}]}}]})

    def test_advisory_blocks_an_invented_population_figure(self, monkeypatch):
        self._live(monkeypatch, "About 24000 residents are at risk. Consult IMD/OSDMA.")
        result = gemini.draft_advisory(EXPOSURE, 3.0, "en")
        assert result["mode"] == "template"
        assert result["guardrail"]["ok"] is False
        assert "24000" not in result["text"]

    def test_risk_read_blocks_invented_figures(self, monkeypatch):
        """Regression: this path shipped with no guardrail at all."""
        payload = json.dumps({
            "score": 5,
            "headline": "Catastrophic: 24000 residents at risk",
            "reasons": ["24000 people inside the footprint", "a", "b"],
            "confidence": "high",
            "caveats": ["screening level"],
        })
        self._live(monkeypatch, payload)
        result = gemini.read_risk(EXPOSURE, 3.0)
        assert result["ok"] is False, "an unbacked population figure must not be served as ok"
        assert result["guardrail"]["ok"] is False

    def test_risk_read_passes_a_clean_grounded_assessment(self, monkeypatch):
        payload = json.dumps({
            "score": 4,
            "headline": "Severe exposure at a 3.0 m screening surge",
            "reasons": [
                "About 127 sq km of land is inside the scenario",
                "4 health facilities and 6 power assets intersect it",
                "13.9 km of road is affected",
            ],
            "confidence": "medium",
            "caveats": ["screening level; not a hydrodynamic forecast"],
        })
        self._live(monkeypatch, payload)
        result = gemini.read_risk(EXPOSURE, 3.0)
        assert result["ok"] is True
        assert result["guardrail"]["ok"] is True

    def test_vision_reports_a_violation_rather_than_hiding_it(self, monkeypatch):
        self._live(monkeypatch, "The image shows 42000 hectares of inundation.")
        result = gemini.describe_sar_chip(b"\x89PNG fake")
        assert result["guardrail"]["ok"] is False
        assert result["guardrail"]["violations"]
