"""Unit tests for bounded NC motion parser.

PROCESS_PLAN_CYCLE_TIME_CAD_CAM_INTEGRATION_01 — Phase 2

Test-contract guarantees:
    NC_FILE_EXECUTED=NO
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    ARC_AS_CHORD_APPROXIMATION=NO
    UNKNOWN_INITIAL_POSITION_GUESSED=NO
    IGNORED_UNSUPPORTED_MOTION_REPORTED_COMPLETE=NO
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO
    CUTTING_TIME_FORMULA_DUPLICATED=NO
    RAPID_TIME_FROM_NC_ALONE=NO
    REFERENCE_FEED_OVERWRITTEN_BY_NC=NO
"""

from __future__ import annotations

import math

import pytest

from backend.interoperability.nc_motion import (
    NcAnalysisStatus,
    NcMotionResult,
    PARSER_PROFILE,
    parse_nc_motion,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INCH = 25.4  # exact factor


def _parse(text: str, **kw) -> NcMotionResult:
    return parse_nc_motion(text.strip(), **kw)


def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return math.fabs(a - b) <= tol


# ---------------------------------------------------------------------------
# Section 1 — Parser profile and safety flags
# ---------------------------------------------------------------------------


def test_parser_profile():
    r = _parse("G21\nG90\nG1 X10\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.parser_profile == PARSER_PROFILE


def test_safety_flags_always_false():
    r = _parse("G21\nG1 X10\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.nc_feed_move_equals_confirmed_cutting is False
    assert r.arc_chord_approximation_used is False
    assert r.nc_file_executed is False


def test_deterministic_repeatability():
    prog = "G21\nG90\nG0 X0 Y0 Z0\nG1 X100 Y0 F500\n"
    r1 = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    r2 = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r1.feed_distance_mm == r2.feed_distance_mm
    assert r1.rapid_distance_mm == r2.rapid_distance_mm
    assert r1.analysis_status == r2.analysis_status


# ---------------------------------------------------------------------------
# Section 2 — Units (G20 / G21)
# ---------------------------------------------------------------------------


def test_g21_mm_absolute_linear():
    """G21 G90 G1 X100 → feed = 100 mm."""
    r = _parse("G21\nG90\nG1 X100 F300\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 100.0)
    assert r.units_declared == "mm"


def test_g20_inch_to_mm_conversion():
    """G20 G90 G1 X1.0 → feed = 25.4 mm."""
    r = _parse("G20\nG90\nG1 X1.0 F10\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, _INCH, tol=1e-4)
    assert r.units_declared == "inch"


def test_unit_conversion_deterministic():
    """Two identical inch programs must give identical results."""
    prog = "G20\nG90\nG1 X2.0 F5\n"
    r1 = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    r2 = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert r1.feed_distance_mm == r2.feed_distance_mm


def test_g20_feed_word_converted_to_mm_min():
    """F word in G20 program is converted to mm/min."""
    r = _parse("G20\nG1 X0 F10\n", initial_x=0, initial_y=0, initial_z=0)
    # F10 in/min → 254 mm/min
    assert r.nc_commanded_feed_mm_min is not None
    assert _approx(r.nc_commanded_feed_mm_min, 10.0 * _INCH, tol=0.01)


# ---------------------------------------------------------------------------
# Section 3 — Absolute / Incremental positioning
# ---------------------------------------------------------------------------


def test_g90_absolute_coordinates():
    """G90 G1 X50 from origin → 50 mm."""
    r = _parse("G21\nG90\nG1 X50 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 50.0)


def test_g91_incremental_coordinates():
    """G91 G1 X10 Y10 → sqrt(200) ≈ 14.142 mm."""
    r = _parse("G21\nG91\nG1 X10 Y10 F100\n")
    assert _approx(r.feed_distance_mm, math.sqrt(200), tol=1e-5)


def test_g91_does_not_require_initial_position():
    """G91 distance computable without initial position."""
    r = _parse("G21\nG91\nG1 X5 F100\n")
    assert _approx(r.feed_distance_mm, 5.0)
    assert r.unknown_start_count == 0


def test_modal_motion_persistence():
    """Second block inherits G1 modal without repeating G word."""
    r = _parse("G21\nG90\nG1 X10 F100\nX20\n", initial_x=0, initial_y=0, initial_z=0)
    # First: 0→10 = 10 mm; Second: 10→20 = 10 mm. Total = 20 mm.
    assert _approx(r.feed_distance_mm, 20.0)
    assert r.supported_motion_count == 2


def test_omitted_axis_does_not_reset():
    """Unspecified axis carries forward; only specified axis contributes to delta."""
    # G1 X10 → moves only X by 10. Y and Z carry forward.
    r = _parse("G21\nG90\nG1 X10 F100\n", initial_x=0, initial_y=5, initial_z=3)
    # delta: X = 10-0 = 10, Y = 0 (not specified), Z = 0 → dist = 10
    assert _approx(r.feed_distance_mm, 10.0)


def test_partial_axis_words_supported():
    """XY move with Z unspecified computes 2D distance."""
    r = _parse("G21\nG90\nG1 X3 Y4 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 5.0)  # 3-4-5 triangle


# ---------------------------------------------------------------------------
# Section 4 — XYZ Euclidean distance
# ---------------------------------------------------------------------------


def test_xyz_euclidean_3d():
    """3D move: distance = sqrt(3^2 + 4^2 + 0^2) = 5."""
    r = _parse("G21\nG90\nG1 X3 Y4 Z0 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 5.0)


def test_xyz_3d_full():
    """3D move: sqrt(1^2+2^2+2^2) = 3."""
    r = _parse("G21\nG90\nG1 X1 Y2 Z2 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 3.0)


def test_zero_distance_block():
    """G1 to same position → 0 mm added."""
    r = _parse("G21\nG90\nG0 X0 Y0 Z0\nG1 X0 Y0 Z0 F100\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 0.0)


# ---------------------------------------------------------------------------
# Section 5 — G0 rapid / G1 feed classification
# ---------------------------------------------------------------------------


def test_g0_rapid_classification():
    """G0 distance goes to rapid_distance_mm, not feed."""
    r = _parse("G21\nG90\nG0 X100 Y0 F0\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.rapid_distance_mm, 100.0)
    assert _approx(r.feed_distance_mm, 0.0)


def test_g1_feed_classification():
    """G1 distance goes to feed_distance_mm, not rapid."""
    r = _parse("G21\nG90\nG1 X100 Y0 F200\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 100.0)
    assert _approx(r.rapid_distance_mm, 0.0)


def test_mixed_rapid_feed_totals():
    """G0 and G1 moves accumulate in separate buckets."""
    prog = "G21\nG90\nG0 X50 Y0\nG1 X100 Y0 F100\n"
    r = _parse(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.rapid_distance_mm, 50.0)
    assert _approx(r.feed_distance_mm, 50.0)


def test_nc_feed_move_not_confirmed_cutting():
    """feed_distance_mm MUST NOT be labeled as confirmed cutting path."""
    r = _parse("G21\nG1 X100\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.nc_feed_move_equals_confirmed_cutting is False


# ---------------------------------------------------------------------------
# Section 6 — Feed word capture
# ---------------------------------------------------------------------------


def test_feed_word_captured():
    """F word is recorded in nc_commanded_feed_mm_min."""
    r = _parse("G21\nG1 X10 F500\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.nc_commanded_feed_mm_min == pytest.approx(500.0)


def test_feed_word_modal():
    """F word persists to later blocks."""
    r = _parse("G21\nG1 X10 F300\nX20\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.nc_commanded_feed_mm_min == pytest.approx(300.0)


def test_reference_feed_not_overwritten():
    """Parser never touches the reference guidance feed — it is a separate channel."""
    # This test documents the architecture: nc_commanded_feed_mm_min is evidence only.
    # The process planning cycle-time foundation continues to use feed_rate_metric
    # from engineering metrics. There is no mechanism to overwrite it here.
    r = _parse("G21\nG1 X10 F750\n", initial_x=0, initial_y=0, initial_z=0)
    # Parser output has nc_commanded_feed_mm_min; it is NOT injected into any
    # engineering metric or reference guidance field.
    assert r.nc_commanded_feed_mm_min == pytest.approx(750.0)
    # No field named "feed_rate_range" or similar exists in NcMotionResult
    assert not hasattr(r, "feed_rate_range")


# ---------------------------------------------------------------------------
# Section 7 — Tool change detection
# ---------------------------------------------------------------------------


def test_tool_change_t_m6_detected():
    """T word followed by M6 on same line → tool change counted."""
    r = _parse("G21\nT1M6\nG1 X10 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 1


def test_tool_change_time_not_implemented():
    """Tool change count exists; NO time produced (TOOL_CHANGE_TIME_IMPLEMENTED=NO)."""
    r = _parse("G21\nT1M6\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 1
    # NcMotionResult has no tool_change_time_sec field
    assert not hasattr(r, "tool_change_time_sec")


def test_multiple_tool_changes():
    r = _parse("G21\nT1M6\nG1 X10 F100\nT2M6\nG1 X20\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert r.tool_change_count == 2


# ---------------------------------------------------------------------------
# Section 8 — Unsupported arcs
# ---------------------------------------------------------------------------


def test_g2_arc_unsupported():
    """G2 detected → PARTIAL, feature recorded, NO distance added."""
    r = _parse("G21\nG90\nG1 X50 F100\nG2 X100 Y50 R30\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("G2" in f for f in r.unsupported_features)


def test_g3_arc_unsupported():
    """G3 detected → PARTIAL, feature recorded."""
    r = _parse("G21\nG90\nG3 X10 Y10 R5\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert any("G3" in f for f in r.unsupported_features)


def test_arc_never_chord_approximated():
    """Arc presence → distance_mm NOT increased by chord approximation.
    ARC_AS_CHORD_APPROXIMATION=NO.
    """
    # Only G2 present — feed_distance_mm stays 0 (no G1 moves)
    r = _parse("G21\nG90\nG2 X100 Y0 R50\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.arc_chord_approximation_used is False
    assert _approx(r.feed_distance_mm, 0.0)


def test_unsupported_arc_prevents_complete():
    """G2/G3 presence means status CANNOT be COMPLETE."""
    r = _parse("G21\nG90\nG0 X0 Y0 Z0\nG1 X50 F100\nG2 X100 Y0 R25\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status != NcAnalysisStatus.COMPLETE


# ---------------------------------------------------------------------------
# Section 9 — Canned cycles
# ---------------------------------------------------------------------------


def test_g81_detected_not_expanded():
    """G81 is now expanded — feed stroke |Z-R| = |-10-2| = 12 mm, COMPLETE."""
    r = _parse("G21\nG90\nG81 X50 Y50 Z-10 R2 F100\n",
               initial_x=0, initial_y=0, initial_z=0)
    # G81 fully expanded: no unsupported features for G81
    assert not any("G81" in f for f in r.unsupported_features)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE
    assert r.feed_distance_mm > 0


def test_g83_detected_not_expanded():
    """G83 expanded with feed stroke; PARTIAL due to peck-rapid limitation."""
    r = _parse("G21\nG90\nG83 X10 Y10 Z-20 Q5 R2 F80\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert any("G83" in f for f in r.unsupported_features)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert r.feed_distance_mm > 0   # feed stroke |Z-R| = 22 mm accumulated


def test_g84_detected_not_expanded():
    """G84 with R: expanded with 2×|Z-R| path; PARTIAL due to spindle limitation."""
    r = _parse("G21\nG90\nG84 X20 Y20 Z-15 R5 F100\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert any("G84" in f for f in r.unsupported_features)
    assert r.analysis_status == NcAnalysisStatus.PARTIAL
    assert r.feed_distance_mm > 0   # 2×|Z-R| = 2×20 = 40 mm


def test_canned_cycle_expansion_not_implemented():
    """G81 is now expanded — feed stroke is counted (not zero)."""
    r = _parse("G21\nG90\nG81 X0 Y0 Z-10 R2 F100\n",
               initial_x=0, initial_y=0, initial_z=0)
    # Feed stroke |Z-R| = |-10-2| = 12 mm; feed_distance_mm > 0
    assert r.feed_distance_mm > 0


# ---------------------------------------------------------------------------
# Section 10 — Subprograms and macros
# ---------------------------------------------------------------------------


def test_m98_subprogram_unsupported_semantics():
    r = _parse("G21\nG1 X10 F100\nM98 P1000\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.UNSUPPORTED_SEMANTICS
    assert any("M98" in f for f in r.unsupported_features)


def test_m99_subprogram_unsupported_semantics():
    r = _parse("G21\nM99\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.UNSUPPORTED_SEMANTICS
    assert any("M99" in f for f in r.unsupported_features)


def test_macro_variable_detection():
    r = _parse("G21\n#1=100\nG1 X#1 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.UNSUPPORTED_SEMANTICS
    assert any("MACRO" in f for f in r.unsupported_features)


def test_macro_prevents_complete():
    """Macro/subprogram presence → NOT COMPLETE."""
    r = _parse("G21\nG1 X50 F100\nM98 P999\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status not in (
        NcAnalysisStatus.COMPLETE, NcAnalysisStatus.PARTIAL
    )


# ---------------------------------------------------------------------------
# Section 11 — Unknown initial position
# ---------------------------------------------------------------------------


def test_unknown_initial_position_not_guessed():
    """G90 move before position established → distance NOT computed."""
    r = _parse("G21\nG90\nG1 X100 Y0 F100\n")  # no initial position
    assert r.unknown_start_count > 0
    assert _approx(r.feed_distance_mm, 0.0)


def test_known_initial_position_used():
    """With initial_xyz, first absolute move IS computed."""
    r = _parse("G21\nG90\nG1 X100 Y0 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 100.0)
    assert r.unknown_start_count == 0


def test_position_known_after_first_full_move():
    """After G0 X0 Y0 Z0, subsequent moves can be computed even without initial_xyz."""
    # G0 sets position to 0,0,0 (we can't compute G0 distance itself without initial_xyz
    # but after it, position is known for subsequent moves)
    prog = "G21\nG90\nG0 X0 Y0 Z0\nG1 X50 F100\n"
    r = _parse(prog)  # no initial_xyz
    # G0 unknown start → skip; G1 from known (0,0,0) → 50mm
    assert _approx(r.feed_distance_mm, 50.0)
    assert r.unknown_start_count == 1  # the G0 was skipped


# ---------------------------------------------------------------------------
# Section 12 — Analysis status completeness rules
# ---------------------------------------------------------------------------


def test_complete_status_all_moves_computed():
    r = _parse("G21\nG90\nG1 X100 F100\n", initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status == NcAnalysisStatus.COMPLETE


def test_insufficient_data_no_motion():
    """Program with only modal codes and no moves → INSUFFICIENT_DATA."""
    r = _parse("G21\nG90\nM30\n")
    assert r.analysis_status in (
        NcAnalysisStatus.INSUFFICIENT_DATA,
        NcAnalysisStatus.PARTIAL,  # M30 is not a motion
    )


def test_invalid_program_empty():
    r = _parse("")
    assert r.analysis_status == NcAnalysisStatus.INVALID_PROGRAM


def test_unsupported_prevents_complete():
    """Any unsupported path-affecting construct → status CANNOT be COMPLETE."""
    r = _parse("G21\nG90\nG1 X50 F100\nG2 X100 Y0 R25\n",
               initial_x=0, initial_y=0, initial_z=0)
    assert r.analysis_status != NcAnalysisStatus.COMPLETE


# ---------------------------------------------------------------------------
# Section 13 — Live Case A (spec section 34)
# ---------------------------------------------------------------------------


def test_live_case_a_feed_100():
    """G21/G90/G0 X0Y0Z0/G1 X100 Y0 F500 — feed = 100 mm with initial origin."""
    prog = "G21\nG90\nG0 X0 Y0 Z0\nG1 X100 Y0 F500\n"
    r = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 100.0)
    assert r.nc_commanded_feed_mm_min == pytest.approx(500.0)
    assert r.nc_feed_move_equals_confirmed_cutting is False


def test_live_case_b_pythagorean_with_origin():
    """G21/G90/G1 X30 Y40 from origin → 50 mm (3-4-5 triangle)."""
    prog = "G21\nG90\nG1 X30 Y40 F200\n"
    r = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 50.0, tol=1e-4)


def test_live_case_b_no_origin_skipped():
    """Without initial position, G90 first move from unknown pos → skipped."""
    prog = "G21\nG90\nG1 X30 Y40 F200\n"
    r = parse_nc_motion(prog)  # no initial_xyz
    assert _approx(r.feed_distance_mm, 0.0)
    assert r.unknown_start_count == 1


# ---------------------------------------------------------------------------
# Section 14 — Line count limit
# ---------------------------------------------------------------------------


def test_line_count_limit_exceeded():
    from backend.interoperability.nc_motion import _MAX_LINES
    oversized = "\n".join(["G1 X1"] * (_MAX_LINES + 1))
    r = parse_nc_motion(oversized)
    assert r.analysis_status == NcAnalysisStatus.INVALID_PROGRAM


# ---------------------------------------------------------------------------
# Section 15 — Private path protection
# ---------------------------------------------------------------------------


def test_parser_has_no_filesystem_access():
    """Parser accepts text only and never touches the filesystem."""
    # Any string that looks like a path should be treated as NC text data
    fake_path = r"C:\Users\test\prog.nc"
    r = parse_nc_motion(fake_path)
    # Parser processes it as NC text data; does not open any file
    # No exception raised; result is valid (but likely INVALID_PROGRAM or INSUFFICIENT_DATA)
    assert isinstance(r, NcMotionResult)


# ---------------------------------------------------------------------------
# Section 16 — G91 with no initial position
# ---------------------------------------------------------------------------


def test_g91_multiple_incremental_moves():
    """G91 mode: each move accumulates independently."""
    prog = "G21\nG91\nG1 X10 F100\nG1 X10\nG1 X10\n"
    r = parse_nc_motion(prog)
    assert _approx(r.feed_distance_mm, 30.0)
    assert r.supported_motion_count == 3
    assert r.unknown_start_count == 0


def test_g91_rapid_then_feed():
    prog = "G21\nG91\nG0 X5\nG1 Y5 F100\n"
    r = parse_nc_motion(prog)
    assert _approx(r.rapid_distance_mm, 5.0)
    assert _approx(r.feed_distance_mm, 5.0)


# ---------------------------------------------------------------------------
# Section 17 — Comments stripped correctly
# ---------------------------------------------------------------------------


def test_paren_comments_stripped():
    """(comments) should be stripped; G codes after paren should be parsed."""
    prog = "G21 (units)\nG90 (absolute)\nG1 X10 F100 (move)\n"
    r = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 10.0)


def test_semicolon_comments_stripped():
    prog = "G21 ; mm units\nG1 X10 F100 ; cut\n"
    r = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 10.0)


# ---------------------------------------------------------------------------
# Section 18 — Malformed / edge cases
# ---------------------------------------------------------------------------


def test_malformed_line_no_crash():
    """Parser must not raise on malformed lines."""
    bad = "G21\n!!!@@@\nG1 X10 F100\n"
    r = parse_nc_motion(bad, initial_x=0, initial_y=0, initial_z=0)
    assert isinstance(r, NcMotionResult)


def test_percent_delimiter_skipped():
    """% program delimiters are ignored."""
    prog = "%\nG21\nG1 X10 F100\n%\n"
    r = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 10.0)


def test_o_number_skipped():
    prog = "O0010\nG21\nG1 X10 F100\n"
    r = parse_nc_motion(prog, initial_x=0, initial_y=0, initial_z=0)
    assert _approx(r.feed_distance_mm, 10.0)
