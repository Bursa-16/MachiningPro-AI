"""NC Program Engineering Review synthesis.

NC_PROGRAM_ENGINEERING_REVIEW_01 — Phase 2

Synthesizes existing NC motion, validation, and catalog evidence into a
structured engineering review.  Does NOT reimplement:
  - NC parsing (nc_motion.py)
  - Feed / spindle validation (nc_validation.py)
  - Compatibility engine
  - Selection engine
  - Cycle-time formulas
  - Cutting formulas

Safety constants enforced here:
    NC_FILE_EXECUTED=NO
    MACHINE_BEHAVIOR_SIMULATED=NO
    COLLISION_CHECK_PERFORMED=NO
    MACHINE_KINEMATICS_SIMULATED=NO
    GOUGE_CHECK_PERFORMED=NO
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO
    FALSE_PRODUCTION_APPROVAL_CLAIM=NO
    FALSE_SAFE_TO_RUN_CLAIM=NO
    FALSE_COLLISION_FREE_CLAIM=NO
    ARBITRARY_NUMERIC_ENGINEERING_SCORE_IMPLEMENTED=NO
    PROGRAMMED_MOTION_EQUALS_EXECUTED_MOTION=NO
    PROGRAMMED_FEED_DISTANCE_EQUALS_CONFIRMED_CUTTING=NO
    T_WORD_EQUALS_CONFIRMED_TOOL_IDENTITY=NO
    PARTIAL_TIME_MISLABELED_TOTAL=NO
    BOUNDED_CANNED_CYCLE_MISLABELED_COMPLETE=NO
    PRIVATE_LOCAL_PATH_VISIBLE=NO
    PRIVATE_PATH_IN_API_RESPONSE=NO
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from backend.interoperability.nc_motion import NcMotionResult, NcMotionSegment
from backend.process_planning.nc_validation import (
    NCProgramValidationSummary,
    NCValidationSeverity,
)
from backend.process_planning.path_evidence import PathEvidence

__all__ = [
    "ParserFeatureState",
    "EngReviewStatus",
    "ParserFeatureCoverage",
    "CannedCycleNote",
    "EquipmentSummary",
    "EngReviewFinding",
    "NCProgramEngineeringReview",
    "build_engineering_review",
]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ParserFeatureState(StrEnum):
    SUPPORTED = "SUPPORTED"
    BOUNDED = "BOUNDED"
    DEFERRED = "DEFERRED"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_SEMANTICS = "INSUFFICIENT_SEMANTICS"


class EngReviewStatus(StrEnum):
    PASS_WITH_EVIDENCE = "PASS_WITH_EVIDENCE"
    PASS_WITH_ADVISORIES = "PASS_WITH_ADVISORIES"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED_BY_KNOWN_LIMIT = "BLOCKED_BY_KNOWN_LIMIT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNSUPPORTED_FEATURES_PRESENT = "UNSUPPORTED_FEATURES_PRESENT"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ParserFeatureCoverage(BaseModel):
    """Parser support state for one G/M-code feature."""

    feature: str
    state: ParserFeatureState
    detected: bool = False
    note: str | None = None


class CannedCycleNote(BaseModel):
    """Summary evidence for one detected canned cycle code."""

    cycle_code_str: str        # e.g. "G83"
    state: ParserFeatureState  # SUPPORTED / BOUNDED
    bounded_reason: str | None = None
    detected_limitations: list[str] = []

    # Safety constants
    bounded_canned_cycle_mislabeled_complete: bool = False


class EquipmentSummary(BaseModel):
    """Reused catalog and compatibility evidence. COMPATIBILITY_FORMULA_DUPLICATED=NO."""

    machine_id: str | None = None
    machine_display: str | None = None
    cutting_tool_id: str | None = None
    cutting_tool_display: str | None = None
    tool_holder_id: str | None = None
    tool_holder_display: str | None = None

    machine_spindle_max_rpm: int | None = None
    tool_max_rpm: int | None = None
    holder_max_rpm: int | None = None
    effective_rpm_limit: int | None = None
    effective_rpm_limit_source: str | None = None

    missing_fields: list[str] = []


class EngReviewFinding(BaseModel):
    """One engineering review finding with provenance.

    EXISTING_FINDING_MODEL_REUSED_WHERE_VALID=YES — severity/status vocabulary
    aligns with NCValidationSeverity.
    """

    finding_code: str
    category: str           # e.g. "RPM_LIMIT", "PARSER_COVERAGE", "FEED_CONSISTENCY"
    severity: NCValidationSeverity
    title_key: str
    message_key: str
    observed_value: float | None = None
    limit_value: float | None = None
    unit: str | None = None
    source: str | None = None
    evidence_type: str | None = None   # provenance category
    segment_id: str | None = None
    limitation: str | None = None


# ---------------------------------------------------------------------------
# Static parser feature table
# ---------------------------------------------------------------------------
# Describes the parser profile contract. 'detected' is patched at runtime.
# FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO — GENERIC_ISO_GCODE_SUBSET only.

_FEATURE_TABLE: list[tuple[str, ParserFeatureState, str]] = [
    ("G0 (Rapid)", ParserFeatureState.SUPPORTED, "Linear rapid motion"),
    ("G1 (Feed)", ParserFeatureState.SUPPORTED, "Linear feed motion"),
    ("G2/G3 IJK (Arc)", ParserFeatureState.SUPPORTED,
     "Analytic circular arc; ARC_FALLBACK_TO_CHORD=NO"),
    ("G2/G3 R-format", ParserFeatureState.DEFERRED,
     "R-format arcs deferred — IJK only supported"),
    ("G17/G18/G19 (Plane)", ParserFeatureState.SUPPORTED, "Plane selection tracked"),
    ("G20/G21 (Units)", ParserFeatureState.SUPPORTED, "Inch/mm unit selection"),
    ("G90/G91 (Positioning)", ParserFeatureState.SUPPORTED,
     "Absolute/incremental positioning"),
    ("G91 inside canned cycles", ParserFeatureState.DEFERRED,
     "Incremental canned cycle coordinates deferred"),
    ("L repeat (canned)", ParserFeatureState.DEFERRED,
     "L-word repeat inside canned cycles deferred"),
    ("G80 (Cancel canned)", ParserFeatureState.SUPPORTED, "Canned cycle cancel"),
    ("G81 (Drill)", ParserFeatureState.SUPPORTED, "Standard drill cycle"),
    ("G82 (Drill+Dwell)", ParserFeatureState.BOUNDED,
     "Dwell: P-word captured; units controller-specific"),
    ("G83 (Peck Drill)", ParserFeatureState.BOUNDED,
     "Peck feed distance; retract rapid controller-specific"),
    ("G84 (Tapping)", ParserFeatureState.BOUNDED,
     "Path distance only; spindle-reversal time not modelled"),
    ("G85 (Bore)", ParserFeatureState.SUPPORTED, "Bore-out cycle"),
    ("G86-G89", ParserFeatureState.BOUNDED, "Detected; expand deferred"),
    ("G94 (Feed/min)", ParserFeatureState.SUPPORTED, "Feed per minute modal"),
    ("G95 (Feed/rev)", ParserFeatureState.SUPPORTED, "Feed per revolution modal"),
    ("G93 (Inverse time)", ParserFeatureState.DEFERRED,
     "Inverse-time feed deferred; G93_INVERSE_TIME_DEFERRED=YES"),
    ("G96 (CSS)", ParserFeatureState.DEFERRED,
     "Constant surface speed deferred; G96_CSS_RPM_CALCULATED=NO"),
    ("G97 (Constant RPM)", ParserFeatureState.SUPPORTED, "Constant spindle speed tracked"),
    ("G98/G99 (Return mode)", ParserFeatureState.SUPPORTED,
     "Canned cycle return-to-initial/retract-plane"),
    ("M3/M4/M5 (Spindle)", ParserFeatureState.SUPPORTED,
     "Spindle direction and stop tracked"),
    ("M98/M99 (Subprogram)", ParserFeatureState.UNSUPPORTED,
     "Subprogram call rejected; NC_FILE_EXECUTED=NO"),
    ("Macro variables (#)", ParserFeatureState.UNSUPPORTED, "Macro variables rejected"),
    ("WHILE/IF control flow", ParserFeatureState.UNSUPPORTED, "Control flow rejected"),
]

# Tags that indicate a feature was detected in the NC program
_DETECTION_HINTS: dict[str, list[str]] = {
    "G2/G3 R-format": ["G2_R_FORMAT_DEFERRED", "G3_R_FORMAT_DEFERRED"],
    "G91 inside canned cycles": ["G91_CANNED_DEFERRED"],
    "L repeat (canned)": ["L_REPEAT_CANNED_DEFERRED"],
    "G82 (Drill+Dwell)": [],   # detected via limitations; always show if present
    "G83 (Peck Drill)": ["G83_PECK_RAPID_CONTROLLER_SPECIFIC"],
    "G84 (Tapping)": ["G84_CYCLE_TIME_SPINDLE_DEPENDENT", "G84_CYCLE_TIME_OMITTED"],
    "G86-G89": ["G86_CANNED_CYCLE_DETECTED", "G87_CANNED_CYCLE_DETECTED",
                "G88_CANNED_CYCLE_DETECTED", "G89_CANNED_CYCLE_DETECTED"],
    "G93 (Inverse time)": ["G93_INVERSE_TIME_DEFERRED"],
    "G96 (CSS)": ["G96_CSS_DEFERRED"],
    "M98/M99 (Subprogram)": [
        "SUBPROGRAM_CALL_M98", "SUBPROGRAM_CALL_M99", "SUBPROGRAM_CALL_REJECTED",
    ],
    "Macro variables (#)": ["MACRO_VARIABLE", "MACRO_VARIABLE_REJECTED"],
    "WHILE/IF control flow": ["CONTROL_FLOW_REJECTED", "WHILE_REJECTED", "IF_REJECTED"],
    "G41/G42 (Cutter comp)": ["G41_CUTTER_RADIUS_COMP_DETECTED", "G42_CUTTER_RADIUS_COMP_DETECTED"],
}

# Tags for cycles that indicate actual encounter (G81/G85 have no partial tags)
_CYCLE_DETECTED_TAGS: dict[str, list[str]] = {
    "G83": ["G83_PECK_RAPID_CONTROLLER_SPECIFIC"],
    "G84": ["G84_CYCLE_TIME_SPINDLE_DEPENDENT", "G84_CYCLE_TIME_OMITTED"],
    "G82": [],  # G82 only appears in limitations, not unsupported_features normally
    "G86-G89": ["G86_CANNED_CYCLE_DETECTED", "G87_CANNED_CYCLE_DETECTED",
                "G88_CANNED_CYCLE_DETECTED", "G89_CANNED_CYCLE_DETECTED"],
}

_CANNED_STATES: dict[str, tuple[ParserFeatureState, str | None]] = {
    "G81": (ParserFeatureState.SUPPORTED, None),
    "G82": (ParserFeatureState.BOUNDED, "Dwell P-word captured; units are controller-specific"),
    "G83": (ParserFeatureState.BOUNDED,
            "Peck retract rapid is controller-specific (G83_PECK_RAPID_CONTROLLER_SPECIFIC)"),
    "G84": (ParserFeatureState.BOUNDED,
            "Path distance only; spindle-reversal cycle time not modelled"
            " (G84_CYCLE_TIME_SPINDLE_DEPENDENT)"),
    "G85": (ParserFeatureState.SUPPORTED, None),
    "G86-G89": (ParserFeatureState.BOUNDED, "Detected but not expanded — BOUNDED/NO_EXPAND"),
}


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------


class NCProgramEngineeringReview(BaseModel):
    """Deterministic NC Program Engineering Review.

    Synthesizes NC motion, validation, and catalog evidence.
    VALIDATION_SUMMARY_REMAINS_SEPARATE=YES — NCProgramValidationSummary
    is embedded, not replaced.

    All distances are programmed values:
      PROGRAMMED_MOTION_EQUALS_EXECUTED_MOTION=NO
      PROGRAMMED_FEED_DISTANCE_EQUALS_CONFIRMED_CUTTING=NO
    """

    # A. Program Identity
    source_name_safe: str | None = None   # PRIVATE_LOCAL_PATH_VISIBLE=NO
    parser_profile: str
    parser_version: str
    units_declared: str | None = None
    analysis_status: str
    segment_count: int = 0
    tool_change_count: int = 0
    supported_motion_count: int = 0
    unsupported_construct_count: int = 0
    arc_motion_count: int = 0

    # B. Parser Coverage
    feature_coverage: list[ParserFeatureCoverage] = []
    deferred_features_detected: list[str] = []
    unsupported_features_detected: list[str] = []

    # C. Motion Summary (programmed values only)
    total_feed_distance_mm: float = 0.0
    total_rapid_distance_mm: float = 0.0

    # D. Segments (reused directly; T_WORD_EQUALS_CONFIRMED_TOOL_IDENTITY=NO)
    segments: list[NcMotionSegment] = []

    # E. Machine / Tool / Holder
    equipment: EquipmentSummary

    # F. Compatibility Evidence (reused string — not recomputed)
    compatibility_status: str | None = None

    # G. Feed & Spindle Validation (NC_PROGRAM_VALIDATION_REUSED=YES)
    validation_summary: NCProgramValidationSummary

    # H. Operation / Process Mapping
    operation_association: str | None = None

    # I. Cycle Time (CYCLE_TIME_FOUNDATION_REUSED=YES)
    cycle_time_known_subtotal_sec: float | None = None
    cycle_time_status: str | None = None
    cycle_time_limitations: list[str] = []

    # J/K. Canned Cycle Notes
    canned_cycle_notes: list[CannedCycleNote] = []

    # L. Findings
    findings: list[EngReviewFinding] = []

    # M. Severity counts
    blocking_count: int = 0
    warning_count: int = 0
    advisory_count: int = 0
    info_count: int = 0
    insufficient_data_count: int = 0
    unsupported_count: int = 0

    # M. Limitations
    limitations: list[str] = []

    # N. Overall Engineering Review Status
    review_status: EngReviewStatus

    # Immutable safety flags — always constant
    nc_file_executed: bool = False
    machine_behavior_simulated: bool = False
    collision_check_performed: bool = False
    machine_kinematics_simulated: bool = False
    gouge_check_performed: bool = False
    false_controller_compatibility_claim: bool = False
    false_production_approval_claim: bool = False
    false_safe_to_run_claim: bool = False
    false_collision_free_claim: bool = False
    arbitrary_numeric_engineering_score_implemented: bool = False
    programmed_motion_equals_executed_motion: bool = False
    programmed_feed_distance_equals_confirmed_cutting: bool = False
    t_word_equals_confirmed_tool_identity: bool = False
    partial_time_mislabeled_total: bool = False
    bounded_canned_cycle_mislabeled_complete: bool = False
    private_local_path_visible: bool = False
    private_path_in_api_response: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_feature_coverage(unsupported_features: list[str]) -> list[ParserFeatureCoverage]:
    result: list[ParserFeatureCoverage] = []
    feat_set = set(unsupported_features)
    for name, state, note in _FEATURE_TABLE:
        hints = _DETECTION_HINTS.get(name, [])
        detected = bool(hints and any(h in feat_set for h in hints))
        result.append(ParserFeatureCoverage(
            feature=name,
            state=state,
            detected=detected,
            note=note,
        ))
    return result


def _build_canned_cycle_notes(
    unsupported_features: list[str], limitations: list[str]
) -> list[CannedCycleNote]:
    feat_set = set(unsupported_features)
    all_text = " ".join(unsupported_features) + " " + " ".join(limitations)
    notes: list[CannedCycleNote] = []

    # G83
    if "G83_PECK_RAPID_CONTROLLER_SPECIFIC" in feat_set:
        state, reason = _CANNED_STATES["G83"]
        lims = [f for f in unsupported_features if "G83" in f]
        notes.append(CannedCycleNote(
            cycle_code_str="G83",
            state=state,
            bounded_reason=reason,
            detected_limitations=lims,
            bounded_canned_cycle_mislabeled_complete=False,
        ))

    # G84
    if any("G84" in f for f in unsupported_features):
        state, reason = _CANNED_STATES["G84"]
        lims = [f for f in unsupported_features if "G84" in f]
        notes.append(CannedCycleNote(
            cycle_code_str="G84",
            state=state,
            bounded_reason=reason,
            detected_limitations=lims,
            bounded_canned_cycle_mislabeled_complete=False,
        ))

    # G82 dwell — detected via limitations
    if "G82" in all_text and any("G82" in lim or "DWELL" in lim.upper() for lim in limitations):
        state, reason = _CANNED_STATES["G82"]
        lims = [lim for lim in limitations if "G82" in lim or "dwell" in lim.lower()]
        notes.append(CannedCycleNote(
            cycle_code_str="G82",
            state=state,
            bounded_reason=reason,
            detected_limitations=lims,
            bounded_canned_cycle_mislabeled_complete=False,
        ))

    # G86-G89
    adv_tags = [f for f in unsupported_features
                if any(f.startswith(f"G8{n}_CANNED_CYCLE_DETECTED") for n in (6, 7, 8, 9))]
    if adv_tags:
        state, reason = _CANNED_STATES["G86-G89"]
        notes.append(CannedCycleNote(
            cycle_code_str="G86-G89",
            state=state,
            bounded_reason=reason,
            detected_limitations=adv_tags,
            bounded_canned_cycle_mislabeled_complete=False,
        ))

    return notes


def _build_findings_from_validation(vs: NCProgramValidationSummary) -> list[EngReviewFinding]:
    findings: list[EngReviewFinding] = []

    for check, code_suffix, title_key, evt_type in [
        (vs.machine_rpm_limit_check, "MACHINE_RPM", "ncErFindingMachineRpm", "MACHINE_CATALOG"),
        (vs.tool_rpm_limit_check, "TOOL_RPM", "ncErFindingToolRpm", "CUTTING_TOOL_CATALOG"),
        (vs.holder_rpm_limit_check, "HOLDER_RPM", "ncErFindingHolderRpm", "TOOL_HOLDER_CATALOG"),
        (vs.effective_rpm_limit_check, "EFFECTIVE_RPM",
         "ncErFindingEffectiveRpm", "DERIVED_FORMULA"),
    ]:
        if check is not None:
            findings.append(EngReviewFinding(
                finding_code=f"RPM_LIMIT_{code_suffix}",
                category="RPM_LIMIT",
                severity=check.severity,
                title_key=title_key,
                message_key=check.message_key,
                observed_value=check.observed_value,
                limit_value=check.limit_or_reference,
                unit=check.observed_unit,
                source=check.limit_source,
                evidence_type=evt_type,
                limitation=check.limitations[0] if check.limitations else None,
            ))

    for check, code_suffix, title_key in [
        (vs.cutting_speed_check, "CUTTING_SPEED", "ncErFindingVc"),
        (vs.feed_per_tooth_check, "FEED_PER_TOOTH", "ncErFindingFz"),
        (vs.feed_per_rev_check, "FEED_PER_REV", "ncErFindingFeedRev"),
    ]:
        if check is not None:
            findings.append(EngReviewFinding(
                finding_code=f"REFERENCE_{code_suffix}",
                category="CUTTING_PARAMETER_REFERENCE",
                severity=check.severity,
                title_key=title_key,
                message_key=check.message_key,
                observed_value=check.observed_value,
                limit_value=check.limit_or_reference,
                unit=check.observed_unit,
                source=check.limit_source,
                evidence_type="CUTTING_PARAMETER_REFERENCE",
                limitation=check.limitations[0] if check.limitations else None,
            ))

    return findings


def _build_findings_from_motion(motion_result: NcMotionResult) -> list[EngReviewFinding]:
    findings: list[EngReviewFinding] = []

    # Unsupported / deferred feature findings
    for feat in motion_result.unsupported_features:
        if "G93_INVERSE_TIME" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_G93_DEFERRED",
                category="PARSER_COVERAGE",
                severity=NCValidationSeverity.ADVISORY,
                title_key="ncErFindingG93Deferred",
                message_key="ncPvG93Deferred",
                evidence_type="NC_PROGRAM",
            ))
        elif "G96_CSS" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_G96_DEFERRED",
                category="PARSER_COVERAGE",
                severity=NCValidationSeverity.ADVISORY,
                title_key="ncErFindingG96Deferred",
                message_key="ncPvG96Deferred",
                evidence_type="NC_PROGRAM",
            ))
        elif "G83_PECK_RAPID" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_G83_BOUNDED",
                category="PARSER_COVERAGE",
                severity=NCValidationSeverity.ADVISORY,
                title_key="ncErFindingG83Bounded",
                message_key="ncErG83BoundedMsg",
                evidence_type="NC_PROGRAM",
                limitation="G83 peck-retract rapid is controller-specific",
            ))
        elif "G84_CYCLE_TIME" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_G84_BOUNDED",
                category="PARSER_COVERAGE",
                severity=NCValidationSeverity.ADVISORY,
                title_key="ncErFindingG84Bounded",
                message_key="ncErG84BoundedMsg",
                evidence_type="NC_PROGRAM",
                limitation="G84 cycle time requires spindle model",
            ))
        elif "CANNED_CYCLE_DETECTED" in feat:
            findings.append(EngReviewFinding(
                finding_code=f"PARSER_CANNED_{feat}",
                category="PARSER_COVERAGE",
                severity=NCValidationSeverity.ADVISORY,
                title_key="ncErFindingCannedDetected",
                message_key="ncErCannedDetectedMsg",
                source=feat,
                evidence_type="NC_PROGRAM",
                limitation="Canned cycle detected but not expanded",
            ))
        elif feat in (
            "SUBPROGRAM_CALL_M98", "SUBPROGRAM_CALL_M99", "SUBPROGRAM_CALL_REJECTED",
        ) or "M98" in feat or "M99" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_SUBPROGRAM_UNSUPPORTED",
                category="UNSUPPORTED_FEATURE",
                severity=NCValidationSeverity.WARNING,
                title_key="ncErFindingSubprogramUnsupported",
                message_key="ncErSubprogramUnsupportedMsg",
                source=feat,
                evidence_type="NC_PROGRAM",
            ))
        elif "MACRO_VARIABLE" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_MACRO_UNSUPPORTED",
                category="UNSUPPORTED_FEATURE",
                severity=NCValidationSeverity.WARNING,
                title_key="ncErFindingMacroUnsupported",
                message_key="ncErMacroUnsupportedMsg",
                source=feat,
                evidence_type="NC_PROGRAM",
            ))
        elif "CONTROL_FLOW" in feat or "WHILE" in feat or "IF_REJECTED" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_CONTROL_FLOW_UNSUPPORTED",
                category="UNSUPPORTED_FEATURE",
                severity=NCValidationSeverity.WARNING,
                title_key="ncErFindingControlFlowUnsupported",
                message_key="ncErControlFlowUnsupportedMsg",
                source=feat,
                evidence_type="NC_PROGRAM",
            ))
        elif "R_FORMAT" in feat:
            findings.append(EngReviewFinding(
                finding_code="PARSER_R_ARC_DEFERRED",
                category="PARSER_COVERAGE",
                severity=NCValidationSeverity.ADVISORY,
                title_key="ncErFindingRArcDeferred",
                message_key="ncErRArcDeferredMsg",
                source=feat,
                evidence_type="NC_PROGRAM",
                limitation="R-format arcs deferred — IJK only supported",
            ))

    # Spindle-stopped-during-feed check (per segment)
    # Only flag if the segment has feed motion AND no spindle rotation was ever commanded
    # (spindle_direction is None means no M3/M4 was seen in this segment)
    for seg in motion_result.segments:
        if (
            seg.spindle_state == "M5_STOP"
            and seg.feed_motion_distance_mm > 0.0
            and seg.spindle_direction is None
        ):
            findings.append(EngReviewFinding(
                finding_code=f"FEED_SPINDLE_STOPPED_{seg.segment_id}",
                category="FEED_CONSISTENCY",
                severity=NCValidationSeverity.WARNING,
                title_key="ncErFindingSpindleStoppedFeed",
                message_key="ncErSpindleStoppedFeedMsg",
                observed_value=seg.feed_motion_distance_mm,
                unit="mm",
                source="NC_PROGRAM",
                evidence_type="NC_PROGRAM",
                segment_id=seg.segment_id,
            ))

    return findings


def _deduplicate_findings(findings: list[EngReviewFinding]) -> list[EngReviewFinding]:
    seen: set[str] = set()
    result: list[EngReviewFinding] = []
    for f in findings:
        if f.finding_code not in seen:
            seen.add(f.finding_code)
            result.append(f)
    return result


def _count_severities(findings: list[EngReviewFinding]) -> tuple[int, int, int, int, int, int]:
    blocking = warning = advisory = info = insuf = unsupported = 0
    for f in findings:
        if f.severity == NCValidationSeverity.BLOCKING:
            blocking += 1
        elif f.severity == NCValidationSeverity.WARNING:
            warning += 1
        elif f.severity == NCValidationSeverity.ADVISORY:
            advisory += 1
        elif f.severity == NCValidationSeverity.INFO:
            info += 1
        elif f.severity == NCValidationSeverity.INSUFFICIENT_DATA:
            insuf += 1
        # NOT_APPLICABLE — not counted
    # Unsupported features from motion result are warnings
    unsupported = len([f for f in findings if f.category == "UNSUPPORTED_FEATURE"])
    return blocking, warning, advisory, info, insuf, unsupported


def _compute_review_status(
    findings: list[EngReviewFinding],
    blocking: int,
    warning: int,
    advisory: int,
    info: int,
    insuf: int,
    unsupported: int,
) -> EngReviewStatus:
    """Conservative deterministic precedence — Phase 1 spec order."""
    if blocking > 0:
        return EngReviewStatus.BLOCKED_BY_KNOWN_LIMIT
    if unsupported > 0:
        return EngReviewStatus.UNSUPPORTED_FEATURES_PRESENT
    if warning > 0:
        return EngReviewStatus.REVIEW_REQUIRED
    total = blocking + warning + advisory + info + insuf
    if total > 0 and (blocking + warning + advisory + info) == 0 and insuf > 0:
        return EngReviewStatus.INSUFFICIENT_DATA
    if advisory > 0:
        return EngReviewStatus.PASS_WITH_ADVISORIES
    return EngReviewStatus.PASS_WITH_EVIDENCE


def _effective_rpm_limit(
    machine_rpm: int | None,
    tool_rpm: int | None,
    holder_rpm: int | None,
    machine_id: str | None,
    tool_id: str | None,
    holder_id: str | None,
) -> tuple[int | None, str | None]:
    """COMPATIBILITY_FORMULA_DUPLICATED=NO — recomputes effective limit from known values."""
    known: list[tuple[int, str]] = []
    if machine_rpm is not None:
        known.append((machine_rpm, f"machine:{machine_id or 'unknown'}"))
    if tool_rpm is not None:
        known.append((tool_rpm, f"cutting_tool:{tool_id or 'unknown'}"))
    if holder_rpm is not None:
        known.append((holder_rpm, f"tool_holder:{holder_id or 'unknown'}"))
    if not known:
        return None, None
    val, source = min(known, key=lambda x: x[0])
    return val, source


# ---------------------------------------------------------------------------
# Public synthesis function
# ---------------------------------------------------------------------------


def build_engineering_review(
    motion_result: NcMotionResult,
    feed_evidence: PathEvidence,
    rapid_evidence: PathEvidence,
    validation_summary: NCProgramValidationSummary,
    *,
    source_name_safe: str | None = None,
    machine_id: str | None = None,
    machine_spindle_max_rpm: int | None = None,
    machine_display: str | None = None,
    cutting_tool_id: str | None = None,
    tool_max_rpm: int | None = None,
    cutting_tool_display: str | None = None,
    tool_holder_id: str | None = None,
    holder_max_rpm: int | None = None,
    tool_holder_display: str | None = None,
    operation_association: str | None = None,
    compatibility_status: str | None = None,
    cycle_time_known_subtotal_sec: float | None = None,
    cycle_time_status: str | None = None,
    cycle_time_limitations: list[str] | None = None,
) -> NCProgramEngineeringReview:
    """Build a deterministic engineering review from existing evidence.

    NC_PARSE_RESULT_REUSED=YES
    PATH_EVIDENCE_REUSED=YES
    NC_SEGMENT_MODEL_REUSED=YES
    NC_VALIDATION_SUMMARY_REUSED=YES
    COMPATIBILITY_ENGINE_REUSED=YES
    CYCLE_TIME_FOUNDATION_REUSED=YES
    FEED_SPINDLE_VALIDATION_DUPLICATED=NO
    """
    # --- B. Parser Coverage ---
    feature_coverage = _build_feature_coverage(motion_result.unsupported_features)
    deferred_detected = [
        f for f in motion_result.unsupported_features
        if any(tag in f for tag in ("DEFERRED", "G93_", "G96_", "R_FORMAT"))
    ]
    unsupported_detected = [
        f for f in motion_result.unsupported_features
        if any(tag in f for tag in ("REJECTED", "MACRO_VARIABLE", "CONTROL_FLOW"))
    ]

    # --- E. Equipment ---
    eff_rpm, eff_source = _effective_rpm_limit(
        machine_spindle_max_rpm, tool_max_rpm, holder_max_rpm,
        machine_id, cutting_tool_id, tool_holder_id,
    )
    missing: list[str] = []
    if machine_id and machine_spindle_max_rpm is None:
        missing.append("machine_spindle_max_rpm")
    if cutting_tool_id and tool_max_rpm is None:
        missing.append("tool_max_rpm")
    if tool_holder_id and holder_max_rpm is None:
        missing.append("holder_max_rpm")

    equipment = EquipmentSummary(
        machine_id=machine_id,
        machine_display=machine_display,
        cutting_tool_id=cutting_tool_id,
        cutting_tool_display=cutting_tool_display,
        tool_holder_id=tool_holder_id,
        tool_holder_display=tool_holder_display,
        machine_spindle_max_rpm=machine_spindle_max_rpm,
        tool_max_rpm=tool_max_rpm,
        holder_max_rpm=holder_max_rpm,
        effective_rpm_limit=eff_rpm,
        effective_rpm_limit_source=eff_source,
        missing_fields=missing,
    )

    # --- K. Canned Cycle Notes ---
    canned_notes = _build_canned_cycle_notes(
        motion_result.unsupported_features, motion_result.limitations
    )

    # --- L. Findings ---
    val_findings = _build_findings_from_validation(validation_summary)
    motion_findings = _build_findings_from_motion(motion_result)
    all_findings = _deduplicate_findings(val_findings + motion_findings)

    # --- M. Counts ---
    blocking, warning, advisory, info, insuf, unsupported = _count_severities(all_findings)

    # --- N. Review Status ---
    status = _compute_review_status(
        all_findings, blocking, warning, advisory, info, insuf, unsupported
    )

    # --- Limitations ---
    limitations: list[str] = list(motion_result.limitations[:8])
    if unsupported_detected:
        limitations.append(
            f"Unsupported features detected: {', '.join(unsupported_detected[:4])}"
        )

    return NCProgramEngineeringReview(
        # A. Identity
        source_name_safe=source_name_safe,
        parser_profile=motion_result.parser_profile,
        parser_version=motion_result.parser_version,
        units_declared=motion_result.units_declared,
        analysis_status=str(motion_result.analysis_status),
        segment_count=len(motion_result.segments),
        tool_change_count=motion_result.tool_change_count,
        supported_motion_count=motion_result.supported_motion_count,
        unsupported_construct_count=motion_result.unsupported_construct_count,
        arc_motion_count=motion_result.arc_motion_count,
        # B. Parser coverage
        feature_coverage=feature_coverage,
        deferred_features_detected=deferred_detected,
        unsupported_features_detected=unsupported_detected,
        # C. Motion summary
        total_feed_distance_mm=motion_result.feed_distance_mm,
        total_rapid_distance_mm=motion_result.rapid_distance_mm,
        # D. Segments
        segments=list(motion_result.segments),
        # E. Equipment
        equipment=equipment,
        # F. Compatibility
        compatibility_status=compatibility_status,
        # G. Validation (reused)
        validation_summary=validation_summary,
        # H. Operation mapping
        operation_association=operation_association,
        # I. Cycle time
        cycle_time_known_subtotal_sec=cycle_time_known_subtotal_sec,
        cycle_time_status=cycle_time_status,
        cycle_time_limitations=list(cycle_time_limitations or []),
        # K. Canned cycles
        canned_cycle_notes=canned_notes,
        # L. Findings
        findings=all_findings,
        # M. Counts
        blocking_count=blocking,
        warning_count=warning,
        advisory_count=advisory,
        info_count=info,
        insufficient_data_count=insuf,
        unsupported_count=unsupported,
        # M. Limitations
        limitations=limitations,
        # N. Status
        review_status=status,
        # Safety flags
        nc_file_executed=False,
        machine_behavior_simulated=False,
        collision_check_performed=False,
        machine_kinematics_simulated=False,
        gouge_check_performed=False,
        false_controller_compatibility_claim=False,
        false_production_approval_claim=False,
        false_safe_to_run_claim=False,
        false_collision_free_claim=False,
        arbitrary_numeric_engineering_score_implemented=False,
        programmed_motion_equals_executed_motion=False,
        programmed_feed_distance_equals_confirmed_cutting=False,
        t_word_equals_confirmed_tool_identity=False,
        partial_time_mislabeled_total=False,
        bounded_canned_cycle_mislabeled_complete=False,
        private_local_path_visible=False,
        private_path_in_api_response=False,
    )
