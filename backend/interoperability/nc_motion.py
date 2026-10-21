"""Bounded NC/G-code motion distance parser.

PROCESS_PLAN_CYCLE_TIME_CAD_CAM_INTEGRATION_01 — Phase 2
NC_ARC_AND_OPERATION_SEGMENTATION_01 — Phase 2

Parser profile  : GENERIC_ISO_GCODE_SUBSET
Supported       : G20/G21, G90/G91, G0/G00, G1/G01, G17/G18/G19,
                  G2/G3 (IJK relative-center only), X/Y/Z/I/J/K, F
Arc support     : Exact analytic arcs. R-format DEFERRED.
                  ARC_FALLBACK_TO_CHORD=NO
Segmentation    : NC Motion Segments bounded by T+M6 tool-change events.
Detected (no expand): G81-G89 canned cycles, G41/G42 compensation
Rejected        : R-format G2/G3, M98/M99 subprograms, # macro variables,
                  WHILE/IF control flow

Safety constants enforced here:
    NC_FILE_EXECUTED=NO
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    ARC_AS_CHORD_APPROXIMATION=NO
    ARC_FALLBACK_TO_CHORD=NO
    IGNORED_UNSUPPORTED_MOTION_REPORTED_COMPLETE=NO
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO
    UNKNOWN_INITIAL_POSITION_GUESSED=NO
    PRIVATE_PATH_IN_PATH_EVIDENCE=NO
    NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field as dc_field
from enum import StrEnum

from pydantic import BaseModel

__all__ = [
    "NcAnalysisStatus",
    "NcMotionSegment",
    "NcMotionResult",
    "parse_nc_motion",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PARSER_PROFILE = "GENERIC_ISO_GCODE_SUBSET"
PARSER_VERSION = "2.0.0"
_MAX_LINES = 100_000
_INCH_TO_MM = 25.4
_ARC_RADIUS_ABS_TOL_MM = 0.001   # 1 µm absolute
_ARC_RADIUS_REL_TOL = 1e-4       # 0.01% relative

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class NcAnalysisStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNSUPPORTED_SEMANTICS = "UNSUPPORTED_SEMANTICS"
    INVALID_PROGRAM = "INVALID_PROGRAM"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class NcMotionSegment(BaseModel):
    """One NC Motion Segment bounded by tool-change events.

    Segments are created at each M6 tool-change event.
    The preamble segment (before the first M6) has tool_id_raw=None.

    Safety constants:
        NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO  — tool_id_raw is the
            raw NC T-word string; it is NOT matched to any MachiningPro catalog entry.
        NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — feed_motion_distance_mm is
            NC commanded feed path, not confirmed material engagement.
        ARC_FALLBACK_TO_CHORD=NO
    """

    segment_id: str                # "SEG_PREAMBLE", "SEG_TC1", "SEG_TC2", …
    start_line: int                # 1-indexed raw line (inclusive)
    end_line: int                  # 1-indexed raw line (inclusive)
    tool_id_raw: str | None        # NC T-word value; None for preamble

    # Distances (always mm, always >= 0)
    feed_motion_distance_mm: float = 0.0
    rapid_motion_distance_mm: float = 0.0

    # Motion counts
    linear_motion_count: int = 0
    arc_motion_count: int = 0

    # Commanded feed summary (mm/min; NOT reference engineering feed)
    commanded_feed_min: float | None = None
    commanded_feed_max: float | None = None
    feed_change_count: int = 0

    # Quality
    analysis_status: NcAnalysisStatus = NcAnalysisStatus.INSUFFICIENT_DATA
    unsupported_features: list[str] = []

    # Immutable safety flags
    nc_feed_move_equals_confirmed_cutting: bool = False
    arc_chord_approximation_used: bool = False


class NcMotionResult(BaseModel):
    """Result of bounded NC motion parsing."""

    parser_profile: str = PARSER_PROFILE
    parser_version: str = PARSER_VERSION
    analysis_status: NcAnalysisStatus

    # Distances (always mm, always >= 0)
    feed_distance_mm: float = 0.0
    rapid_distance_mm: float = 0.0

    # Counts
    block_count_total: int = 0
    supported_motion_count: int = 0
    unsupported_construct_count: int = 0
    unknown_start_count: int = 0
    tool_change_count: int = 0
    arc_motion_count: int = 0

    # Units
    units_declared: str | None = None

    # Feed
    nc_commanded_feed_mm_min: float | None = None

    # Diagnostics
    unsupported_features: list[str] = []
    limitations: list[str] = []

    # NC Motion Segments (tool-change bounded)
    segments: list[NcMotionSegment] = []

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
    plane: str = "G17"                 # "G17" | "G18" | "G19"
    x: float | None = None
    y: float | None = None
    z: float | None = None
    feed_mm_min: float | None = None


@dataclass
class _SegState:
    """Mutable accumulator for one NC Motion Segment being built."""
    segment_id: str
    start_line: int                    # 1-indexed
    tool_id_raw: str | None = None
    feed_mm: float = 0.0
    rapid_mm: float = 0.0
    linear_count: int = 0
    arc_count: int = 0
    feed_min: float | None = None
    feed_max: float | None = None
    feed_change_count: int = 0
    has_partial: bool = False
    has_unsupported_semantics: bool = False
    unsupported: list[str] = dc_field(default_factory=list)


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
    result: list[tuple[str, float]] = []
    for m in _WORD_RE.finditer(line):
        try:
            result.append((m.group(1).upper(), float(m.group(2))))
        except ValueError:
            pass
    return result


def _g(val: float) -> int:
    return int(val)


def _mm(val: float, state: _ModalState) -> float:
    if state.units == "inch":
        return val * _INCH_TO_MM
    return val


# ---------------------------------------------------------------------------
# Linear motion helpers (unchanged from Phase 1)
# ---------------------------------------------------------------------------


def _compute_distance(
    state: _ModalState,
    new_x: float | None,
    new_y: float | None,
    new_z: float | None,
) -> float | None:
    """Euclidean distance for a linear move.

    UNKNOWN_INITIAL_POSITION_GUESSED=NO — returns None when start unknown.
    """
    if state.positioning == "incremental":
        dx = new_x if new_x is not None else 0.0
        dy = new_y if new_y is not None else 0.0
        dz = new_z if new_z is not None else 0.0
        return math.sqrt(dx * dx + dy * dy + dz * dz)

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
# Analytic arc geometry
# ---------------------------------------------------------------------------


def _arc_sweep(
    start_u: float,
    start_v: float,
    end_u: float,
    end_v: float,
    center_u: float,
    center_v: float,
    cw: bool,
) -> float:
    """Return arc sweep angle in radians in (0, 2π].

    Full circle (start == end in plane) returns 2π.
    ARC_FALLBACK_TO_CHORD=NO — purely analytic.
    """
    if abs(end_u - start_u) < 1e-10 and abs(end_v - start_v) < 1e-10:
        return 2.0 * math.pi

    angle_s = math.atan2(start_v - center_v, start_u - center_u)
    angle_e = math.atan2(end_v - center_v, end_u - center_u)

    if cw:
        sweep = angle_s - angle_e
        if sweep <= 0.0:
            sweep += 2.0 * math.pi
    else:
        sweep = angle_e - angle_s
        if sweep <= 0.0:
            sweep += 2.0 * math.pi

    return sweep


def _validate_arc_radius(radius_s: float, radius_e: float) -> bool:
    """Return True when start/end radii are consistent within tolerance."""
    delta = abs(radius_s - radius_e)
    rel = delta / max(radius_s, 1e-9)
    return delta < _ARC_RADIUS_ABS_TOL_MM and rel < _ARC_RADIUS_REL_TOL


def _compute_arc_distance(
    state: _ModalState,
    gn: int,
    new_x: float | None,
    new_y: float | None,
    new_z: float | None,
    i_val: float | None,
    j_val: float | None,
    k_val: float | None,
) -> tuple[float | None, str | None, str | None]:
    """Compute exact analytic arc/helix distance.

    Returns (distance_mm, error_code, helix_limitation).
        distance_mm       — computed distance in mm, or None on error
        error_code        — None on success; string tag on failure
        helix_limitation  — None, or warning when helical Z unknown

    ARC_AS_CHORD_APPROXIMATION=NO
    ARC_FALLBACK_TO_CHORD=NO
    UNKNOWN_INITIAL_POSITION_GUESSED=NO
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO (IJK relative-center only)
    """
    cw = (gn == 2)
    plane = state.plane

    # Select plane axes and offsets
    if plane == "G17":      # XY plane, orthogonal Z
        start_u, start_v, start_w = state.x, state.y, state.z
        raw_end_u, raw_end_v, raw_end_w = new_x, new_y, new_z
        i_off = i_val if i_val is not None else 0.0
        j_off = j_val if j_val is not None else 0.0
        has_ijk = (i_val is not None or j_val is not None)
    elif plane == "G18":    # XZ plane, orthogonal Y
        start_u, start_v, start_w = state.x, state.z, state.y
        raw_end_u, raw_end_v, raw_end_w = new_x, new_z, new_y
        i_off = i_val if i_val is not None else 0.0
        j_off = k_val if k_val is not None else 0.0
        has_ijk = (i_val is not None or k_val is not None)
    else:                   # G19 — YZ plane, orthogonal X
        start_u, start_v, start_w = state.y, state.z, state.x
        raw_end_u, raw_end_v, raw_end_w = new_y, new_z, new_x
        i_off = j_val if j_val is not None else 0.0
        j_off = k_val if k_val is not None else 0.0
        has_ijk = (j_val is not None or k_val is not None)

    if not has_ijk:
        return None, "ARC_MISSING_IJK", None

    if start_u is None or start_v is None:
        return None, "ARC_UNKNOWN_START_POSITION", None

    # Absolute endpoints
    if state.positioning == "incremental":
        abs_end_u = start_u + (raw_end_u if raw_end_u is not None else 0.0)
        abs_end_v = start_v + (raw_end_v if raw_end_v is not None else 0.0)
        if start_w is not None and raw_end_w is not None:
            abs_end_w: float | None = start_w + raw_end_w
        else:
            abs_end_w = None
    else:
        abs_end_u = raw_end_u if raw_end_u is not None else start_u
        abs_end_v = raw_end_v if raw_end_v is not None else start_v
        abs_end_w = raw_end_w if raw_end_w is not None else start_w

    center_u = start_u + i_off
    center_v = start_v + j_off

    radius_s = math.sqrt(i_off ** 2 + j_off ** 2)
    if radius_s < 1e-10:
        return None, "ARC_ZERO_RADIUS", None

    radius_e = math.sqrt(
        (abs_end_u - center_u) ** 2 + (abs_end_v - center_v) ** 2
    )
    if not _validate_arc_radius(radius_s, radius_e):
        return None, "ARC_GEOMETRY_INCONSISTENT", None

    sweep = _arc_sweep(start_u, start_v, abs_end_u, abs_end_v,
                       center_u, center_v, cw)

    l_arc = radius_s * sweep

    # Helical component
    helix_limitation: str | None = None
    if raw_end_w is not None:
        if start_w is not None and abs_end_w is not None:
            if state.positioning == "incremental":
                delta_w = raw_end_w
            else:
                delta_w = abs_end_w - start_w
            l_total = math.sqrt(l_arc ** 2 + delta_w ** 2)
        else:
            # Orthogonal axis unknown — return planar arc with limitation
            l_total = l_arc
            helix_limitation = "ARC_HELICAL_ORTHOGONAL_AXIS_UNKNOWN_PLANAR_ONLY"
    else:
        l_total = l_arc

    return l_total, None, helix_limitation


# ---------------------------------------------------------------------------
# Segment helpers
# ---------------------------------------------------------------------------


def _seg_add_unsupported(seg: _SegState, feat: str) -> None:
    if feat not in seg.unsupported:
        seg.unsupported.append(feat)


def _seg_update_feed(seg: _SegState, feed_mm_min: float | None) -> None:
    if feed_mm_min is None:
        return
    seg.feed_change_count += 1
    if seg.feed_min is None or feed_mm_min < seg.feed_min:
        seg.feed_min = feed_mm_min
    if seg.feed_max is None or feed_mm_min > seg.feed_max:
        seg.feed_max = feed_mm_min


def _finalize_segment(seg: _SegState, end_line: int) -> NcMotionSegment:
    if seg.has_unsupported_semantics:
        status = NcAnalysisStatus.UNSUPPORTED_SEMANTICS
    elif seg.has_partial:
        status = NcAnalysisStatus.PARTIAL
    elif seg.linear_count == 0 and seg.arc_count == 0:
        status = NcAnalysisStatus.INSUFFICIENT_DATA
    else:
        status = NcAnalysisStatus.COMPLETE
    return NcMotionSegment(
        segment_id=seg.segment_id,
        start_line=seg.start_line,
        end_line=end_line,
        tool_id_raw=seg.tool_id_raw,
        feed_motion_distance_mm=round(seg.feed_mm, 6),
        rapid_motion_distance_mm=round(seg.rapid_mm, 6),
        linear_motion_count=seg.linear_count,
        arc_motion_count=seg.arc_count,
        commanded_feed_min=round(seg.feed_min, 4) if seg.feed_min is not None else None,
        commanded_feed_max=round(seg.feed_max, 4) if seg.feed_max is not None else None,
        feed_change_count=seg.feed_change_count,
        analysis_status=status,
        unsupported_features=list(seg.unsupported),
    )


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
    NC_FILE_EXECUTED=NO — text is treated as plain text data only.
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — G1/G2/G3 distance ≠ cutting path.
    ARC_AS_CHORD_APPROXIMATION=NO — arcs use exact analytic geometry.
    ARC_FALLBACK_TO_CHORD=NO — invalid/unsupported arcs mark PARTIAL; not measured.
    UNKNOWN_INITIAL_POSITION_GUESSED=NO — moves whose start is unknown are skipped.
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO — IJK relative-center only; no dialect claims.
    NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO — tool_id_raw is not catalog-matched.
    PRIVATE_PATH_IN_PATH_EVIDENCE=NO — never reads filesystem.
    """
    state = _ModalState(x=initial_x, y=initial_y, z=initial_z)

    # Global accumulators
    feed_mm = 0.0
    rapid_mm = 0.0
    supported_count = 0
    unsupported_count = 0
    unknown_start_count = 0
    tool_change_count = 0
    arc_motion_count = 0
    block_count = 0
    unsupported: list[str] = []
    limitations: list[str] = []
    last_feed_mm_min: float | None = None

    has_partial = False
    has_unsupported_semantics = False

    # Segment tracking
    tc_index = 0
    cur_seg = _SegState(segment_id="SEG_PREAMBLE", start_line=1)
    completed_segments: list[NcMotionSegment] = []

    def _add_unsupported(feat: str) -> None:
        nonlocal unsupported_count
        if feat not in unsupported:
            unsupported.append(feat)
            unsupported_count += 1

    lines = text.splitlines()
    if len(lines) > _MAX_LINES:
        return NcMotionResult(
            analysis_status=NcAnalysisStatus.INVALID_PROGRAM,
            limitations=[f"Program exceeds maximum line count ({_MAX_LINES})."],
            unsupported_features=["PROGRAM_TOO_LARGE"],
        )

    pending_t: int | None = None   # T word waiting for M6

    for raw_line_idx, raw_line in enumerate(lines):
        line_no = raw_line_idx + 1  # 1-indexed

        # Pre-scan macro constructs
        if _MACRO_VAR_RE.search(raw_line):
            has_unsupported_semantics = True
            cur_seg.has_unsupported_semantics = True
            _add_unsupported("MACRO_VARIABLE_DETECTED")
            _seg_add_unsupported(cur_seg, "MACRO_VARIABLE_DETECTED")

        if _FLOW_RE.search(raw_line):
            has_unsupported_semantics = True
            cur_seg.has_unsupported_semantics = True
            _add_unsupported("MACRO_CONTROL_FLOW_DETECTED")
            _seg_add_unsupported(cur_seg, "MACRO_CONTROL_FLOW_DETECTED")

        cleaned = _strip_comments(raw_line)
        if not cleaned or cleaned in ("%",):
            continue
        if _ONUM_RE.match(cleaned):
            continue

        block_count += 1
        words = _parse_words(cleaned)
        if not words:
            continue

        # Separate word types
        g_nums: list[int] = []
        m_nums: list[int] = []
        t_num: int | None = None
        new_x: float | None = None
        new_y: float | None = None
        new_z: float | None = None
        new_i: float | None = None
        new_j: float | None = None
        new_k: float | None = None
        new_r: float | None = None
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
            elif letter == "I":
                new_i = _mm(val, state)
            elif letter == "J":
                new_j = _mm(val, state)
            elif letter == "K":
                new_k = _mm(val, state)
            elif letter == "R":
                new_r = val
            elif letter == "F":
                new_f = val

        # Update units (before coord conversion)
        for gn in g_nums:
            if gn == 20:
                state.units = "inch"
                if new_x is not None:
                    new_x = new_x * _INCH_TO_MM
                if new_y is not None:
                    new_y = new_y * _INCH_TO_MM
                if new_z is not None:
                    new_z = new_z * _INCH_TO_MM
                if new_i is not None:
                    new_i = new_i * _INCH_TO_MM
                if new_j is not None:
                    new_j = new_j * _INCH_TO_MM
                if new_k is not None:
                    new_k = new_k * _INCH_TO_MM
            elif gn == 21:
                state.units = "mm"

        # Convert F word to mm/min
        if new_f is not None:
            if state.units == "inch":
                state.feed_mm_min = new_f * _INCH_TO_MM
            else:
                state.feed_mm_min = new_f
            last_feed_mm_min = state.feed_mm_min
            _seg_update_feed(cur_seg, state.feed_mm_min)

        # Process G codes
        this_line_motion: str | None = None
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
                state.motion = f"G{gn}"
                this_line_motion = f"G{gn}"
                this_line_arc = True
            elif gn in (17, 18, 19):
                state.plane = f"G{gn}"
            elif gn in (81, 82, 83, 84, 85, 86, 87, 88, 89):
                has_partial = True
                cur_seg.has_partial = True
                feat = f"G{gn}_CANNED_CYCLE_DETECTED"
                _add_unsupported(feat)
                _seg_add_unsupported(cur_seg, feat)
                state.motion = "CANNED"
                this_line_motion = "CANNED"
                this_line_canned = True
            elif gn == 90:
                state.positioning = "absolute"
            elif gn == 91:
                state.positioning = "incremental"
            elif gn == 28:
                state.x = state.y = state.z = None
                if "G28_REFERENCE_RETURN_DETECTED" not in limitations:
                    limitations.append(
                        "G28_REFERENCE_RETURN_DETECTED — machine position reset to unknown."
                    )
            elif gn in (41, 42):
                has_partial = True
                cur_seg.has_partial = True
                feat = f"G{gn}_CUTTER_RADIUS_COMP_DETECTED"
                _add_unsupported(feat)
                _seg_add_unsupported(cur_seg, feat)
            elif gn == 40:
                pass
            elif gn in (43, 44, 49):
                tag = f"G{gn}_TOOL_LENGTH_COMP_NOTED"
                if tag not in unsupported:
                    unsupported.append(tag)
            elif gn in (53, 54, 55, 56, 57, 58, 59):
                tag = f"G{gn}_WORK_OFFSET_NOTED"
                if tag not in unsupported:
                    unsupported.append(tag)
            elif gn == 92:
                if "G92_COORDINATE_SHIFT_NOTED" not in unsupported:
                    unsupported.append("G92_COORDINATE_SHIFT_NOTED")
            # All other G codes silently ignored

        # Process M codes
        for mn in m_nums:
            if mn == 6:
                if pending_t is not None or t_num is not None:
                    tool_change_count += 1
                    raw_tid = str(t_num if t_num is not None else pending_t)
                    # Close current segment
                    completed_segments.append(_finalize_segment(cur_seg, line_no))
                    # Open next segment
                    tc_index += 1
                    cur_seg = _SegState(
                        segment_id=f"SEG_TC{tc_index}",
                        start_line=line_no,
                        tool_id_raw=raw_tid,
                    )
                    pending_t = None  # reset after M6 fires
            elif mn == 98:
                has_unsupported_semantics = True
                cur_seg.has_unsupported_semantics = True
                _add_unsupported("M98_SUBPROGRAM_UNSUPPORTED")
                _seg_add_unsupported(cur_seg, "M98_SUBPROGRAM_UNSUPPORTED")
            elif mn == 99:
                has_unsupported_semantics = True
                cur_seg.has_unsupported_semantics = True
                _add_unsupported("M99_SUBPROGRAM_UNSUPPORTED")
                _seg_add_unsupported(cur_seg, "M99_SUBPROGRAM_UNSUPPORTED")
            elif mn in (2, 30):
                this_line_end = True

        # Track T word for next M6
        if t_num is not None:
            pending_t = t_num

        # Compute motion distance
        has_coords = new_x is not None or new_y is not None or new_z is not None
        active_motion = this_line_motion if this_line_motion else state.motion

        linear_move = (
            active_motion in ("G0", "G1")
            and not this_line_arc
            and not this_line_canned
        )

        if has_coords and linear_move:
            dist = _compute_distance(state, new_x, new_y, new_z)
            _update_position(state, new_x, new_y, new_z)

            if dist is None:
                unknown_start_count += 1
                has_partial = True
                cur_seg.has_partial = True
                feat = "UNKNOWN_INITIAL_POSITION_FOR_SOME_MOVES"
                if feat not in unsupported:
                    unsupported.append(feat)
                _seg_add_unsupported(cur_seg, feat)
            else:
                supported_count += 1
                cur_seg.linear_count += 1
                if active_motion == "G0":
                    rapid_mm += dist
                    cur_seg.rapid_mm += dist
                else:
                    feed_mm += dist
                    cur_seg.feed_mm += dist

        elif has_coords and active_motion in ("G2", "G3") and this_line_arc:
            gn_arc = 2 if active_motion == "G2" else 3

            # R-format: deferred
            if new_r is not None and new_i is None and new_j is None and new_k is None:
                has_partial = True
                cur_seg.has_partial = True
                feat = f"G{gn_arc}_R_FORMAT_DEFERRED"
                _add_unsupported(feat)
                _seg_add_unsupported(cur_seg, feat)
                _update_position(state, new_x, new_y, new_z)

            else:
                dist, err, helix_lim = _compute_arc_distance(
                    state, gn_arc, new_x, new_y, new_z,
                    new_i, new_j, new_k,
                )
                _update_position(state, new_x, new_y, new_z)

                if err is not None:
                    has_partial = True
                    cur_seg.has_partial = True
                    _add_unsupported(err)
                    _seg_add_unsupported(cur_seg, err)
                else:
                    assert dist is not None
                    supported_count += 1
                    arc_motion_count += 1
                    feed_mm += dist
                    cur_seg.arc_count += 1
                    cur_seg.feed_mm += dist

                    if helix_lim is not None:
                        if helix_lim not in limitations:
                            limitations.append(helix_lim)

        elif active_motion in ("G2", "G3") and not has_coords and this_line_arc:
            # G2/G3 block with no endpoint coordinates (e.g. only I/J/K)
            # Treat as modal continuation with same endpoint as start → zero-distance arc
            # or as invalid. Keep PARTIAL.
            has_partial = True
            cur_seg.has_partial = True
            feat = f"G{2 if active_motion == 'G2' else 3}_ARC_NO_ENDPOINT"
            _add_unsupported(feat)
            _seg_add_unsupported(cur_seg, feat)

        elif has_coords and active_motion == "CANNED":
            _update_position(state, new_x, new_y, new_z)

        elif has_coords and active_motion in ("G2", "G3") and not this_line_arc:
            # Modal arc continuation (no G word on this block, state.motion is G2/G3)
            gn_arc = 2 if active_motion == "G2" else 3

            if new_r is not None and new_i is None and new_j is None and new_k is None:
                has_partial = True
                cur_seg.has_partial = True
                feat = f"G{gn_arc}_R_FORMAT_DEFERRED"
                _add_unsupported(feat)
                _seg_add_unsupported(cur_seg, feat)
                _update_position(state, new_x, new_y, new_z)
            else:
                dist, err, helix_lim = _compute_arc_distance(
                    state, gn_arc, new_x, new_y, new_z,
                    new_i, new_j, new_k,
                )
                _update_position(state, new_x, new_y, new_z)

                if err is not None:
                    has_partial = True
                    cur_seg.has_partial = True
                    _add_unsupported(err)
                    _seg_add_unsupported(cur_seg, err)
                else:
                    assert dist is not None
                    supported_count += 1
                    arc_motion_count += 1
                    feed_mm += dist
                    cur_seg.arc_count += 1
                    cur_seg.feed_mm += dist

                    if helix_lim is not None:
                        if helix_lim not in limitations:
                            limitations.append(helix_lim)

        if this_line_end:
            break

    # Close final open segment
    final_line = len(lines)
    completed_segments.append(_finalize_segment(cur_seg, final_line))

    # Final status
    if block_count == 0:
        status = NcAnalysisStatus.INVALID_PROGRAM
    elif has_unsupported_semantics:
        status = NcAnalysisStatus.UNSUPPORTED_SEMANTICS
    elif has_partial:
        status = NcAnalysisStatus.PARTIAL
    elif supported_count == 0 and unknown_start_count == 0:
        status = NcAnalysisStatus.INSUFFICIENT_DATA
    else:
        status = NcAnalysisStatus.COMPLETE

    # Build limitations
    limitations.append(
        "NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — G1/G2/G3 motion does not confirm "
        "material engagement. feed_distance_mm is NC commanded feed path."
    )
    limitations.append(
        f"PARSER_PROFILE={PARSER_PROFILE} — dialect-specific semantics not validated."
    )
    if any("ARC" in f and "DEFERRED" in f for f in unsupported):
        limitations.append(
            "R_FORMAT_ARC_DEFERRED — G2/G3 R-format arcs not measured. "
            "Use IJK relative-center for analytic arc distance. ARC_FALLBACK_TO_CHORD=NO."
        )
    if any("ARC" in f and "DEFERRED" not in f and "HELICAL" not in f
           for f in unsupported):
        if not any("R_FORMAT_ARC_DEFERRED" in lim for lim in limitations):
            limitations.append(
                "ARC_MOTION_PARTIAL — some G2/G3 arcs could not be measured. "
                "ARC_AS_CHORD_APPROXIMATION=NO."
            )
    if any("CANNED" in f for f in unsupported):
        limitations.append(
            "CANNED_CYCLE_DETECTED — G81-G89 not expanded; axial path not counted."
        )
    if any("M98" in f or "M99" in f for f in unsupported):
        limitations.append(
            "SUBPROGRAM_DETECTED — M98/M99 found; repeated segments may be missing."
        )
    if any("MACRO" in f for f in unsupported):
        limitations.append(
            "MACRO_DETECTED — # variables or WHILE/IF found; conditional path not evaluated."
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
        arc_motion_count=arc_motion_count,
        nc_commanded_feed_mm_min=(
            round(last_feed_mm_min, 4) if last_feed_mm_min is not None else None
        ),
        unsupported_features=unsupported,
        limitations=limitations,
        segments=completed_segments,
        nc_feed_move_equals_confirmed_cutting=False,
        arc_chord_approximation_used=False,
        nc_file_executed=False,
    )
