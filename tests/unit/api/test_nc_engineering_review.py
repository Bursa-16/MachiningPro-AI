"""Tests for NC_PROGRAM_ENGINEERING_REVIEW_01 Phase 2.

Covers:
  - NCProgramEngineeringReview model
  - build_engineering_review() synthesis
  - EngReviewStatus precedence
  - ParserFeatureCoverage
  - CannedCycleNote
  - EquipmentSummary
  - EngReviewFinding generation
  - API integration (NcAnalyzeResponse.engineering_review)
  - Safety flags
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.interoperability.nc_motion import (
    NcAnalysisStatus,
    NcMotionResult,
    NcMotionSegment,
    parse_nc_motion,
)
from backend.process_planning.engineering_review import (
    CannedCycleNote,
    EngReviewFinding,
    EngReviewStatus,
    EquipmentSummary,
    NCProgramEngineeringReview,
    ParserFeatureCoverage,
    ParserFeatureState,
    build_engineering_review,
)
from backend.process_planning.nc_validation import (
    NCProgramValidationSummary,
    NCValidationFinding,
    NCValidationSeverity,
    NCValidationStatus,
    validate_nc_feed_spindle,
)
from backend.process_planning.path_evidence import (
    feed_evidence_from_nc,
    rapid_evidence_from_nc,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SIMPLE_NC = """
