"""Surface finish annotation parser for engineering drawing text tokens.

Extracts Ra, Rz, Rt, Rmax and machining required/prohibited designations.

FABRICATED_SURFACE_FINISH=NO
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum, unique


@unique
class SurfaceFinishParameter(StrEnum):
    Ra = "Ra"
    Rz = "Rz"
    Rt = "Rt"
    Rmax = "Rmax"
    MACHINING_REQUIRED = "MACHINING_REQUIRED"
    MACHINING_PROHIBITED = "MACHINING_PROHIBITED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SurfaceFinishCallout:
    """Parsed surface finish annotation."""
    parameter: SurfaceFinishParameter
    value: Decimal | None       # Roughness value; None for machining required/prohibited
    unit: str | None            # "µm" or "µin"; None when no value
    lay_symbol: str | None      # Optional lay symbol (=, X, M, C, R, P)
    machining_allowance_mm: Decimal | None  # Optional material allowance
    raw_text: str


# Ra 1.6, Rz 3.2, Rt 6.3, Rmax 12.5  (µm implied in mm drawings)
_SF_VALUE_RE = re.compile(
    r"^(Ra|Rz|Rt|Rmax)\s*(\d+(?:[.,]\d+)?)\s*(µm|um|μm|µin|uin)?\s*$",
    re.IGNORECASE,
)

# Ra3.2 (no space)
_SF_COMPACT_RE = re.compile(
    r"^(Ra|Rz|Rt|Rmax)(\d+(?:[.,]\d+)?)(µm|um|μm|µin|uin)?\s*$",
    re.IGNORECASE,
)

# Machining required: √ or ∇ alone
_MACHINING_REQUIRED_RE = re.compile(r"^[√∇⛏]$")

# Machining prohibited: circle-slash symbol or explicit text
_MACHINING_PROHIBITED_RE = re.compile(
    r"^([∅⊘]\/|NO\s*MACHINING|MACHINING\s*PROHIBITED)$",
    re.IGNORECASE,
)

# Lay symbol (optional suffix)
_LAY_RE = re.compile(r"[=X⊥M C R P]$")


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def _normalize_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    raw_lower = raw.lower()
    if raw_lower in ("µm", "um", "μm"):
        return "µm"
    if raw_lower in ("µin", "uin"):
        return "µin"
    return raw


def parse_surface_finish_token(token: str) -> SurfaceFinishCallout | None:
    """Parse a text token as a surface finish annotation. Returns None if not SF."""
    t = token.strip()
    if not t:
        return None

    # Machining prohibited
    if _MACHINING_PROHIBITED_RE.match(t):
        return SurfaceFinishCallout(
            parameter=SurfaceFinishParameter.MACHINING_PROHIBITED,
            value=None, unit=None, lay_symbol=None,
            machining_allowance_mm=None, raw_text=t,
        )

    # Machining required
    if _MACHINING_REQUIRED_RE.match(t):
        return SurfaceFinishCallout(
            parameter=SurfaceFinishParameter.MACHINING_REQUIRED,
            value=None, unit=None, lay_symbol=None,
            machining_allowance_mm=None, raw_text=t,
        )

    # Value with space: Ra 1.6
    m = _SF_VALUE_RE.match(t)
    if m:
        param_str = m.group(1)
        val = _dec(m.group(2))
        unit = _normalize_unit(m.group(3)) or "µm"
        param = SurfaceFinishParameter(param_str)
        return SurfaceFinishCallout(
            parameter=param, value=val, unit=unit,
            lay_symbol=None, machining_allowance_mm=None, raw_text=t,
        )

    # Compact: Ra3.2
    m2 = _SF_COMPACT_RE.match(t)
    if m2:
        param_str = m2.group(1)
        val = _dec(m2.group(2))
        unit = _normalize_unit(m2.group(3)) or "µm"
        try:
            param = SurfaceFinishParameter(param_str)
        except ValueError:
            return None
        return SurfaceFinishCallout(
            parameter=param, value=val, unit=unit,
            lay_symbol=None, machining_allowance_mm=None, raw_text=t,
        )

    return None


def parse_surface_finish_tokens(tokens: list[str]) -> list[SurfaceFinishCallout]:
    """Parse a list of text tokens, returning all found surface finish callouts."""
    results: list[SurfaceFinishCallout] = []
    for token in tokens:
        callout = parse_surface_finish_token(token)
        if callout is not None:
            results.append(callout)
    return results
