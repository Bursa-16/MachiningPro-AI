"""Thread callout parser for engineering drawing text tokens.

Supports: Metric (M), UNC/UNF, BSP (G/R), NPT/NPTF.
Extracts symbolic callout data only.

FABRICATED_THREAD=NO — no thread geometry fabricated from symbols.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum, unique


@unique
class ThreadStandard(StrEnum):
    METRIC = "METRIC"
    UNC = "UNC"
    UNF = "UNF"
    UNEF = "UNEF"
    UNS = "UNS"
    BSP = "BSP"       # ISO 228 / BS 2779
    BSPT = "BSPT"     # ISO 7 / BS 21 (tapered)
    NPT = "NPT"
    NPTF = "NPTF"
    UNKNOWN = "UNKNOWN"


@unique
class ThreadOrientation(StrEnum):
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ThreadCallout:
    """Parsed thread callout from drawing text."""
    standard: ThreadStandard
    nominal_raw: str            # e.g. "10" for M10, "3/4" for 3/4 NPT
    nominal_mm: Decimal | None  # outer diameter in mm (None if not determinable)
    pitch_mm: Decimal | None    # pitch in mm (None if not specified)
    tolerance_class: str | None # e.g. "6H", "2B", "6g"
    depth_mm: Decimal | None    # thread depth in mm (None if not stated)
    thru: bool                  # True if THRU stated
    orientation: ThreadOrientation
    raw_text: str


# Metric: M10, M10x1.5, M10x1.5-6H, M10x1.5-6H-LH
_METRIC_RE = re.compile(
    r"^M(\d{1,3}(?:[.,]\d{1,2})?)"
    r"(?:[xX×](\d{1,3}(?:[.,]\d{1,3})?))??"
    r"(?:\s*[-–]\s*([1-9]\d?[A-Za-z]+))?"
    r"(?:\s*[-–]\s*(LH|RH))?\s*$",
    re.IGNORECASE,
)

# UN series: 1/4-20 UNC, 1/4-20UNC, #10-32 UNF
_UN_RE = re.compile(
    r"^(#\d+|\d+(?:[/\-]\d+)?)\s*[-–]\s*(\d+)\s+"
    r"(UNEF|UNF|UNC|UNS)"
    r"(?:\s*[-–]\s*([12][AB]))?\s*$",
    re.IGNORECASE,
)

# BSP: G1/2, G3/4-A, R3/8
_BSP_RE = re.compile(
    r"^([GR])(\d{1,3}(?:/\d{1,3})?(?:-\d+)?)"
    r"(?:\s*(A|B))?\s*$",
    re.IGNORECASE,
)

# NPT/NPTF: 1/4 NPT, 3/4-14 NPTF
_NPT_RE = re.compile(
    r"^(\d{1,3}(?:/\d{1,3})?)\s*(?:[-–]\s*\d+\s*)?"
    r"(NPTF|NPT)\s*$",
    re.IGNORECASE,
)

# Depth/THRU suffix patterns (applied after primary match)
_DEPTH_RE = re.compile(
    r"DEPTH\s*(\d+(?:[.,]\d+)?)|▽\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_THRU_RE = re.compile(r"\bTHRU\b", re.IGNORECASE)

# Approximate metric pitch table for common sizes (informational only, not fabricated):
# pitch is the standard coarse pitch for the given nominal diameter.
_METRIC_COARSE_PITCH: dict[int, Decimal] = {
    1: Decimal("0.25"), 2: Decimal("0.4"), 3: Decimal("0.5"), 4: Decimal("0.7"),
    5: Decimal("0.8"), 6: Decimal("1.0"), 8: Decimal("1.25"), 10: Decimal("1.5"),
    12: Decimal("1.75"), 14: Decimal("2.0"), 16: Decimal("2.0"), 18: Decimal("2.5"),
    20: Decimal("2.5"), 22: Decimal("2.5"), 24: Decimal("3.0"), 27: Decimal("3.0"),
    30: Decimal("3.5"), 33: Decimal("3.5"), 36: Decimal("4.0"), 39: Decimal("4.0"),
    42: Decimal("4.5"), 45: Decimal("4.5"), 48: Decimal("5.0"),
}


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None


def _extract_suffix(text: str) -> tuple[Decimal | None, bool]:
    """Return (depth_mm, thru) from thread callout suffix text."""
    depth: Decimal | None = None
    m = _DEPTH_RE.search(text)
    if m:
        raw = m.group(1) or m.group(2)
        depth = _dec(raw) if raw else None
    thru = bool(_THRU_RE.search(text))
    return depth, thru


def parse_thread_token(token: str) -> ThreadCallout | None:
    """Parse a text token as a thread callout. Returns None if not a thread."""
    t = token.strip()
    if not t:
        return None

    depth, thru = _extract_suffix(t)

    # Metric
    m = _METRIC_RE.match(t)
    if m:
        nom_str = m.group(1).replace(",", ".")
        nom = _dec(nom_str)
        pitch_str = m.group(2)
        pitch: Decimal | None = None
        if pitch_str:
            pitch = _dec(pitch_str.replace(",", "."))
        elif nom is not None:
            try:
                nom_int = int(nom)
                pitch = _METRIC_COARSE_PITCH.get(nom_int)
            except Exception:
                pass
        tol_class = m.group(3)
        # Internal: tolerance class ending in H (e.g. 6H); External: g or h
        orientation = ThreadOrientation.UNKNOWN
        if tol_class:
            if tol_class[-1].upper() == "H":
                orientation = ThreadOrientation.INTERNAL
            elif tol_class[-1] in ("g", "h", "e", "f"):
                orientation = ThreadOrientation.EXTERNAL
        return ThreadCallout(
            standard=ThreadStandard.METRIC,
            nominal_raw=nom_str,
            nominal_mm=nom,
            pitch_mm=pitch,
            tolerance_class=tol_class,
            depth_mm=depth,
            thru=thru,
            orientation=orientation,
            raw_text=t,
        )

    # UN series
    m2 = _UN_RE.match(t)
    if m2:
        nom_raw = m2.group(1)
        std_str = m2.group(3).upper()
        std_map = {
            "UNC": ThreadStandard.UNC, "UNF": ThreadStandard.UNF,
            "UNEF": ThreadStandard.UNEF, "UNS": ThreadStandard.UNS,
        }
        std = std_map.get(std_str, ThreadStandard.UNKNOWN)
        tol = m2.group(4)
        # UNC/UNF nominal in inches — we do NOT convert to mm (FABRICATED_THREAD=NO)
        return ThreadCallout(
            standard=std,
            nominal_raw=nom_raw,
            nominal_mm=None,  # inch system; no fabricated mm conversion
            pitch_mm=None,
            tolerance_class=tol,
            depth_mm=depth,
            thru=thru,
            orientation=ThreadOrientation.UNKNOWN,
            raw_text=t,
        )

    # BSP
    m3 = _BSP_RE.match(t)
    if m3:
        prefix = m3.group(1).upper()
        nom_raw = m3.group(2)
        std = ThreadStandard.BSP if prefix == "G" else ThreadStandard.BSPT
        tol = m3.group(3)
        return ThreadCallout(
            standard=std,
            nominal_raw=nom_raw,
            nominal_mm=None,
            pitch_mm=None,
            tolerance_class=tol,
            depth_mm=depth,
            thru=thru,
            orientation=ThreadOrientation.UNKNOWN,
            raw_text=t,
        )

    # NPT/NPTF
    m4 = _NPT_RE.match(t)
    if m4:
        nom_raw = m4.group(1)
        std = ThreadStandard.NPTF if "NPTF" in t.upper() else ThreadStandard.NPT
        return ThreadCallout(
            standard=std,
            nominal_raw=nom_raw,
            nominal_mm=None,
            pitch_mm=None,
            tolerance_class=None,
            depth_mm=depth,
            thru=thru,
            orientation=ThreadOrientation.UNKNOWN,
            raw_text=t,
        )

    return None


def parse_thread_tokens(tokens: list[str]) -> list[ThreadCallout]:
    """Parse a list of text tokens, returning all found thread callouts."""
    results: list[ThreadCallout] = []
    for token in tokens:
        callout = parse_thread_token(token)
        if callout is not None:
            results.append(callout)
    return results
