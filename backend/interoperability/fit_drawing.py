"""Fit callout parser for ISO 286-1 tolerance designations.

Extracts fit codes (H7, g6, JS7, H7/g6) from drawing text tokens.
Does NOT fabricate numerical fit limits — only symbolic codes.

FABRICATED_FIT_LIMITS=NO
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum, unique


@unique
class FitClass(StrEnum):
    HOLE = "HOLE"           # Upper-case fundamental deviation (A-ZC)
    SHAFT = "SHAFT"         # Lower-case fundamental deviation (a-zc)
    UNKNOWN = "UNKNOWN"


@unique
class FitParseStatus(StrEnum):
    PARSED = "PARSED"
    NO_FIT = "NO_FIT"
    AMBIGUOUS = "AMBIGUOUS"


# ISO 286-1 fit code: 1-2 letter deviation + 1-2 digit grade
# e.g. H7, g6, JS7, h11, F8, k5, za4, AB1
_FIT_PATTERN = re.compile(
    r"^([A-Za-z]{1,3})(\d{1,2})$"
)

# Combined fit: H7/g6 or H7-g6
_COMBINED_FIT_PATTERN = re.compile(
    r"^([A-Za-z]{1,3}\d{1,2})[/\-]([A-Za-z]{1,3}\d{1,2})$"
)

# Dimension + fit: Ø25 H7  or  Ø25H7  or  25 H7
_DIM_FIT_PATTERN = re.compile(
    r"^[ØR∅]?\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]{1,3}\d{1,2})$"
)


@dataclass(frozen=True)
class FitCallout:
    """A parsed ISO 286-1 fit designation."""
    fit_code: str           # e.g. "H7", "g6"
    fit_class: FitClass     # HOLE or SHAFT
    grade: int              # IT grade number e.g. 7
    deviation: str          # Fundamental deviation letter(s) e.g. "H", "g"
    nominal_mm: Decimal | None = None  # from associated dimension token
    mating_fit_code: str | None = None  # for H7/g6 combined callouts
    raw_text: str | None = None


def _fit_class(deviation: str) -> FitClass:
    """Upper-case → HOLE (internal); lower-case → SHAFT (external)."""
    if deviation[0].isupper():
        return FitClass.HOLE
    elif deviation[0].islower():
        return FitClass.SHAFT
    return FitClass.UNKNOWN


def _parse_single_fit(token: str) -> FitCallout | None:
    m = _FIT_PATTERN.match(token.strip())
    if not m:
        return None
    deviation = m.group(1)
    grade_str = m.group(2)
    try:
        grade = int(grade_str)
    except ValueError:
        return None
    if grade < 0 or grade > 18:
        return None
    return FitCallout(
        fit_code=token.strip(),
        fit_class=_fit_class(deviation),
        grade=grade,
        deviation=deviation,
        raw_text=token.strip(),
    )


def parse_fit_token(token: str) -> tuple[FitParseStatus, list[FitCallout]]:
    """Parse a single text token for ISO fit codes.

    Returns (status, callouts). Multiple callouts for combined H7/g6 form.
    """
    token = token.strip()
    if not token:
        return FitParseStatus.NO_FIT, []

    # Combined fit: H7/g6
    m = _COMBINED_FIT_PATTERN.match(token)
    if m:
        c1 = _parse_single_fit(m.group(1))
        c2 = _parse_single_fit(m.group(2))
        if c1 and c2:
            c1 = FitCallout(
                fit_code=c1.fit_code, fit_class=c1.fit_class,
                grade=c1.grade, deviation=c1.deviation,
                mating_fit_code=c2.fit_code, raw_text=token,
            )
            return FitParseStatus.PARSED, [c1, c2]

    # Dimension + fit: Ø25 H7
    m2 = _DIM_FIT_PATTERN.match(token)
    if m2:
        dim_str = m2.group(1).replace(",", ".")
        fit_str = m2.group(2)
        try:
            nominal = Decimal(dim_str)
        except Exception:
            nominal = None
        callout = _parse_single_fit(fit_str)
        if callout:
            callout = FitCallout(
                fit_code=callout.fit_code, fit_class=callout.fit_class,
                grade=callout.grade, deviation=callout.deviation,
                nominal_mm=nominal, raw_text=token,
            )
            return FitParseStatus.PARSED, [callout]

    # Single fit token
    callout = _parse_single_fit(token)
    if callout:
        return FitParseStatus.PARSED, [callout]

    return FitParseStatus.NO_FIT, []


def parse_fit_tokens(tokens: list[str]) -> list[FitCallout]:
    """Parse a list of text tokens, returning all found fit callouts."""
    results: list[FitCallout] = []
    for token in tokens:
        status, callouts = parse_fit_token(token)
        if status == FitParseStatus.PARSED:
            results.extend(callouts)
    return results
