"""Number guardrail for AI-written text.

The project's core safety claim is that the engine computes every number and the
language model only phrases them. This module enforces that claim mechanically
rather than trusting a prompt.

Two checks run on every model response:

1. **Unbacked digits.** Every numeric token in the output must be traceable to
   the computed exposure payload, or be a declared structural constant
   (a T-minus hour, an IMD category threshold). Anything else is a violation.
2. **Invented impact.** A number attached to a population or casualty unit
   (people, lives, households, deaths) when the payload carries no population
   figure is a hard violation. This is the specific failure mode where a model
   helpfully estimates how many people are affected.

On violation the caller must discard the model text and keep the deterministic
template. Redacting in place is not offered on purpose: a partially rewritten
advisory is harder for a human reviewer to reason about than an obvious fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Numeric tokens, including decimals, thousands separators and a preceding currency sign.
_NUMBER_RE = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?![\w])")

# Nouns that can only refer to people, so a number in the same sentence as one of
# these is a claim about human impact.
_POPULATION_NOUNS = (
    "people", "person", "persons", "lives", "life", "households", "household",
    "residents", "villagers", "families", "family", "deaths", "dead", "injured",
    "casualties", "displaced", "evacuated",
)

# Impact words describe a consequence but are not themselves about people:
# "32 km of road is affected" is a grounded claim about road, not an invented
# population estimate. These only matter in the presence of a person-noun.

# Calendar and clock references. These are never exposure magnitudes, but the
# digit scanner splits them: "03:00" yielded the tokens "00" and "30", and
# "2019-05-03" yielded "2019". A cyclone advisory naturally names a landfall time,
# so without this every such draft was rejected and silently replaced by the
# template. Deliberately narrow: only dates and clock times are exempt. A physical
# quantity such as "45 m/s" or "20 m depth" stays subject to the number rule,
# because a model that invents a wind speed has invented a number.
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm|hrs?|hours?|UTC|IST)?\b", re.I)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMERIC_DATE = re.compile(r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b")
_WRITTEN_DATE = re.compile(
    r"\b(?:\d{1,2}\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b", re.I
)
_YEAR_IN_CONTEXT = re.compile(r"\b(?:in|since|during|by|from|of|year|year's)\s+(?:1[89]|20)\d{2}\b", re.I)

_DATE_TIME_PATTERNS = (_CLOCK, _ISO_DATE, _NUMERIC_DATE, _WRITTEN_DATE, _YEAR_IN_CONTEXT)


def _non_magnitude_spans(text: str) -> list[tuple[int, int]]:
    """Character ranges holding calendar or clock references."""
    return [(m.start(), m.end()) for pat in _DATE_TIME_PATTERNS for m in pat.finditer(text)]


# Structural constants that are legitimate in any advisory: planning horizons,
# the Beaufort/IMD threshold family, and calendar years.
_STRUCTURAL_CONSTANTS = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,   # months, Beaufort-ish buckets
    24, 36, 48, 72, 96,                       # T-minus planning windows
    34, 64, 90, 120,                          # IMD cyclone intensity thresholds (kt)
    100,                                      # percentages
}


@dataclass
class GuardrailResult:
    """Outcome of checking one model response."""

    ok: bool
    text: str
    violations: list[str] = field(default_factory=list)
    checked_numbers: int = 0

    @property
    def reason(self) -> str:
        return "; ".join(self.violations) if self.violations else "clean"


def _payload_numbers(payload: object, out: set[float]) -> None:
    """Collect every numeric value anywhere in the payload, at 3 rounding levels.

    Rounding levels matter because a model legitimately writes "127" for 127.32
    or "13" for 12.88. Accepting any rounding of a real value keeps the guardrail
    strict about *fabrication* without flagging ordinary rounding.
    """
    if isinstance(payload, bool):
        return
    if isinstance(payload, (int, float)):
        value = float(payload)
        out.add(value)
        out.add(round(value, 1))
        out.add(round(value, 2))
        out.add(round(value))
        # Truncation as well as rounding: 493.19 -> "493" is common phrasing.
        out.add(float(int(value)))
        return
    if isinstance(payload, dict):
        for item in payload.values():
            _payload_numbers(item, out)
        return
    if isinstance(payload, (list, tuple, set)):
        for item in payload:
            _payload_numbers(item, out)


def allowed_numbers(payload: object, extra: set[float] | None = None) -> set[float]:
    """The set of numbers a response is permitted to contain."""
    allowed: set[float] = set(_STRUCTURAL_CONSTANTS)
    _payload_numbers(payload, allowed)
    if extra:
        for value in extra:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            allowed.update({numeric, round(numeric, 1), round(numeric, 2), round(numeric)})
    return allowed


def _has_population_figure(payload: object) -> bool:
    """True when the payload actually carries a population figure to quote."""
    keys = ("population", "people", "persons", "households", "affected_population", "population_in_zone")

    def walk(node: object) -> bool:
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).lower() in keys and isinstance(value, (int, float)) and not isinstance(value, bool):
                    return True
                if walk(value):
                    return True
        elif isinstance(node, (list, tuple)):
            return any(walk(item) for item in node)
        return False

    return walk(payload)


def _sentence_around(text: str, start: int, end: int) -> str:
    """The sentence a number sits in, lowercased.

    Sentence scope, not a fixed character window. A window makes the verdict depend
    on how long the intervening words happen to be: "32 km of road is affected" was
    rejected while "276 sq km of land is affected" passed, purely because
    "affected" fell at character 22 in one and 25 in the other.
    """
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right = text.find(".", end)
    return text[left: right if right != -1 else len(text)].lower()


def check(text: str, payload: object, extra_allowed: set[float] | None = None) -> GuardrailResult:
    """Verify that every number in `text` is backed by `payload`.

    Returns a result whose ``ok`` is False when the caller must fall back to the
    deterministic template.
    """
    allowed = allowed_numbers(payload, extra_allowed)
    violations: list[str] = []
    checked = 0

    has_population = _has_population_figure(payload)
    ignored = _non_magnitude_spans(text)

    for match in _NUMBER_RE.finditer(text):
        raw = match.group(1)
        if any(lo <= match.start() and match.end() <= hi for lo, hi in ignored):
            continue
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        checked += 1

        tail = text[match.end():match.end() + 24].lower()
        head = text[max(0, match.start() - 12):match.start()].lower()

        if re.match(r"\s*%", tail):
            # A percentage is allowed only if that value is itself in the payload.
            if value not in allowed and round(value) not in allowed:
                violations.append(f"unbacked percentage {raw!r}")
            continue

        if not has_population and any(
            noun in _sentence_around(text, match.start(), match.end())
            for noun in _POPULATION_NOUNS
        ):
            violations.append(
                f"invented impact: {raw!r} sits in a sentence about people but the "
                "exposure payload contains no population figure"
            )
            continue

        if (head.strip().endswith("t-") or head.strip().endswith("t -")) and value in _STRUCTURAL_CONSTANTS:
            continue

        if value in allowed:
            continue

        violations.append(f"unbacked number {raw!r}")

    # De-duplicate while preserving the order a reviewer will read.
    seen: set[str] = set()
    unique = [v for v in violations if not (v in seen or seen.add(v))]

    return GuardrailResult(ok=not unique, text=text, violations=unique, checked_numbers=checked)
