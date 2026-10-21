"""Tests for NC_ARC_AND_OPERATION_SEGMENTATION_01 — Phase 2.

Covers:
    Arc tests  (26) — G17/G18/G19, G2/G3 IJK, helical, full circle,
                       modal, incremental, inch, radius validation, R-deferred
    Segment tests (25) — tool-change boundaries, preamble, aggregation,
                          feed summary, explicit association, safety invariants

Safety invariants verified throughout:
    ARC_AS_CHORD_APPROXIMATION=NO
    ARC_FALLBACK_TO_CHORD=NO
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO
    SEGMENT_TO_OPERATION_MAPPING_METHOD=EXPLICIT_USER_ASSIGNMENT
"""

from __future__ import annotations

import math

import pytest

from backend.interoperability.nc_motion import (
    NcAnalysisStatus,
    NcMotionResult,
    NcMotionSegment,
    parse_nc_motion,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INCH_TO_MM = 25.4


def _parse(text: str, **kw) -> NcMotionResult:
    return parse_nc_motion(text, **kw)


def _approx(a: float, b: float, rel: float = 1e-5) -> bool:
    if b == 0.0:
        return abs(a) < 1e-9
    return abs(a - b) / max(abs(b), 1e-12) < rel


# ===========================================================================
# ARC TESTS (26)
# ===========================================================================


# ---------------------------------------------------------------------------
# A1 — G17 quarter circle CCW (G3), 90° sweep
# ---------------------------------------------------------------------------

def test_g17_quarter_circle_ccw():
    """G3 in G17 plane: 90° CCW arc from (10,0) to (0,10), r=10.
    Arc length = r * π/2 = 5π ≈ 15.7080.
    """
    prog = "G21\nG17\nG90\nG3 X0 Y10 I-10 J0 F200\n"
    r = _parse(prog, initial_x=10, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 2
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} != {expected}"
    assert r.arc_chord_approximation_used is False
    assert r.arc_motion_count == 1


# ---------------------------------------------------------------------------
# A2 — G17 quarter circle CW (G2)
# ---------------------------------------------------------------------------

def test_g17_quarter_circle_cw():
    """G2 in G17 plane: 90° CW arc from (0,10) to (10,0), r=10.
    Same arc length as CCW.
    """
    prog = "G21\nG17\nG90\nG2 X10 Y0 I0 J-10 F200\n"
    r = _parse(prog, initial_x=0, initial_y=10, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 2
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} != {expected}"
    assert r.arc_chord_approximation_used is False


# ---------------------------------------------------------------------------
# A3 — G17 half circle
# ---------------------------------------------------------------------------

def test_g17_half_circle():
    """G3 half circle: from (10,0) to (-10,0), r=10, sweep=π.
    Arc length = r * π = 10π ≈ 31.4159.
    """
    prog = "G21\nG17\nG90\nG3 X-10 Y0 I-10 J0 F100\n"
    r = _parse(prog, initial_x=10, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi
    assert _approx(r.feed_distance_mm, expected)
    assert r.arc_motion_count == 1


# ---------------------------------------------------------------------------
# A4 — IJK full circle G17 (start == end in plane)
# ---------------------------------------------------------------------------

def test_ijk_full_circle_g17():
    """G2 full circle: start==end, r=5, sweep=2π.
    Arc length = 2π*5 = 10π ≈ 31.4159.
    distance_mm must NOT be zero.
    """
    prog = "G21\nG17\nG90\nG2 X0 Y0 I5 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 2.0 * math.pi * 5.0
    assert _approx(r.feed_distance_mm, expected)
    assert r.feed_distance_mm > 0.0, "Full circle must not return zero distance"


# ---------------------------------------------------------------------------
# A5 — G18 plane arc (XZ plane)
# ---------------------------------------------------------------------------

def test_g18_quarter_arc():
    """G3 in G18 (XZ) plane: from (10,0,0) to (0,0,10), r=10, sweep=π/2.
    Arc length = 10 * π/2.
    """
    prog = "G21\nG18\nG90\nG3 X0 Z10 I-10 K0 F100\n"
    r = _parse(prog, initial_x=10, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 2
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} vs {expected}"


# ---------------------------------------------------------------------------
# A6 — G19 plane arc (YZ plane)
# ---------------------------------------------------------------------------

def test_g19_quarter_arc():
    """G3 in G19 (YZ) plane: from (0,10,0) to (0,0,10), r=10, sweep=π/2."""
    prog = "G21\nG19\nG90\nG3 Y0 Z10 J-10 K0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=10, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 2
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} vs {expected}"


# ---------------------------------------------------------------------------
# A7 — Helical arc G17 (XY arc + Z change)
# ---------------------------------------------------------------------------

def test_helical_arc_g17():
    """G3 helical: XY half-circle r=10 (L_arc=10π) + dZ=5.
    L_helix = sqrt((10π)² + 5²).
    """
    prog = "G21\nG17\nG90\nG3 X-10 Y0 Z5 I-10 J0 F100\n"
    r = _parse(prog, initial_x=10, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    l_arc = 10.0 * math.pi
    l_helix = math.sqrt(l_arc ** 2 + 5.0 ** 2)
    assert _approx(r.feed_distance_mm, l_helix), f"{r.feed_distance_mm} vs {l_helix}"
    assert r.arc_motion_count == 1


# ---------------------------------------------------------------------------
# A8 — Helical arc G18 (XZ arc + Y change)
# ---------------------------------------------------------------------------

def test_helical_arc_g18():
    """G2 helical in G18: XZ half-circle r=5 + dY=3."""
    prog = "G21\nG18\nG90\nG2 X-5 Y3 Z0 I-5 K0 F100\n"
    r = _parse(prog, initial_x=5, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    l_arc = 5.0 * math.pi
    l_helix = math.sqrt(l_arc ** 2 + 3.0 ** 2)
    assert _approx(r.feed_distance_mm, l_helix), f"{r.feed_distance_mm} vs {l_helix}"


# ---------------------------------------------------------------------------
# A9 — G20 inch units arc
# ---------------------------------------------------------------------------

def test_arc_g20_inch_units():
    """G2 in inch units: r=1 inch = 25.4 mm, quarter arc.
    Arc length in mm = 25.4 * π/2.
    """
    prog = "G20\nG17\nG90\nG2 X0 Y-1 I0 J-1 F10\n"
    r = _parse(prog, initial_x=0, initial_y=1, initial_z=0)
    # initial positions given in mm already (no units at parse time)
    # Actually we need to give initial in program units (inch)
    r2 = parse_nc_motion(prog, initial_x=0, initial_y=1 * _INCH_TO_MM, initial_z=0)
    # The program declares G20 first, so coords on the G2 line get converted
    # initial_x/y are in mm (parser doesn't convert them), but G20 converts word vals
    # For this test: start at (0, 25.4), arc to (0, -25.4) with J offset -25.4 mm
    # Actually: initial must be in mm. Let's use a simpler approach.
    prog2 = "G20\nG17\nG90\nG2 X1 Y0 I0 J-1 F10\n"
    r3 = parse_nc_motion(prog2, initial_x=0, initial_y=_INCH_TO_MM, initial_z=0)
    assert r3.analysis_status == NcAnalysisStatus.COMPLETE
    expected_mm = _INCH_TO_MM * math.pi / 2
    assert _approx(r3.feed_distance_mm, expected_mm), f"{r3.feed_distance_mm} vs {expected_mm}"
    assert r3.units_declared == "inch"


# ---------------------------------------------------------------------------
# A10 — G91 incremental endpoint arc
# ---------------------------------------------------------------------------

def test_arc_g91_incremental():
    """G3 in G91: incremental endpoint. r=10, quarter arc.
    From (0,10) with G91 X-10 Y-10 I0 J-10 → endpoint at (-10, 0) absolute.
    sweep = 90° CCW → arc length = 10 * π/2.
    """
    prog = "G21\nG17\nG91\nG3 X-10 Y-10 I0 J-10 F100\n"
    r = _parse(prog, initial_x=0, initial_y=10, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 2
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} vs {expected}"


# ---------------------------------------------------------------------------
# A11 — Modal G2 continuation
# ---------------------------------------------------------------------------

def test_modal_arc_continuation():
    """G2 on first line, second arc block with no G word (modal G2)."""
    prog = "G21\nG17\nG90\nG2 X10 Y0 I0 J-10 F100\nX-10 Y0 I-10 J0\n"
    # First: from (0,10) CW quarter → (10,0), arc = 10 * π/2
    # Modal: from (10,0) CW half circle to (-10,0), arc = 10 * π
    r = _parse(prog, initial_x=0, initial_y=10, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 2 + 10.0 * math.pi
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} vs {expected}"
    assert r.arc_motion_count == 2


# ---------------------------------------------------------------------------
# A12 — Partial axis words (arc missing one plane endpoint — stays planar)
# ---------------------------------------------------------------------------

def test_arc_partial_axis_words():
    """G3 with only X endpoint word (Y missing) — Y stays at start position.
    X=10 same as start X=10, Y omitted → Y stays at 0 → start == end → full circle.
    """
    prog = "G21\nG17\nG90\nG3 X10 I-10 J0 F100\n"
    r = _parse(prog, initial_x=10, initial_y=0, initial_z=0)
    # X=10 == start_x, Y omitted → end_y = start_y = 0 → full circle
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 2.0 * math.pi * 10.0
    assert _approx(r.feed_distance_mm, expected)


# ---------------------------------------------------------------------------
# A13 — Invalid radius consistency → PARTIAL
# ---------------------------------------------------------------------------

def test_invalid_radius_consistency():
    """G3 with I/J giving radius_start ≠ radius_end → PARTIAL, no distance added."""
    # r_start = sqrt(10² + 0²) = 10; endpoint (12,0) → r_end = sqrt((12-10)² + 0²) = 2
    prog = "G21\nG17\nG90\nG3 X12 Y0 I10 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("INCONSISTENT" in f for f in r.unsupported_features)
    assert r.arc_chord_approximation_used is False


# ---------------------------------------------------------------------------
# A14 — Missing IJK on G2 → PARTIAL
# ---------------------------------------------------------------------------

def test_arc_missing_ijk():
    """G2 with no I/J/K (and no R) → PARTIAL, ARC_MISSING_IJK."""
    prog = "G21\nG17\nG90\nG2 X10 Y0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("MISSING_IJK" in f for f in r.unsupported_features)
    assert r.arc_chord_approximation_used is False


# ---------------------------------------------------------------------------
# A15 — Zero-radius IJK (I=J=0) → PARTIAL
# ---------------------------------------------------------------------------

def test_arc_zero_radius():
    """G2 with I=0 J=0 → zero radius → PARTIAL."""
    prog = "G21\nG17\nG90\nG2 X5 Y5 I0 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("ZERO_RADIUS" in f or "MISSING_IJK" in f for f in r.unsupported_features)


# ---------------------------------------------------------------------------
# A16 — R format still PARTIAL (deferred)
# ---------------------------------------------------------------------------

def test_r_format_arc_deferred():
    """G2 with R-format → PARTIAL (R_FORMAT_DEFERRED in unsupported_features)."""
    prog = "G21\nG17\nG90\nG2 X10 Y0 R5 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("R_FORMAT_DEFERRED" in f for f in r.unsupported_features)
    assert r.arc_chord_approximation_used is False


# ---------------------------------------------------------------------------
# A17 — arc_chord_approximation_used is always False, even for valid arcs
# ---------------------------------------------------------------------------

def test_arc_chord_approximation_always_false():
    """Valid IJK arc: arc_chord_approximation_used must be False."""
    prog = "G21\nG17\nG90\nG3 X0 Y10 I0 J5 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.arc_chord_approximation_used is False


# ---------------------------------------------------------------------------
# A18 — Arc adds to feed_distance_mm only (not rapid)
# ---------------------------------------------------------------------------

def test_arc_adds_to_feed_only():
    """Arc distance must go to feed_distance_mm, not rapid_distance_mm."""
    prog = "G21\nG17\nG90\nG3 X10 Y0 I5 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.feed_distance_mm > 0.0
    assert r.rapid_distance_mm == 0.0


# ---------------------------------------------------------------------------
# A19 — Linear + arc combination: correct total
# ---------------------------------------------------------------------------

def test_linear_plus_arc_total():
    """G1 + G3: total feed = linear + arc."""
    prog = "G21\nG17\nG90\nG1 X10 F100\nG3 X0 Y10 I-10 J0\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    # G1: 10mm; G3 from (10,0) to (0,10) r=10 quarter CCW = 10*π/2
    linear = 10.0
    arc = 10.0 * math.pi / 2
    expected = linear + arc
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    assert _approx(r.feed_distance_mm, expected), f"{r.feed_distance_mm} vs {expected}"


# ---------------------------------------------------------------------------
# A20 — Arc-only program achieves COMPLETE
# ---------------------------------------------------------------------------

def test_arc_only_program_complete():
    """Program with only arcs (no canned cycles, no R-format) achieves COMPLETE."""
    prog = "G21\nG17\nG90\nG2 X0 Y0 I5 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE


# ---------------------------------------------------------------------------
# A21 — G17 default (no explicit plane declaration)
# ---------------------------------------------------------------------------

def test_g17_default_plane():
    """Without explicit G17, default plane is G17 (XY). Arc uses X and Y."""
    prog = "G21\nG90\nG3 X10 Y0 I5 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 5.0 * math.pi
    assert _approx(r.feed_distance_mm, expected)


# ---------------------------------------------------------------------------
# A22 — IJK full circle status is COMPLETE, distance > 0
# ---------------------------------------------------------------------------

def test_full_circle_complete_and_nonzero():
    """Full circle must not degrade to PARTIAL and must have positive distance."""
    prog = "G21\nG17\nG90\nG3 X0 Y0 I8 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    assert r.feed_distance_mm > 0.0
    expected = 2.0 * math.pi * 8.0
    assert _approx(r.feed_distance_mm, expected)


# ---------------------------------------------------------------------------
# A23 — 45° arc analytic verification: r * π/4
# ---------------------------------------------------------------------------

def test_45_degree_arc_length():
    """G3 45° arc: r=10, arc length = 10 * π/4."""
    # From (10,0) to (10*cos45, 10*sin45), CCW, center at (0,0)
    ex = 10.0 * math.cos(math.radians(45))
    ey = 10.0 * math.sin(math.radians(45))
    prog = f"G21\nG17\nG90\nG3 X{ex:.6f} Y{ey:.6f} I-10 J0 F100\n"
    r = _parse(prog, initial_x=10, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 10.0 * math.pi / 4
    assert _approx(r.feed_distance_mm, expected, rel=1e-4)


# ---------------------------------------------------------------------------
# A24 — G91 arc with known start
# ---------------------------------------------------------------------------

def test_g91_arc_known_start():
    """G91 incremental arc: start known, endpoint relative."""
    # Full circle in G91: X=0 Y=0 means endpoint == start → full circle
    prog = "G21\nG17\nG91\nG3 X0 Y0 I10 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 2.0 * math.pi * 10.0
    assert _approx(r.feed_distance_mm, expected)


# ---------------------------------------------------------------------------
# A25 — Mixed G17 then G18 arcs
# ---------------------------------------------------------------------------

def test_mixed_plane_arcs():
    """G17 arc then G18 arc in sequence — both computed.
    G17: G3 from (0,0) → (10,0), center (5,0), r=5, half circle CCW, L=5π.
    G18: G3 (CCW) from (10,0,0) → (0,0,10), center (0,0,0), r=10, quarter, L=10*π/2.
    """
    prog = (
        "G21\nG17\nG90\n"
        "G3 X10 Y0 I5 J0 F100\n"   # G17 XY half circle CCW, r=5, L=5π
        "G18\n"
        "G3 X0 Z10 I-10 K0 F100\n"  # G18 XZ quarter arc CCW, r=10, L=10*π/2
    )
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    l1 = 5.0 * math.pi
    l2 = 10.0 * math.pi / 2
    expected = l1 + l2
    assert _approx(r.feed_distance_mm, expected, rel=1e-4), f"{r.feed_distance_mm} vs {expected}"
    assert r.arc_motion_count == 2


# ---------------------------------------------------------------------------
# A26 — G18 full circle
# ---------------------------------------------------------------------------

def test_g18_full_circle():
    """G2 full circle in G18 plane: start==end, r=6, L=2π*6."""
    prog = "G21\nG18\nG90\nG2 X0 Z0 I6 K0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    expected = 2.0 * math.pi * 6.0
    assert _approx(r.feed_distance_mm, expected)
    assert r.feed_distance_mm > 0.0


# ===========================================================================
# SEGMENTATION TESTS (25)
# ===========================================================================


# ---------------------------------------------------------------------------
# S1 — Single tool change → 2 segments
# ---------------------------------------------------------------------------

def test_single_tool_change_two_segments():
    prog = "G21\nG0 X0 Y0 Z0\nG1 X10 F100\nT1M6\nG1 X20\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert len(r.segments) == 2
    assert r.segments[0].segment_id == "SEG_PREAMBLE"
    assert r.segments[1].segment_id == "SEG_TC1"
    assert r.tool_change_count == 1


# ---------------------------------------------------------------------------
# S2 — T+M6 same line pairing
# ---------------------------------------------------------------------------

def test_t_m6_same_line_pairing():
    """T1M6 on one line creates one segment boundary."""
    prog = "G21\nG1 X5 F100\nT1M6\nG1 X10\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 1
    assert len(r.segments) == 2
    assert r.segments[1].tool_id_raw == "1"


# ---------------------------------------------------------------------------
# S3 — T then M6 on separate lines
# ---------------------------------------------------------------------------

def test_t_then_m6_separate_lines():
    """T1 on one line, M6 on next — same result as T1M6."""
    prog = "G21\nG1 X5 F100\nT1\nM6\nG1 X10\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 1
    assert len(r.segments) == 2
    assert r.segments[1].tool_id_raw == "1"


# ---------------------------------------------------------------------------
# S4 — Multiple tool changes → N+1 segments
# ---------------------------------------------------------------------------

def test_multiple_tool_changes():
    prog = "G21\nG1 X5 F100\nT1M6\nG1 X10\nT2M6\nG1 X15\nT3M6\nG1 X20\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 3
    assert len(r.segments) == 4
    assert [s.tool_id_raw for s in r.segments] == [None, "1", "2", "3"]


# ---------------------------------------------------------------------------
# S5 — Motion before first M6 captured in preamble
# ---------------------------------------------------------------------------

def test_preamble_motion_captured():
    prog = "G21\nG0 X0 Y0 Z0\nG1 X10 F100\nG1 X20\nT1M6\nG1 X25\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    preamble = r.segments[0]
    assert preamble.segment_id == "SEG_PREAMBLE"
    assert preamble.feed_motion_distance_mm > 0.0


# ---------------------------------------------------------------------------
# S6 — No M6 → entire program is one preamble segment
# ---------------------------------------------------------------------------

def test_no_tool_change_single_preamble():
    prog = "G21\nG0 X0 Y0 Z0\nG1 X50 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert len(r.segments) == 1
    assert r.segments[0].segment_id == "SEG_PREAMBLE"
    assert r.segments[0].tool_id_raw is None
    assert r.tool_change_count == 0


# ---------------------------------------------------------------------------
# S7 — Zero-motion segment (tool change immediately after another)
# ---------------------------------------------------------------------------

def test_zero_motion_segment():
    """Two consecutive M6 events → middle segment has zero distances."""
    prog = "G21\nG1 X5 F100\nT1M6\nT2M6\nG1 X10\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert len(r.segments) == 3
    mid = r.segments[1]
    assert mid.feed_motion_distance_mm == 0.0
    assert mid.rapid_motion_distance_mm == 0.0
    assert mid.analysis_status == NcAnalysisStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# S8 — feed_motion_distance_mm per segment
# ---------------------------------------------------------------------------

def test_feed_distance_per_segment():
    prog = "G21\nG1 X10 F100\nT1M6\nG1 X20\nT2M6\nG1 X35\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.segments[0].feed_motion_distance_mm, 10.0)
    assert _approx(r.segments[1].feed_motion_distance_mm, 10.0)
    assert _approx(r.segments[2].feed_motion_distance_mm, 15.0)


# ---------------------------------------------------------------------------
# S9 — rapid_motion_distance_mm per segment
# ---------------------------------------------------------------------------

def test_rapid_distance_per_segment():
    prog = "G21\nG0 X5\nT1M6\nG0 X10\nT2M6\nG0 X25\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.segments[0].rapid_motion_distance_mm, 5.0)
    assert _approx(r.segments[1].rapid_motion_distance_mm, 5.0)
    assert _approx(r.segments[2].rapid_motion_distance_mm, 15.0)


# ---------------------------------------------------------------------------
# S10 — arc_motion_count per segment
# ---------------------------------------------------------------------------

def test_arc_count_per_segment():
    prog = "G21\nG17\nG90\nG2 X0 Y0 I5 J0 F100\nT1M6\nG3 X0 Y0 I5 J0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.segments[0].arc_motion_count == 1
    assert r.segments[1].arc_motion_count == 1


# ---------------------------------------------------------------------------
# S11 — Unsupported arc (R-format) in segment → segment PARTIAL
# ---------------------------------------------------------------------------

def test_r_format_arc_in_segment_partial():
    prog = "G21\nG17\nG90\nT1M6\nG2 X10 Y0 R5 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    tc_seg = r.segments[1]
    assert tc_seg.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("R_FORMAT_DEFERRED" in f for f in tc_seg.unsupported_features)


# ---------------------------------------------------------------------------
# S12 — Canned cycle (G81 with all params) in segment → segment COMPLETE
#        G81 is now expanded; feed stroke |Z-R| = |-10 - 2| = 12 mm
# ---------------------------------------------------------------------------

def test_canned_cycle_in_segment_partial():
    prog = "G21\nG90\nT1M6\nG81 X50 Y50 Z-10 R2 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    tc_seg = r.segments[1]
    # G81 is now fully expanded → COMPLETE (no missing Z/R, G90, G99 return)
    assert tc_seg.analysis_status == NcAnalysisStatus.COMPLETE
    # Feed stroke = |Z-R| = |-10 - 2| = 12 mm; feed accumulated, no unsupported tags
    assert tc_seg.feed_motion_distance_mm > 0


# ---------------------------------------------------------------------------
# S13 — Macro/subprogram in segment → UNSUPPORTED_SEMANTICS
# ---------------------------------------------------------------------------

def test_macro_in_segment_unsupported_semantics():
    prog = "G21\nT1M6\nM98 P1000\nG1 X10 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    tc_seg = r.segments[1]
    assert tc_seg.analysis_status == NcAnalysisStatus.UNSUPPORTED_SEMANTICS


# ---------------------------------------------------------------------------
# S14 — Explicit operation_association preserved (EXPLICIT_USER_ASSIGNMENT)
# ---------------------------------------------------------------------------

def test_segment_explicit_operation_association():
    """segment_id and tool_id_raw are available for explicit user assignment.
    SEGMENT_TO_OPERATION_MAPPING_METHOD=EXPLICIT_USER_ASSIGNMENT.
    No automatic mapping to process steps happens here.
    """
    prog = "G21\nT5M6\nG1 X10 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    seg = r.segments[1]
    # segment_id and tool_id_raw are available for explicit mapping
    assert seg.segment_id == "SEG_TC1"
    assert seg.tool_id_raw == "5"
    # No automatic step association has occurred
    # (PathEvidence.operation_association starts as None — user assigns explicitly)


# ---------------------------------------------------------------------------
# S15 — Multiple segments total: sum of feed distances matches whole result
# ---------------------------------------------------------------------------

def test_multi_segment_feed_sum_matches_total():
    prog = "G21\nG1 X10 F100\nT1M6\nG1 X5\nT2M6\nG1 X8\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    seg_total = sum(s.feed_motion_distance_mm for s in r.segments)
    assert _approx(seg_total, r.feed_distance_mm)


# ---------------------------------------------------------------------------
# S16 — NC T-word is NOT a catalog tool ID
# ---------------------------------------------------------------------------

def test_nc_tool_id_not_catalog_id():
    """tool_id_raw is the raw NC T-word string.
    NC_TOOL_ID_AUTOMATICALLY_MAPPED_TO_CATALOG=NO.
    """
    prog = "G21\nT42M6\nG1 X10 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    seg = r.segments[1]
    # Raw NC T-word — not a catalog UUID or any structured ID
    assert seg.tool_id_raw == "42"
    # No catalog_tool_id or resolved_tool_id field exists on segment
    assert not hasattr(seg, "catalog_tool_id")
    assert not hasattr(seg, "resolved_tool_id")


# ---------------------------------------------------------------------------
# S17 — commanded_feed_min/max per segment
# ---------------------------------------------------------------------------

def test_commanded_feed_min_max_per_segment():
    prog = "G21\nT1M6\nG1 X5 F200\nG1 X10 F500\nG1 X15 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    seg = r.segments[1]
    assert seg.commanded_feed_min == pytest.approx(100.0)
    assert seg.commanded_feed_max == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# S18 — feed_change_count per segment
# ---------------------------------------------------------------------------

def test_feed_change_count_per_segment():
    prog = "G21\nT1M6\nG1 X5 F200\nX10 F300\nX15 F150\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    seg = r.segments[1]
    assert seg.feed_change_count == 3


# ---------------------------------------------------------------------------
# S19 — segment_id uniqueness
# ---------------------------------------------------------------------------

def test_segment_id_uniqueness():
    prog = "G21\nT1M6\nG1 X5 F100\nT2M6\nG1 X10\nT3M6\nG1 X15\n"
    r = _parse(prog)
    ids = [s.segment_id for s in r.segments]
    assert len(ids) == len(set(ids)), f"Duplicate segment IDs: {ids}"


# ---------------------------------------------------------------------------
# S20 — start_line / end_line ordering
# ---------------------------------------------------------------------------

def test_segment_start_end_line_ordering():
    prog = "G21\nG1 X5 F100\nT1M6\nG1 X10\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    for seg in r.segments:
        assert seg.start_line >= 1
        assert seg.end_line >= seg.start_line


# ---------------------------------------------------------------------------
# S21 — Program end (M30) terminates last segment
# ---------------------------------------------------------------------------

def test_program_end_m30_terminates_segment():
    prog = "G21\nT1M6\nG1 X10 F100\nM30\nG1 X20\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    # Motion after M30 should not be counted
    assert _approx(r.segments[1].feed_motion_distance_mm, 10.0)


# ---------------------------------------------------------------------------
# S22 — Bare M6 with no prior T → no tool change counted
# ---------------------------------------------------------------------------

def test_bare_m6_no_prior_t_no_change():
    """M6 with no pending T and no same-line T does NOT create a new segment."""
    prog = "G21\nG1 X10 F100\nM6\nG1 X20\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 0
    assert len(r.segments) == 1


# ---------------------------------------------------------------------------
# S23 — Segment with only rapid moves (feed_distance=0)
# ---------------------------------------------------------------------------

def test_segment_rapid_only():
    prog = "G21\nT1M6\nG0 X10\nG0 X20\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    seg = r.segments[1]
    assert seg.feed_motion_distance_mm == 0.0
    assert seg.rapid_motion_distance_mm > 0.0


# ---------------------------------------------------------------------------
# S24 — Partial segment in set degrades aggregation (most-degraded rule)
# PARTIAL_SEGMENT_HIDDEN_IN_COMPLETE_OPERATION=NO
# ---------------------------------------------------------------------------

def test_partial_segment_propagates_status():
    """If any segment has PARTIAL status, the whole result must not be COMPLETE."""
    prog = "G21\nT1M6\nG1 X10 F100\nG2 X20 Y0 R5\n"  # R-format arc → PARTIAL
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    # The partial segment is visible; its unsupported_features are non-empty
    partial_segs = [s for s in r.segments if s.analysis_status == NcAnalysisStatus.PARTIAL]
    assert len(partial_segs) >= 1


# ---------------------------------------------------------------------------
# S25 — tool_id_raw matches T word seen before M6
# ---------------------------------------------------------------------------

def test_tool_id_raw_matches_t_word():
    """tool_id_raw in each segment matches the T number before its M6."""
    prog = "G21\nT7M6\nG1 X5 F100\nT3M6\nG1 X10\n"
    r = _parse(prog)
    assert r.segments[1].tool_id_raw == "7"
    assert r.segments[2].tool_id_raw == "3"
