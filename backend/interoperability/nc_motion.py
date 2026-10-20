"""Bounded NC/G-code motion distance parser.

PROCESS_PLAN_CYCLE_TIME_CAD_CAM_INTEGRATION_01 — Phase 2

Parser profile  : GENERIC_ISO_GCODE_SUBSET
Supported       : G20/G21, G90/G91, G0/G00, G1/G01, X/Y/Z, F
Detected (no expand): G2/G3 arcs, G81-G85 canned cycles, G41/G42 compensation
Rejected        : M98/M99 subprograms, # macro variables, WHILE/IF control flow

Safety constants enforced here:
    NC_FILE_EXECUTED=NO          — text is data only; no exec, no subprocess
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    ARC_AS_CHORD_APPROXIMATION=NO
    IGNORED_UNSUPPORTED_MOTION_REPORTED_COMPLETE=NO
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO
    UNKNOWN_INITIAL_POSITION_GUESSED=NO
    PRIVATE_PATH_IN_PATH_EVIDENCE=NO
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

__all__ = [
    "NcAnalysisStatus",
    "NcMotionResult",
    "parse_nc_motion",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARSER_PROFILE = "GENERIC_ISO_GCODE_SUBSET"
PARSER_VERSION = "1.0.0"
_MAX_LINES = 100_000
_INCH_TO_MM = 25.4

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class NcAnalysisStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNSUPPORTED_SEMANTICS = "UNSUPPORTED_SEMANTICS"
    INVALID_PROGRAM = "INVALID_PROGRAM"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class NcMotionResult(BaseModel):
    """Result of bounded NC motion parsing."""

    parser_profile: str = PARSER_PROFILE
    parser_version: str = PARSER_VERSION
    analysis_status: NcAnalysisStatus

    # Distances (always in mm, always >= 0)
    feed_distance_mm: float = 0.0
    rapid_distance_mm: float = 0.0

    # Counts
    block_count_total: int = 0
    supported_motion_count: int = 0
    unsupported_construct_count: int = 0
    unknown_start_count: int = 0
    tool_change_count: int = 0

    # Units
    units_declared: str | None = None       # "mm" | "inch" | None

    # Feed
    nc_commanded_feed_mm_min: float | None = None

    # Diagnostics
    unsupported_features: list[str] = []
    limitations: list[str] = []

    # Immutable safety flags — always False; present for explicit audit
    nc_feed_move_equals_confirmed_cutting: bool = False
    arc_chord_approximation_used: bool = False
    nc_file_executed: bool = False


# ---------------------------------------------------------------------------
# Internal parser state
# ---------------------------------------------------------------------------


@dataclass
class _ModalState:
    units: str | None = None           # None | "mm" | "inch"
    positioning: str = "absolute"      # "absolute" | "incremental"
    motion: str | None = None          # None | "G0" | "G1" | "G2" | "G3" | "CANNED"
    x: float | None = None
    y: float | None = None
    z: float | None = None
    feed_mm_min: float | None = None   # current F modal, stored in mm/min


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_PAREN_COMMENT_RE = re.compile(r"\(.*?\)", re.DOTALL)
_WORD_RE = re.compile(r"([A-Za-z])([-+]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE)
_ONUM_RE = re.compile(r"^[Oo]\d+\s*$")
_MACRO_VAR_RE = re.compile(r"#")
_FLOW_RE = re.compile(r"\bWHILE\b|\bIF\s*\[", re.IGNORECASE)


def _strip_comments(line: str) -> str:
    line = _PAREN_COMMENT_RE.sub("", line)
    semi = line.find(";")
    if semi >= 0:
        line = line[:semi]
    return line.strip()


def _parse_words(line: str) -> list[tuple[str, float]]:
    """Return (uppercase_letter, numeric_value) pairs from a cleaned block."""
    result: list[tuple[str, float]] = []
    for m in _WORD_RE.finditer(line):
        try:
            result.append((m.group(1).upper(), float(m.group(2))))
        except ValueError:
            pass
    return result


def _g(val: float) -> int:
    """Normalise G-code decimal to integer, e.g. G17.1 → 17, G01 → 1."""
    return int(val)


def _mm(val: float, state: _ModalState) -> float:
    """Convert a coordinate/distance word to mm based on current unit modal."""
    if state.units == "inch":
        return val * _INCH_TO_MM
    return val


# ---------------------------------------------------------------------------
# Motion distance helper
# ---------------------------------------------------------------------------


def _compute_distance(
    state: _ModalState,
    new_x: float | None,
    new_y: float | None,
    new_z: float | None,
) -> float | None:
    """
    Return Euclidean distance for a linear move, or None if start unknown.

    UNKNOWN_INITIAL_POSITION_GUESSED=NO — returns None rather than
    fabricating a distance when the start position is ambiguous.
    """
    if state.positioning == "incremental":
        dx = new_x if new_x is not None else 0.0
        dy = new_y if new_y is not None else 0.0
        dz = new_z if new_z is not None else 0.0
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    # Absolute mode: need known start for each axis that moved
    if new_x is not None and state.x is None:
        return None
    if new_y is not None and state.y is None:
        return None
    if new_z is not None and state.z is None:
        return None

    dx = (new_x - state.x) if new_x is not None else 0.0
    dy = (new_y - state.y) if new_y is not None else 0.0
    dz = (new_z - state.z) if new_z is not None else 0.0
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _update_position(
    state: _ModalState,
    new_x: float | None,
    new_y: float | None,
    new_z: float | None,
) -> None:
    """Update modal position after a move."""
    if state.positioning == "incremental":
        if new_x is not None:
            state.x = (state.x + new_x) if state.x is not None else None
        if new_y is not None:
            state.y = (state.y + new_y) if state.y is not None else None
        if new_z is not None:
            state.z = (state.z + new_z) if state.z is not None else None
    else:
        if new_x is not None:
            state.x = new_x
        if new_y is not None:
            state.y = new_y
        if new_z is not None:
            state.z = new_z


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------


def parse_nc_motion(
    text: str,
    *,
    initial_x: float | None = None,
    initial_y: float | None = None,
    initial_z: float | None = None,
) -> NcMotionResult:
    """Parse NC G-code text and extract deterministic motion distances.

    Safety contract
    ---------------
    NC_FILE_EXECUTED=NO — ``text`` is treated as plain text data.
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — G1 distance ≠ cutting path.
    ARC_AS_CHORD_APPROXIMATION=NO — G2/G3 arcs are detected and flagged;
        their path is not approximated as chord length.
    UNKNOWN_INITIAL_POSITION_GUESSED=NO — moves whose start position
        cannot be determined are skipped; they increment ``unknown_start_count``
        and degrade status to PARTIAL.
    PRIVATE_PATH_IN_PATH_EVIDENCE=NO — call site must not pass absolute paths
        as ``source_name``; this module never reads a filesystem path.

    Parameters
    ----------
    text:
        The NC program text. Never executed — parsed as data only.
    initial_x, initial_y, initial_z:
        Optional known starting machine position in the workpiece coordinate
        system (mm if G21, inch if G20 — same units as the program).
        Supply (0.0, 0.0, 0.0) to declare the program starts at the origin.
        If None, the first absolute move from an unknown axis cannot be
        measured (UNKNOWN_INITIAL_POSITION_GUESSED=NO).
    """
    # Initial state
    state = _ModalState(x=initial_x, y=initial_y, z=initial_z)

    # Accumulators
    feed_mm = 0.0
    rapid_mm = 0.0
    supported_count = 0
    unsupported_count = 0
    unknown_start_count = 0
    tool_change_count = 0
    block_count = 0
    unsupported: list[str] = []
    limitations: list[str] = []
    last_feed_mm_min: float | None = None

    has_partial = False
    has_unsupported_semantics = False
    has_invalid = False

    def _add_unsupported(feat: str) -> None:
        nonlocal unsupported_count
        if feat not in unsupported:
            unsupported.append(feat)
            unsupported_count += 1

    # ── Line-count guard ──────────────────────────────────────────────────

    lines = text.splitlines()
    if len(lines) > _MAX_LINES:
        return NcMotionResult(
            analysis_status=NcAnalysisStatus.INVALID_PROGRAM,
            limitations=[f"Program exceeds maximum line count ({_MAX_LINES})."],
            unsupported_features=["PROGRAM_TOO_LARGE"],
        )

    pending_t: int | None = None   # tool number waiting for M6

    for raw_line in lines:
        # ── Pre-scan for macro constructs ─────────────────────────────────
        if _MACRO_VAR_RE.search(raw_line):
            has_unsupported_semantics = True
            _add_unsupported("MACRO_VARIABLE_DETECTED")

        if _FLOW_RE.search(raw_line):
            has_unsupported_semantics = True
            _add_unsupported("MACRO_CONTROL_FLOW_DETECTED")

        # ── Clean and skip trivial lines ──────────────────────────────────
        cleaned = _strip_comments(raw_line)
        if not cleaned or cleaned in ("%",):
            continue
        if _ONUM_RE.match(cleaned):
            continue  # pure O-number program header

        block_count += 1
        words = _parse_words(cleaned)
        if not words:
            continue

        # ── Separate word types ───────────────────────────────────────────
        g_nums: list[int] = []
        m_nums: list[int] = []
        t_num: int | None = None
        new_x: float | None = None
        new_y: float | None = None
        new_z: float | None = None
        new_f: float | None = None

        for letter, val in words:
            if letter == "G":
                g_nums.append(_g(val))
            elif letter == "M":
                m_nums.append(int(val))
            elif letter == "T":
                t_num = int(val)
            elif letter == "X":
                new_x = _mm(val, state)
            elif letter == "Y":
                new_y = _mm(val, state)
            elif letter == "Z":
                new_z = _mm(val, state)
            elif letter == "F":
                new_f = val  # raw; conversion after units known

        # ── Update units from this line (before coord conversion) ─────────
        for gn in g_nums:
            if gn == 20:
                state.units = "inch"
                # Retroactively convert X/Y/Z/F words already parsed on this line
                if new_x is not None:
                    new_x = new_x * _INCH_TO_MM
                if new_y is not None:
                    new_y = new_y * _INCH_TO_MM
                if new_z is not None:
                    new_z = new_z * _INCH_TO_MM
            elif gn == 21:
                state.units = "mm"

        # ── Convert F word to mm/min ──────────────────────────────────────
        if new_f is not None:
            if state.units == "inch":
                state.feed_mm_min = new_f * _INCH_TO_MM
            else:
                state.feed_mm_min = new_f
            last_feed_mm_min = state.feed_mm_min

        # ── Process remaining G codes ─────────────────────────────────────
        this_line_motion: str | None = None  # G code on THIS line (overrides modal)
        this_line_arc = False
        this_line_canned = False
        this_line_end = False

        for gn in g_nums:
            if gn == 0:
                state.motion = "G0"
                this_line_motion = "G0"
            elif gn == 1:
                state.motion = "G1"
                this_line_motion = "G1"
            elif gn in (2, 3):
                has_partial = True
                _add_unsupported(f"G{gn}_ARC_UNSUPPORTED")
                state.motion = f"G{gn}"
                this_line_motion = f"G{gn}"
                this_line_arc = True
            elif gn in (81, 82, 83, 84, 85, 86, 87, 88, 89):
                has_partial = True
                _add_unsupported(f"G{gn}_CANNED_CYCLE_DETECTED")
                state.motion = "CANNED"
                this_line_motion = "CANNED"
                this_line_canned = True
            elif gn == 90:
                state.positioning = "absolute"
            elif gn == 91:
                state.positioning = "incremental"
            elif gn == 28:
                # Return to reference/home: position becomes unknown
                state.x = state.y = state.z = None
                if "G28_REFERENCE_RETURN_DETECTED" not in limitations:
                    limitations.append(
                        "G28_REFERENCE_RETURN_DETECTED — machine position reset to unknown."
                    )
            elif gn in (41, 42):
                has_partial = True
                _add_unsupported(f"G{gn}_CUTTER_RADIUS_COMP_DETECTED")
            elif gn == 40:
                pass  # cancel compensation — safe
            elif gn in (43, 44, 49):
                if f"G{gn}_TOOL_LENGTH_COMP_NOTED" not in unsupported:
                    unsupported.append(f"G{gn}_TOOL_LENGTH_COMP_NOTED")
            elif gn in (53, 54, 55, 56, 57, 58, 59):
                if f"G{gn}_WORK_OFFSET_NOTED" not in unsupported:
                    unsupported.append(f"G{gn}_WORK_OFFSET_NOTED")
            elif gn == 92:
                if "G92_COORDINATE_SHIFT_NOTED" not in unsupported:
                    unsupported.append("G92_COORDINATE_SHIFT_NOTED")
            # All other G codes are silently ignored (non-path-affecting for our model)

        # ── Process M codes ───────────────────────────────────────────────
        for mn in m_nums:
            if mn in (6,):
                if pending_t is not None or t_num is not None:
                    tool_change_count += 1
            elif mn == 98:
                has_unsupported_semantics = True
                _add_unsupported("M98_SUBPROGRAM_UNSUPPORTED")
            elif mn == 99:
                has_unsupported_semantics = True
                _add_unsupported("M99_SUBPROGRAM_UNSUPPORTED")
            elif mn in (2, 30):
                this_line_end = True

        # Track T word for T+M6 tool-change detection
        if t_num is not None:
            pending_t = t_num

        # ── Compute motion distance ───────────────────────────────────────
        has_coords = new_x is not None or new_y is not None or new_z is not None
        active_motion = this_line_motion if this_line_motion else state.motion

        linear_move = active_motion in ("G0", "G1") and not this_line_arc and not this_line_canned
        if has_coords and linear_move:
            dist = _compute_distance(state, new_x, new_y, new_z)
            _update_position(state, new_x, new_y, new_z)

            if dist is None:
                unknown_start_count += 1
                has_partial = True
                if "UNKNOWN_INITIAL_POSITION_FOR_SOME_MOVES" not in unsupported:
                    unsupported.append("UNKNOWN_INITIAL_POSITION_FOR_SOME_MOVES")
            else:
                supported_count += 1
                if active_motion == "G0":
                    rapid_mm += dist
                else:
                    feed_mm += dist

        elif has_coords and active_motion in ("G2", "G3"):
            # Arc endpoint — update position but DO NOT add distance
            # ARC_AS_CHORD_APPROXIMATION=NO
            _update_position(state, new_x, new_y, new_z)

        elif has_coords and active_motion == "CANNED":
            # Canned cycle position update; DO NOT expand path
            _update_position(state, new_x, new_y, new_z)

        if this_line_end:
            break

    # ── Final status determination ────────────────────────────────────────

    if block_count == 0:
        status = NcAnalysisStatus.INVALID_PROGRAM
    elif has_invalid:
        status = NcAnalysisStatus.INVALID_PROGRAM
    elif has_unsupported_semantics:
        status = NcAnalysisStatus.UNSUPPORTED_SEMANTICS
    elif has_partial:
        status = NcAnalysisStatus.PARTIAL
    elif supported_count == 0 and unknown_start_count == 0:
        status = NcAnalysisStatus.INSUFFICIENT_DATA
    else:
        status = NcAnalysisStatus.COMPLETE

    # ── Build limitations list ────────────────────────────────────────────

    limitations.append(
        "NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — G1 motion does not confirm "
        "material engagement. feed_distance_mm is NC commanded feed path, not cutting path."
    )
    limitations.append(
        f"PARSER_PROFILE={PARSER_PROFILE} — dialect-specific semantics not validated; "
        "G0/G1 linear only."
    )
    if not unsupported:
        # No arc/canned warning needed
        pass
    elif any("ARC" in f for f in unsupported):
        limitations.append(
            "ARC_MOTION_UNSUPPORTED — G2/G3 arcs detected and skipped; "
            "feed_distance_mm undercounts arc segments. ARC_AS_CHORD_APPROXIMATION=NO."
        )
    if any("CANNED" in f for f in unsupported):
        limitations.append(
            "CANNED_CYCLE_DETECTED — G81-G89 cycles not expanded; "
            "axial drilling/tapping path not counted."
        )
    if any("M98" in f or "M99" in f for f in unsupported):
        limitations.append(
            "SUBPROGRAM_DETECTED — M98/M99 subprogram call found; "
            "repeated path segments may be missing from total."
        )
    if any("MACRO" in f for f in unsupported):
        limitations.append(
            "MACRO_DETECTED — # variables or WHILE/IF found; "
            "conditional path segments cannot be evaluated."
        )

    return NcMotionResult(
        analysis_status=status,
        units_declared=state.units,
        feed_distance_mm=round(feed_mm, 6),
        rapid_distance_mm=round(rapid_mm, 6),
        block_count_total=block_count,
        supported_motion_count=supported_count,
        unsupported_construct_count=unsupported_count,
        unknown_start_count=unknown_start_count,
        tool_change_count=tool_change_count,
        nc_commanded_feed_mm_min=(
            round(last_feed_mm_min, 4) if last_feed_mm_min is not None else None
        ),
        unsupported_features=unsupported,
        limitations=limitations,
        # Safety flags — immutable
        nc_feed_move_equals_confirmed_cutting=False,
        arc_chord_approximation_used=False,
        nc_file_executed=False,
    )