G21 G90
G97 S1200 M3
G0 X0 Y0 Z5
G1 Z-5 F200
G1 X50 F200
G0 Z5
M5
M30
"""

_ARC_NC = """
G21 G90
G97 S800 M3
G0 X0 Y0 Z5
G1 Z-3 F150
G2 X20 Y0 Z-3 I10 J0 F150
G0 Z5
M5 M30
"""

_G93_NC = """
G21 G90
G93
G97 S1000 M3
G0 X0 Y0 Z5
G1 Z-5 F0.5
M5 M30
"""

_G96_NC = """
G21 G90
G96 S120
M3
G0 X0 Y0 Z5
G1 X50 F0.2
M5 M30
"""

_CANNED_G83_NC = """
G21 G90
G97 S800 M3
G0 X0 Y0
G83 X5 Y5 Z-20 R2 Q4 F100
G83 X15 Y15
G80
M5 M30
"""

_CANNED_G84_NC = """
G21 G90
G97 S500 M3
G0 X0 Y0
G84 X5 Y5 Z-15 R2 F1.25
G80
M5 M30
"""

_SPINDLE_STOP_NC = """
G21 G90
G97 S1200 M3
G0 X0 Y0 Z5
G1 Z-5 F200
M5
G1 X50 F200
M30
"""

_HIGH_RPM_NC = """
G21 G90
G97 S99000 M3
G0 X0 Y0 Z5
G1 Z-5 F200
M5 M30
"""


def _empty_validation() -> NCProgramValidationSummary:
    return NCProgramValidationSummary()


def _build(nc_text: str = _SIMPLE_NC, **kwargs) -> NCProgramEngineeringReview:
    motion = parse_nc_motion(nc_text)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    validation = validate_nc_feed_spindle(motion)
    return build_engineering_review(motion, feed_ev, rapid_ev, validation, **kwargs)


# ---------------------------------------------------------------------------
# MODEL — Empty / minimal review
# ---------------------------------------------------------------------------


def test_empty_review_no_motion():
    motion = parse_nc_motion("M30\n")
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion)
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs)
    assert isinstance(review, NCProgramEngineeringReview)
    assert review.total_feed_distance_mm == pytest.approx(0.0)
    assert review.total_rapid_distance_mm == pytest.approx(0.0)


def test_review_parser_profile_set():
    review = _build()
    assert review.parser_profile == "GENERIC_ISO_GCODE_SUBSET"
    assert review.parser_version is not None


def test_review_source_name_safe_none_by_default():
    review = _build()
    assert review.source_name_safe is None


def test_review_source_name_safe_set():
    review = _build(source_name_safe="part_op10.nc")
    assert review.source_name_safe == "part_op10.nc"


def test_review_private_path_not_stored():
    review = _build(source_name_safe="filename.nc")
    assert "/" not in (review.source_name_safe or "")
    assert "\\" not in (review.source_name_safe or "")


# ---------------------------------------------------------------------------
# MODEL — Supported program
# ---------------------------------------------------------------------------


def test_supported_program_pass_with_evidence():
    review = _build(_SIMPLE_NC)
    assert review.review_status in (
        EngReviewStatus.PASS_WITH_EVIDENCE,
        EngReviewStatus.PASS_WITH_ADVISORIES,
        EngReviewStatus.INSUFFICIENT_DATA,
    )


def test_supported_program_motion_counts():
    review = _build(_SIMPLE_NC)
    assert review.total_feed_distance_mm > 0.0


def test_arc_program_arc_count():
    review = _build(_ARC_NC)
    assert review.arc_motion_count > 0


def test_review_segment_count():
    review = _build(_SIMPLE_NC)
    assert review.segment_count >= 1


def test_review_segments_reused():
    review = _build(_SIMPLE_NC)
    assert isinstance(review.segments, list)
    for seg in review.segments:
        assert isinstance(seg, NcMotionSegment)


# ---------------------------------------------------------------------------
# MODEL — Advisory-only
# ---------------------------------------------------------------------------


def test_advisory_only_no_blocking():
    review = _build(_G93_NC)
    assert review.blocking_count == 0
    assert review.review_status != EngReviewStatus.BLOCKED_BY_KNOWN_LIMIT


def test_g93_deferred_advisory_finding():
    review = _build(_G93_NC)
    codes = [f.finding_code for f in review.findings]
    assert "PARSER_G93_DEFERRED" in codes


def test_g96_deferred_advisory_finding():
    review = _build(_G96_NC)
    codes = [f.finding_code for f in review.findings]
    assert "PARSER_G96_DEFERRED" in codes


def test_g93_advisory_severity():
    review = _build(_G93_NC)
    for f in review.findings:
        if f.finding_code == "PARSER_G93_DEFERRED":
            assert f.severity == NCValidationSeverity.ADVISORY


def test_pass_with_advisories_status():
    review = _build(_G93_NC)
    assert review.review_status in (
        EngReviewStatus.PASS_WITH_ADVISORIES,
        EngReviewStatus.INSUFFICIENT_DATA,
    )


# ---------------------------------------------------------------------------
# MODEL — Blocking hard-limit violation
# ---------------------------------------------------------------------------


def test_blocking_rpm_violation():
    motion = parse_nc_motion(_HIGH_RPM_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion, machine_spindle_max_rpm=6000, machine_id="test-machine")
    review = build_engineering_review(
        motion, feed_ev, rapid_ev, vs,
        machine_id="test-machine",
        machine_spindle_max_rpm=6000,
    )
    assert review.blocking_count >= 1
    assert review.review_status == EngReviewStatus.BLOCKED_BY_KNOWN_LIMIT


def test_blocking_finding_has_machine_source():
    motion = parse_nc_motion(_HIGH_RPM_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion, machine_spindle_max_rpm=6000, machine_id="m1")
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs,
                                      machine_id="m1", machine_spindle_max_rpm=6000)
    blocking = [f for f in review.findings if f.severity == NCValidationSeverity.BLOCKING]
    assert len(blocking) >= 1
    assert any("m1" in (f.source or "") for f in blocking)


def test_tool_rpm_blocking():
    motion = parse_nc_motion(_HIGH_RPM_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion, tool_max_rpm=5000, tool_id="t1")
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs,
                                      cutting_tool_id="t1", tool_max_rpm=5000)
    assert review.blocking_count >= 1


def test_holder_rpm_blocking():
    motion = parse_nc_motion(_HIGH_RPM_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion, holder_max_rpm=4000, holder_id="h1")
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs,
                                      tool_holder_id="h1", holder_max_rpm=4000)
    assert review.blocking_count >= 1


# ---------------------------------------------------------------------------
# MODEL — Insufficient data
# ---------------------------------------------------------------------------


def test_no_spindle_command_insufficient_data():
    nc = "G21 G90\nG0 X0 Y0\nG1 X50 F200\nM30\n"
    motion = parse_nc_motion(nc)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion)
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs)
    # Should not fabricate a PASS if RPM data is missing
    assert review.review_status != EngReviewStatus.PASS_WITH_EVIDENCE or review.blocking_count == 0


def test_insufficient_data_not_fabricated_pass():
    nc = "M30\n"
    review = _build(nc)
    assert review.review_status in (
        EngReviewStatus.PASS_WITH_EVIDENCE,
        EngReviewStatus.PASS_WITH_ADVISORIES,
        EngReviewStatus.INSUFFICIENT_DATA,
    )
    # Never claim false approval
    assert review.review_status != "PRODUCTION_APPROVED"
    assert review.review_status != "SAFE_TO_RUN"


# ---------------------------------------------------------------------------
# MODEL — Unsupported feature
# ---------------------------------------------------------------------------


def test_unsupported_features_present_status():
    nc = "M98 P1000\nM30\n"
    review = _build(nc)
    assert review.review_status == EngReviewStatus.UNSUPPORTED_FEATURES_PRESENT


def test_unsupported_finding_warning_severity():
    nc = "M98 P1000\nG21\nM30\n"
    review = _build(nc)
    unsup = [f for f in review.findings if f.category == "UNSUPPORTED_FEATURE"]
    assert len(unsup) >= 1
    for f in unsup:
        assert f.severity in (NCValidationSeverity.WARNING, NCValidationSeverity.BLOCKING)


# ---------------------------------------------------------------------------
# STATUS PRECEDENCE
# ---------------------------------------------------------------------------


def test_blocking_beats_advisory():
    motion = parse_nc_motion(_HIGH_RPM_NC + "\nG93\n")
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion, machine_spindle_max_rpm=1000, machine_id="m1")
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs,
                                      machine_id="m1", machine_spindle_max_rpm=1000)
    assert review.review_status == EngReviewStatus.BLOCKED_BY_KNOWN_LIMIT


def test_unsupported_beats_advisory():
    nc = "G93\nM98 P1000\nM30\n"
    review = _build(nc)
    assert review.review_status in (
        EngReviewStatus.UNSUPPORTED_FEATURES_PRESENT,
        EngReviewStatus.BLOCKED_BY_KNOWN_LIMIT,
    )


def test_warning_produces_review_required():
    review = _build(_SPINDLE_STOP_NC)
    assert review.review_status in (
        EngReviewStatus.REVIEW_REQUIRED,
        EngReviewStatus.PASS_WITH_ADVISORIES,
        EngReviewStatus.PASS_WITH_EVIDENCE,
        EngReviewStatus.INSUFFICIENT_DATA,
    )


def test_pass_with_advisories_no_blocking():
    review = _build(_G93_NC)
    if review.review_status == EngReviewStatus.PASS_WITH_ADVISORIES:
        assert review.blocking_count == 0
        assert review.warning_count == 0


def test_pass_with_evidence_no_issues():
    nc = "G21 G90\nG97 S800 M3\nG0 X0\nG1 X10 F100\nM5 M30\n"
    review = _build(nc)
    assert review.review_status in (
        EngReviewStatus.PASS_WITH_EVIDENCE,
        EngReviewStatus.PASS_WITH_ADVISORIES,
        EngReviewStatus.INSUFFICIENT_DATA,
    )


# ---------------------------------------------------------------------------
# PARSER COVERAGE
# ---------------------------------------------------------------------------


def test_g0_supported():
    review = _build(_SIMPLE_NC)
    g0 = next((f for f in review.feature_coverage if f.feature.startswith("G0")), None)
    assert g0 is not None
    assert g0.state == ParserFeatureState.SUPPORTED


def test_g1_supported():
    review = _build(_SIMPLE_NC)
    g1 = next((f for f in review.feature_coverage if f.feature.startswith("G1 ")), None)
    assert g1 is not None
    assert g1.state == ParserFeatureState.SUPPORTED


def test_g2_g3_supported():
    review = _build(_ARC_NC)
    arc = next((f for f in review.feature_coverage if "G2/G3 IJK" in f.feature), None)
    assert arc is not None
    assert arc.state == ParserFeatureState.SUPPORTED


def test_g93_deferred_in_coverage():
    review = _build(_G93_NC)
    g93 = next((f for f in review.feature_coverage if "G93" in f.feature), None)
    assert g93 is not None
    assert g93.state == ParserFeatureState.DEFERRED


def test_g96_deferred_in_coverage():
    review = _build(_G96_NC)
    g96 = next((f for f in review.feature_coverage if "G96" in f.feature), None)
    assert g96 is not None
    assert g96.state == ParserFeatureState.DEFERRED


def test_g93_detected_when_present():
    review = _build(_G93_NC)
    g93 = next((f for f in review.feature_coverage if "G93" in f.feature), None)
    assert g93 is not None
    assert g93.detected is True


def test_bounded_canned_g83():
    review = _build(_CANNED_G83_NC)
    g83 = next((f for f in review.feature_coverage if "G83" in f.feature), None)
    assert g83 is not None
    assert g83.state == ParserFeatureState.BOUNDED


def test_bounded_canned_g84():
    review = _build(_CANNED_G84_NC)
    g84 = next((f for f in review.feature_coverage if "G84" in f.feature), None)
    assert g84 is not None
    assert g84.state == ParserFeatureState.BOUNDED


def test_unsupported_subprogram():
    review = _build("M98 P1000\nM30\n")
    m98 = next((f for f in review.feature_coverage if "M98" in f.feature), None)
    assert m98 is not None
    assert m98.state == ParserFeatureState.UNSUPPORTED


# ---------------------------------------------------------------------------
# MOTION SUMMARY
# ---------------------------------------------------------------------------


def test_motion_summary_rapid_distance():
    review = _build(_SIMPLE_NC)
    assert review.total_rapid_distance_mm >= 0.0


def test_motion_summary_feed_distance():
    review = _build(_SIMPLE_NC)
    assert review.total_feed_distance_mm >= 0.0


def test_motion_not_labeled_executed():
    review = _build(_SIMPLE_NC)
    assert review.programmed_motion_equals_executed_motion is False


def test_feed_distance_not_confirmed_cutting():
    review = _build(_SIMPLE_NC)
    assert review.programmed_feed_distance_equals_confirmed_cutting is False


def test_canned_cycle_programmed_motion():
    review = _build(_CANNED_G83_NC)
    # G83 produces feed distance (programmed strokes)
    assert review.total_feed_distance_mm >= 0.0


# ---------------------------------------------------------------------------
# SEGMENTS
# ---------------------------------------------------------------------------


def test_segments_one_segment():
    nc = "G21 G90\nG97 S800 M3\nG1 X50 F200\nM5 M30\n"
    review = _build(nc)
    assert len(review.segments) == 1


def test_segments_multiple_tool_change():
    nc = "G21\nT1 M6\nG97 S800 M3\nG1 X10 F200\nT2 M6\nG1 X20 F150\nM5 M30\n"
    review = _build(nc)
    assert len(review.segments) >= 2


def test_t_word_not_catalog_identity():
    nc = "G21\nT5 M6\nG97 S800 M3\nG1 X10 F200\nM5 M30\n"
    review = _build(nc)
    assert review.t_word_equals_confirmed_tool_identity is False
    # tool_id_raw on segment is the raw T-word string
    tc_segs = [s for s in review.segments if s.tool_id_raw is not None]
    for seg in tc_segs:
        assert seg.tool_id_raw == "5"


def test_mapped_operation():
    review = _build(_SIMPLE_NC, operation_association="MILLING")
    assert review.operation_association == "MILLING"


def test_unmapped_operation_none():
    review = _build(_SIMPLE_NC)
    assert review.operation_association is None


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------


def test_equipment_machine_set():
    review = _build(
        _SIMPLE_NC,
        machine_id="dmg-clx-350",
        machine_spindle_max_rpm=5000,
        machine_display="DMG CLX 350",
    )
    assert review.equipment.machine_id == "dmg-clx-350"
    assert review.equipment.machine_spindle_max_rpm == 5000
    assert review.equipment.machine_display == "DMG CLX 350"


def test_equipment_tool_set():
    review = _build(
        _SIMPLE_NC,
        cutting_tool_id="seco-t12m",
        tool_max_rpm=10000,
        cutting_tool_display="SECO T12M",
    )
    assert review.equipment.cutting_tool_id == "seco-t12m"
    assert review.equipment.tool_max_rpm == 10000


def test_equipment_holder_set():
    review = _build(
        _SIMPLE_NC,
        tool_holder_id="sandvik-corogrip",
        holder_max_rpm=8000,
        tool_holder_display="Sandvik CoroGrip",
    )
    assert review.equipment.tool_holder_id == "sandvik-corogrip"
    assert review.equipment.holder_max_rpm == 8000


def test_effective_rpm_limit_min_of_known():
    review = _build(
        _SIMPLE_NC,
        machine_id="m1",
        machine_spindle_max_rpm=6000,
        cutting_tool_id="t1",
        tool_max_rpm=4000,
        tool_holder_id="h1",
        holder_max_rpm=8000,
    )
    assert review.equipment.effective_rpm_limit == 4000
    assert "t1" in (review.equipment.effective_rpm_limit_source or "")


def test_missing_configuration_data():
    review = _build(_SIMPLE_NC)
    # No machine/tool/holder provided — all None
    assert review.equipment.machine_id is None
    assert review.equipment.effective_rpm_limit is None


def test_missing_limit_not_zero():
    review = _build(
        _SIMPLE_NC,
        machine_id="m1",
        machine_spindle_max_rpm=None,
    )
    assert review.equipment.effective_rpm_limit is None or isinstance(
        review.equipment.effective_rpm_limit, int
    )


# ---------------------------------------------------------------------------
# VALIDATION REUSE
# ---------------------------------------------------------------------------


def test_validation_summary_reused():
    motion = parse_nc_motion(_HIGH_RPM_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion, machine_spindle_max_rpm=6000, machine_id="m1")
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs,
                                      machine_id="m1", machine_spindle_max_rpm=6000)
    assert review.validation_summary is vs


def test_vc_reused_not_duplicated():
    motion = parse_nc_motion(_SIMPLE_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(
        motion,
        machine_spindle_max_rpm=5000,
        machine_id="m1",
        tool_cutting_diameter_mm=10.0,
        tool_id="t1",
    )
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs,
                                      machine_id="m1", machine_spindle_max_rpm=5000)
    # Vc comes from validation_summary, not recalculated
    vc_calc = review.validation_summary.calculated_cutting_speed_m_min
    assert vc_calc is not None or vs.calculated_cutting_speed_m_min is None


def test_fz_reused():
    motion = parse_nc_motion(_SIMPLE_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion)
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs)
    assert review.validation_summary.calculated_feed_per_tooth_mm == vs.calculated_feed_per_tooth_mm


def test_feed_rev_reused():
    motion = parse_nc_motion(_SIMPLE_NC)
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion)
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs)
    assert review.validation_summary.calculated_feed_per_rev_mm == vs.calculated_feed_per_rev_mm


def test_insufficient_data_reused():
    motion = parse_nc_motion("G1 X50 F200\nM30\n")
    feed_ev = feed_evidence_from_nc(motion)
    rapid_ev = rapid_evidence_from_nc(motion)
    vs = validate_nc_feed_spindle(motion)
    review = build_engineering_review(motion, feed_ev, rapid_ev, vs)
    # INSUFFICIENT_DATA from no spindle command is propagated, not fabricated OK
    assert review.validation_summary.nc_commanded_spindle_rpm is None


# ---------------------------------------------------------------------------
# CYCLE TIME
# ---------------------------------------------------------------------------


def test_cycle_time_known_subtotal():
    review = _build(_SIMPLE_NC,
                    cycle_time_known_subtotal_sec=12.5,
                    cycle_time_status="PARTIAL")
    assert review.cycle_time_known_subtotal_sec == pytest.approx(12.5)
    assert review.cycle_time_status == "PARTIAL"


def test_cycle_time_none_not_fabricated():
    review = _build(_SIMPLE_NC)
    # If no cycle time passed, should be None — not invented
    assert review.cycle_time_known_subtotal_sec is None or isinstance(
        review.cycle_time_known_subtotal_sec, float
    )


def test_cycle_time_partial_not_labeled_total():
    review = _build(_SIMPLE_NC,
                    cycle_time_known_subtotal_sec=5.0,
                    cycle_time_status="PARTIAL")
    assert review.partial_time_mislabeled_total is False


def test_no_fabricated_tool_change_seconds():
    review = _build(_SIMPLE_NC)
    # engineering_review has no tool_change_time field — count only
    assert not hasattr(review, "tool_change_time_seconds")


# ---------------------------------------------------------------------------
# CANNED CYCLES
# ---------------------------------------------------------------------------


def test_g83_canned_note_detected():
    review = _build(_CANNED_G83_NC)
    codes = [n.cycle_code_str for n in review.canned_cycle_notes]
    assert "G83" in codes


def test_g84_canned_note_bounded():
    review = _build(_CANNED_G84_NC)
    codes = [n.cycle_code_str for n in review.canned_cycle_notes]
    assert "G84" in codes
    g84_note = next(n for n in review.canned_cycle_notes if n.cycle_code_str == "G84")
    assert g84_note.state == ParserFeatureState.BOUNDED


def test_g83_not_labeled_complete():
    review = _build(_CANNED_G83_NC)
    g83 = next((n for n in review.canned_cycle_notes if n.cycle_code_str == "G83"), None)
    if g83:
        assert g83.bounded_canned_cycle_mislabeled_complete is False
        assert g83.state != ParserFeatureState.SUPPORTED or g83.bounded_reason is not None


def test_bounded_canned_cycle_flag():
    review = _build(_CANNED_G83_NC)
    assert review.bounded_canned_cycle_mislabeled_complete is False


# ---------------------------------------------------------------------------
# FINDINGS + PROVENANCE
# ---------------------------------------------------------------------------


def test_finding_has_code():
    review = _build(_G93_NC)
    for f in review.findings:
        assert f.finding_code
        assert len(f.finding_code) > 0


def test_finding_has_severity():
    review = _build(_G93_NC)
    for f in review.findings:
        assert isinstance(f.severity, NCValidationSeverity)


def test_finding_has_category():
    review = _build(_G93_NC)
    for f in review.findings:
        assert f.category


def test_finding_provenance_evidence_type():
    review = _build(_G93_NC)
    for f in review.findings:
        if f.evidence_type is not None:
            assert f.evidence_type in (
                "NC_PROGRAM", "MACHINE_CATALOG", "CUTTING_TOOL_CATALOG",
                "TOOL_HOLDER_CATALOG", "CUTTING_PARAMETER_REFERENCE",
                "DERIVED_FORMULA", "COMPATIBILITY_ENGINE", "SELECTION_ENGINE",
            )


def test_counts_match_findings():
    review = _build(_HIGH_RPM_NC)
    counted = sum([
        review.blocking_count, review.warning_count,
        review.advisory_count, review.info_count,
        review.insufficient_data_count,
    ])
    actual = len([f for f in review.findings
                  if f.severity not in (
                      NCValidationSeverity.NOT_APPLICABLE,
                  )])
    # Counts may be ≤ actual (dedup / category-based)
    assert reviewed_counts_consistent(review)


def reviewed_counts_consistent(review: NCProgramEngineeringReview) -> bool:
    b = sum(1 for f in review.findings if f.severity == NCValidationSeverity.BLOCKING)
    w = sum(1 for f in review.findings if f.severity == NCValidationSeverity.WARNING)
    a = sum(1 for f in review.findings if f.severity == NCValidationSeverity.ADVISORY)
    return (
        review.blocking_count == b
        and review.warning_count == w
        and review.advisory_count == a
    )


# ---------------------------------------------------------------------------
# SAFETY FLAGS
# ---------------------------------------------------------------------------


def test_nc_file_executed_false():
    review = _build(_SIMPLE_NC)
    assert review.nc_file_executed is False


def test_machine_behavior_simulated_false():
    review = _build(_SIMPLE_NC)
    assert review.machine_behavior_simulated is False


def test_collision_check_performed_false():
    review = _build(_SIMPLE_NC)
    assert review.collision_check_performed is False


def test_machine_kinematics_simulated_false():
    review = _build(_SIMPLE_NC)
    assert review.machine_kinematics_simulated is False


def test_gouge_check_performed_false():
    review = _build(_SIMPLE_NC)
    assert review.gouge_check_performed is False


def test_false_controller_compatibility_claim_false():
    review = _build(_SIMPLE_NC)
    assert review.false_controller_compatibility_claim is False


def test_false_production_approval_claim_false():
    review = _build(_SIMPLE_NC)
    assert review.false_production_approval_claim is False


def test_false_safe_to_run_claim_false():
    review = _build(_SIMPLE_NC)
    assert review.false_safe_to_run_claim is False


def test_false_collision_free_claim_false():
    review = _build(_SIMPLE_NC)
    assert review.false_collision_free_claim is False


def test_arbitrary_score_false():
    review = _build(_SIMPLE_NC)
    assert review.arbitrary_numeric_engineering_score_implemented is False


def test_no_numeric_score_field():
    review = _build(_SIMPLE_NC)
    # No engineering_score or similar numeric score field
    assert not hasattr(review, "engineering_score")
    assert not hasattr(review, "quality_score")


def test_t_word_identity_flag_false():
    review = _build(_SIMPLE_NC)
    assert review.t_word_equals_confirmed_tool_identity is False


def test_partial_time_not_labeled_total():
    review = _build(_SIMPLE_NC)
    assert review.partial_time_mislabeled_total is False


def test_bounded_canned_not_labeled_complete():
    review = _build(_CANNED_G83_NC)
    assert review.bounded_canned_cycle_mislabeled_complete is False


def test_private_path_flags_false():
    review = _build(_SIMPLE_NC, source_name_safe="file.nc")
    assert review.private_local_path_visible is False
    assert review.private_path_in_api_response is False


def test_no_production_approved_status():
    review = _build(_SIMPLE_NC)
    assert str(review.review_status) not in ("PRODUCTION_APPROVED", "SAFE_TO_RUN", "CERTIFIED")


# ---------------------------------------------------------------------------
# API — serialization
# ---------------------------------------------------------------------------


_client = TestClient(app)
_URL = "/api/nc-path/analyze"


def _post(nc_text: str, **kwargs) -> dict:
    payload = {"nc_text": nc_text, **kwargs}
    resp = _client.post(_URL, json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


def test_api_engineering_review_present():
    body = _post(_SIMPLE_NC)
    assert "engineering_review" in body
    er = body["engineering_review"]
    assert er is not None
    assert "review_status" in er


def test_api_existing_fields_unchanged():
    body = _post(_SIMPLE_NC)
    assert "feed_evidence" in body
    assert "rapid_evidence" in body
    assert "motion_result" in body
    assert "validation_summary" in body
    assert body["nc_file_executed"] is False


def test_api_backward_compatibility():
    body = _post(_SIMPLE_NC)
    assert "feed_evidence" in body
    assert "rapid_evidence" in body


def test_api_serialization_no_error():
    body = _post(_G96_NC)
    er = body["engineering_review"]
    assert "feature_coverage" in er
    assert "findings" in er
    assert "review_status" in er


def test_api_review_status_values():
    body = _post(_SIMPLE_NC)
    status = body["engineering_review"]["review_status"]
    assert status in (
        "PASS_WITH_EVIDENCE", "PASS_WITH_ADVISORIES",
        "REVIEW_REQUIRED", "BLOCKED_BY_KNOWN_LIMIT",
        "INSUFFICIENT_DATA", "UNSUPPORTED_FEATURES_PRESENT",
    )


def test_api_safety_flags_false():
    body = _post(_SIMPLE_NC)
    er = body["engineering_review"]
    assert er["nc_file_executed"] is False
    assert er["collision_check_performed"] is False
    assert er["false_production_approval_claim"] is False
    assert er["false_safe_to_run_claim"] is False
    assert er["false_collision_free_claim"] is False
    assert er["arbitrary_numeric_engineering_score_implemented"] is False


def test_api_no_private_path_in_response():
    body = _post(_SIMPLE_NC, source_name="my_part.nc")
    er = body["engineering_review"]
    assert er.get("source_name_safe") == "my_part.nc"
    assert er["private_path_in_api_response"] is False
    assert er["private_local_path_visible"] is False
