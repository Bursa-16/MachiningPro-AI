"""NC Program Change Management Review.

NC_PROGRAM_CHANGE_MANAGEMENT_01 — Phase 2

Deterministic comparison of two NCProgramEngineeringReview snapshots.
Does NOT reimplement NC parsing, validation, or compatibility checks.

Safety constants:
    PROGRAMMED_MOTION_DELTA_EQUALS_EXECUTED_MOTION_DELTA=NO
    COMMANDED_FEED_DELTA_EQUALS_ACTUAL_FEED_DELTA=NO
    COMMANDED_RPM_DELTA_EQUALS_ACTUAL_RPM_DELTA=NO
    T_WORD_CHANGE_EQUALS_CONFIRMED_TOOL_CHANGE=NO
    PARTIAL_CYCLE_TIME_DELTA_EXPORTED_AS_TOTAL_DELTA=NO
    FALSE_CHANGE_APPROVAL_CLAIM=NO
    FALSE_SAFE_CHANGE_CLAIM=NO
    FALSE_CONTROLLER_CERTIFICATION_CLAIM=NO
    FALSE_COLLISION_FREE_CHANGE_CLAIM=NO
    PRIVATE_LOCAL_PATH_VISIBLE=NO
    WINDOWS_USERNAME_EXPORTED=NO
    CREDENTIAL_EXPORTED=NO
    AUTH_TOKEN_EXPORTED=NO
    RAW_NC_LOGGED_IN_CHANGE_EVENT=NO
    ARBITRARY_CHANGE_SCORE_IMPLEMENTED=NO
    NC_CHANGE_REVIEW_IS_NOT_APPROVAL=YES
    NC_CHANGE_REVIEW_IS_NOT_SAFETY_CERTIFICATION=YES
"""

from __future__ import annotations

import difflib
import hashlib
import re
import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from backend.process_planning.engineering_review import (
    NCProgramEngineeringReview,
    ParserFeatureCoverage,
)

__all__ = [
    "ComparabilityStatus",
    "OverallChangeStatus",
    "ChangeSeverity",
    "NcBlockChangeType",
    "SemanticChangeType",
    "NcBlockClass",
    "SegmentChangeType",
    "FindingChangeType",
    "ConfigFieldChange",
    "NcBlockChange",
    "NcSegmentChange",
    "NcFindingChange",
    "NcCoverageChange",
    "FeedSpindleChangeSummary",
    "CycleTimeChangeSummary",
    "NcChangeSummary",
    "NCProgramChangeReview",
    "compare_engineering_reviews",
    "CHANGE_REVIEW_SCHEMA_VERSION",
]

CHANGE_REVIEW_SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ComparabilityStatus(StrEnum):
    COMPARABLE = "COMPARABLE"
    PARTIALLY_COMPARABLE = "PARTIALLY_COMPARABLE"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class OverallChangeStatus(StrEnum):
    NO_ENGINEERING_CHANGE = "NO_ENGINEERING_CHANGE"
    ENGINEERING_CHANGE_DETECTED = "ENGINEERING_CHANGE_DETECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    COMPARISON_INCOMPLETE = "COMPARISON_INCOMPLETE"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class ChangeSeverity(StrEnum):
    CRITICAL_REVIEW_REQUIRED = "CRITICAL_REVIEW_REQUIRED"
    MAJOR_REVIEW_REQUIRED = "MAJOR_REVIEW_REQUIRED"
    MINOR_CHANGE = "MINOR_CHANGE"
    INFORMATIONAL_CHANGE = "INFORMATIONAL_CHANGE"
    NO_CHANGE = "NO_CHANGE"
    UNKNOWN = "UNKNOWN"


class NcBlockChangeType(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"


class SemanticChangeType(StrEnum):
    SEMANTIC_CHANGE = "SEMANTIC_CHANGE"
    FORMAT_ONLY_CHANGE = "FORMAT_ONLY_CHANGE"
    COMMENT_CHANGE = "COMMENT_CHANGE"
    UNKNOWN_CHANGE = "UNKNOWN_CHANGE"


class NcBlockClass(StrEnum):
    RAPID_MOTION = "RAPID_MOTION"
    FEED_MOTION = "FEED_MOTION"
    ARC_MOTION = "ARC_MOTION"
    CANNED_CYCLE = "CANNED_CYCLE"
    FEED_MODE = "FEED_MODE"
    FEED_RATE = "FEED_RATE"
    SPINDLE = "SPINDLE"
    SPINDLE_CONTROL = "SPINDLE_CONTROL"
    TOOL_CHANGE = "TOOL_CHANGE"
    UNIT_DECLARATION = "UNIT_DECLARATION"
    POSITIONING_MODE = "POSITIONING_MODE"
    MODAL_CHANGE = "MODAL_CHANGE"
    PROGRAM_DELIMITER = "PROGRAM_DELIMITER"
    PROGRAM_END = "PROGRAM_END"
    COMMENT_ONLY = "COMMENT_ONLY"
    UNKNOWN = "UNKNOWN"


class SegmentChangeType(StrEnum):
    SEGMENT_ADDED = "SEGMENT_ADDED"
    SEGMENT_REMOVED = "SEGMENT_REMOVED"
    SEGMENT_MODIFIED = "SEGMENT_MODIFIED"
    SEGMENT_UNCHANGED = "SEGMENT_UNCHANGED"
    SEGMENT_MATCH_UNCERTAIN = "SEGMENT_MATCH_UNCERTAIN"


class FindingChangeType(StrEnum):
    FINDING_ADDED = "FINDING_ADDED"
    FINDING_RESOLVED = "FINDING_RESOLVED"
    FINDING_UNCHANGED = "FINDING_UNCHANGED"
    FINDING_SEVERITY_CHANGED = "FINDING_SEVERITY_CHANGED"
    FINDING_VALUE_CHANGED = "FINDING_VALUE_CHANGED"
    FINDING_LIMIT_CHANGED = "FINDING_LIMIT_CHANGED"
    FINDING_SOURCE_CHANGED = "FINDING_SOURCE_CHANGED"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ConfigFieldChange(BaseModel):
    field_name: str
    baseline_value: str | None = None
    current_value: str | None = None
    changed: bool


class NcBlockChange(BaseModel):
    change_type: NcBlockChangeType
    baseline_line_index: int | None = None   # 1-indexed
    current_line_index: int | None = None    # 1-indexed
    baseline_text: str | None = None         # normalized
    current_text: str | None = None          # normalized
    block_classification: NcBlockClass = NcBlockClass.UNKNOWN
    semantic_change_type: SemanticChangeType = SemanticChangeType.UNKNOWN_CHANGE
    baseline_review_id: str | None = None
    current_review_id: str | None = None
    baseline_analysis_fingerprint: str | None = None
    current_analysis_fingerprint: str | None = None


class NcSegmentChange(BaseModel):
    baseline_segment_id: str | None = None
    current_segment_id: str | None = None
    change_type: SegmentChangeType
    tool_id_raw_changed: bool = False
    baseline_tool_id_raw: str | None = None
    current_tool_id_raw: str | None = None
    feed_distance_delta_mm: float | None = None
    rapid_distance_delta_mm: float | None = None
    feed_distance_note: str = "PROGRAMMED_DELTA_NOT_EXECUTED_DELTA"
    commanded_feed_changed: bool = False
    commanded_spindle_changed: bool = False
    analysis_status_changed: bool = False
    new_unsupported_features: list[str] = []
    baseline_review_id: str | None = None
    current_review_id: str | None = None
    baseline_analysis_fingerprint: str | None = None
    current_analysis_fingerprint: str | None = None


class NcFindingChange(BaseModel):
    finding_code: str
    category: str
    change_type: FindingChangeType
    baseline_severity: str | None = None
    current_severity: str | None = None
    baseline_observed_value: float | None = None
    current_observed_value: float | None = None
    baseline_limit_value: float | None = None
    current_limit_value: float | None = None
    unit: str | None = None
    source_changed: bool = False
    baseline_review_id: str | None = None
    current_review_id: str | None = None
    baseline_analysis_fingerprint: str | None = None
    current_analysis_fingerprint: str | None = None


class NcCoverageChange(BaseModel):
    feature: str
    change_type: Literal[
        "FEATURE_STATE_CHANGED", "FEATURE_NEWLY_DETECTED",
        "FEATURE_NO_LONGER_DETECTED", "FEATURE_UNCHANGED"
    ]
    baseline_state: str | None = None
    current_state: str | None = None
    baseline_detected: bool = False
    current_detected: bool = False
    baseline_review_id: str | None = None
    current_review_id: str | None = None
    baseline_analysis_fingerprint: str | None = None
    current_analysis_fingerprint: str | None = None


class FeedSpindleChangeSummary(BaseModel):
    feed_mode_changed: bool = False
    baseline_feed_mode: str | None = None
    current_feed_mode: str | None = None
    commanded_feed_mm_min_changed: bool = False
    baseline_commanded_feed_mm_min: float | None = None
    current_commanded_feed_mm_min: float | None = None
    commanded_feed_mm_rev_changed: bool = False
    baseline_commanded_feed_mm_rev: float | None = None
    current_commanded_feed_mm_rev: float | None = None
    commanded_spindle_rpm_changed: bool = False
    baseline_commanded_spindle_rpm: float | None = None
    current_commanded_spindle_rpm: float | None = None
    spindle_state_changed: bool = False
    effective_rpm_limit_changed: bool = False
    baseline_effective_rpm_limit: int | None = None
    current_effective_rpm_limit: int | None = None
    # Safety
    commanded_feed_delta_equals_actual_feed_delta: bool = False
    commanded_rpm_delta_equals_actual_rpm_delta: bool = False


class CycleTimeChangeSummary(BaseModel):
    baseline_known_subtotal_sec: float | None = None
    current_known_subtotal_sec: float | None = None
    delta_sec: float | None = None   # None if either is None/partial
    baseline_status: str | None = None
    current_status: str | None = None
    comparable: bool = False
    note: str = ""
    # Safety
    partial_cycle_time_delta_exported_as_total_delta: bool = False


class NcChangeSummary(BaseModel):
    blocks_added: int | None = None
    blocks_removed: int | None = None
    blocks_modified: int | None = None
    blocks_unchanged: int | None = None
    segments_added: int = 0
    segments_removed: int = 0
    segments_modified: int = 0
    new_findings: int = 0
    resolved_findings: int = 0
    unchanged_findings: int = 0
    changed_findings: int = 0
    new_blocking_findings: int = 0
    resolved_blocking_findings: int = 0
    unchanged_blocking_findings: int = 0
    new_warning_findings: int = 0
    resolved_warning_findings: int = 0
    new_advisory_findings: int = 0
    resolved_advisory_findings: int = 0
    coverage_changes: int = 0
    configuration_changes: int = 0
    feed_changed: bool = False
    spindle_changed: bool = False
    cycle_time_changed: bool | None = None


# ---------------------------------------------------------------------------
# Main model
# ---------------------------------------------------------------------------


class NCProgramChangeReview(BaseModel):
    """Deterministic NC Program Change Review.

    ARBITRARY_CHANGE_SCORE_IMPLEMENTED=NO
    NC_CHANGE_REVIEW_IS_NOT_APPROVAL=YES
    NC_CHANGE_REVIEW_IS_NOT_SAFETY_CERTIFICATION=YES
    FALSE_CHANGE_APPROVAL_CLAIM=NO
    FALSE_SAFE_CHANGE_CLAIM=NO
    FALSE_CONTROLLER_CERTIFICATION_CLAIM=NO
    """

    change_review_id: str          # UUID v4
    comparison_schema_version: str = CHANGE_REVIEW_SCHEMA_VERSION
    comparison_fingerprint: str | None = None  # SHA-256(b_af|c_af|schema)

    baseline_review_id: str | None = None
    current_review_id: str | None = None
    baseline_analysis_fingerprint: str | None = None
    current_analysis_fingerprint: str | None = None
    baseline_program_fingerprint: str | None = None
    current_program_fingerprint: str | None = None
    baseline_configuration_fingerprint: str | None = None
    current_configuration_fingerprint: str | None = None
    baseline_review_schema_version: str | None = None
    current_review_schema_version: str | None = None
    baseline_parser_version: str | None = None
    current_parser_version: str | None = None
    baseline_parser_profile: str | None = None
    current_parser_profile: str | None = None
    baseline_generated_at: str | None = None
    current_generated_at: str | None = None

    # High-level change status
    program_change_status: str   # TraceabilityChangeState values
    configuration_change_status: str
    version_change_status: str   # NO_VERSION_CHANGE | PARSER_VERSION_CHANGED |
                                  # SCHEMA_VERSION_CHANGED | PROFILE_CHANGED

    # Detail lists
    configuration_changes: list[ConfigFieldChange] = []
    block_changes: list[NcBlockChange] | None = None   # None if NC text not available
    segment_changes: list[NcSegmentChange] = []
    finding_changes: list[NcFindingChange] = []
    coverage_changes: list[NcCoverageChange] = []
    feed_spindle_changes: FeedSpindleChangeSummary | None = None
    cycle_time_changes: CycleTimeChangeSummary | None = None

    change_summary: NcChangeSummary
    comparability_status: ComparabilityStatus
    comparability_notes: list[str] = []
    change_severity: ChangeSeverity
    overall_change_status: OverallChangeStatus
    review_required: bool
    review_required_reasons: list[str] = []
    limitations: list[str] = []

    # Safety flags
    programmed_motion_delta_equals_executed_motion_delta: bool = False
    commanded_feed_delta_equals_actual_feed_delta: bool = False
    commanded_rpm_delta_equals_actual_rpm_delta: bool = False
    t_word_change_equals_confirmed_tool_change: bool = False
    partial_cycle_time_delta_exported_as_total_delta: bool = False
    false_change_approval_claim: bool = False
    false_safe_change_claim: bool = False
    false_controller_certification_claim: bool = False
    false_collision_free_change_claim: bool = False
    nc_change_review_is_not_approval: bool = True
    nc_change_review_is_not_safety_certification: bool = True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Conservative normalization — same policy as engineering_review.py
def _normalize_nc_lines(nc_text: str) -> list[str]:
    text = nc_text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("﻿"):
        text = text[1:]
    return [line.rstrip() for line in text.split("\n")]


# Regex for block classification
_RE_G0 = re.compile(r'\bG0*0\b', re.IGNORECASE)
_RE_G1 = re.compile(r'\bG0*1\b', re.IGNORECASE)
_RE_G23 = re.compile(r'\bG0*[23]\b', re.IGNORECASE)
_RE_G8X = re.compile(r'\bG8[0-9]\b', re.IGNORECASE)
_RE_G9X = re.compile(r'\bG9[34]\b', re.IGNORECASE)
_RE_F_WORD = re.compile(r'\bF[\d.]', re.IGNORECASE)
_RE_S_WORD = re.compile(r'\bS[\d]', re.IGNORECASE)
_RE_T_WORD = re.compile(r'\bT\d|\bM0*6\b', re.IGNORECASE)
_RE_UNITS = re.compile(r'\bG2[01]\b', re.IGNORECASE)
_RE_POSITIONING = re.compile(r'\bG9[01]\b', re.IGNORECASE)
_RE_SPINDLE_CTRL = re.compile(r'\bM0*[345]\b', re.IGNORECASE)
_RE_PROG_END = re.compile(r'\bM0*30\b|\bM0*2\b', re.IGNORECASE)
_RE_COMMENT = re.compile(r'^[\s;(]|^\s*%')
_RE_PROG_DELIM = re.compile(r'^\s*%|^\s*O\d', re.IGNORECASE)
_RE_SEMANTIC = re.compile(r'\b[GMSFT]\d', re.IGNORECASE)
_RE_COORD = re.compile(r'\b[XYZIJKRabcABC]-?[\d.]+', re.IGNORECASE)


def _classify_block(text: str) -> NcBlockClass:
    t = text.strip()
    if not t:
        return NcBlockClass.UNKNOWN
    if _RE_COMMENT.match(t) and not _RE_SEMANTIC.search(t) and not _RE_COORD.search(t):
        return NcBlockClass.COMMENT_ONLY
    if _RE_PROG_DELIM.match(t):
        return NcBlockClass.PROGRAM_DELIMITER
    if _RE_PROG_END.search(t):
        return NcBlockClass.PROGRAM_END
    if _RE_T_WORD.search(t):
        return NcBlockClass.TOOL_CHANGE
    if _RE_G8X.search(t):
        return NcBlockClass.CANNED_CYCLE
    if _RE_G0.search(t):
        return NcBlockClass.RAPID_MOTION
    if _RE_G1.search(t):
        return NcBlockClass.FEED_MOTION
    if _RE_G23.search(t):
        return NcBlockClass.ARC_MOTION
    if _RE_G9X.search(t):
        return NcBlockClass.FEED_MODE
    if _RE_F_WORD.search(t):
        return NcBlockClass.FEED_RATE
    if _RE_S_WORD.search(t):
        return NcBlockClass.SPINDLE
    if _RE_SPINDLE_CTRL.search(t):
        return NcBlockClass.SPINDLE_CONTROL
    if _RE_UNITS.search(t):
        return NcBlockClass.UNIT_DECLARATION
    if _RE_POSITIONING.search(t):
        return NcBlockClass.POSITIONING_MODE
    if re.search(r'\b[GM]\d', t, re.IGNORECASE):
        return NcBlockClass.MODAL_CHANGE
    return NcBlockClass.UNKNOWN


def _classify_semantic(baseline_text: str | None, current_text: str | None) -> SemanticChangeType:
    b = (baseline_text or "").strip()
    c = (current_text or "").strip()
    # Check comment-only change
    b_sem = bool(_RE_SEMANTIC.search(b) or _RE_COORD.search(b))
    c_sem = bool(_RE_SEMANTIC.search(c) or _RE_COORD.search(c))
    if not b_sem and not c_sem:
        return SemanticChangeType.COMMENT_CHANGE
    if _RE_COMMENT.match(b) and _RE_COMMENT.match(c):
        return SemanticChangeType.COMMENT_CHANGE
    # If G/M/S/F/T words changed → SEMANTIC_CHANGE
    b_words = set(re.findall(r'\b[GMSFT][\d.]+', b, re.IGNORECASE))
    c_words = set(re.findall(r'\b[GMSFT][\d.]+', c, re.IGNORECASE))
    b_coords = set(re.findall(r'\b[XYZIJKRBC]-?[\d.]+', b, re.IGNORECASE))
    c_coords = set(re.findall(r'\b[XYZIJKRBC]-?[\d.]+', c, re.IGNORECASE))
    if b_words != c_words or b_coords != c_coords:
        return SemanticChangeType.SEMANTIC_CHANGE
    # N-word only? FORMAT_ONLY_CHANGE
    b_n = re.sub(r'\bN\d+\b', '', b, flags=re.IGNORECASE).strip()
    c_n = re.sub(r'\bN\d+\b', '', c, flags=re.IGNORECASE).strip()
    if b_n == c_n:
        return SemanticChangeType.FORMAT_ONLY_CHANGE
    return SemanticChangeType.UNKNOWN_CHANGE


def _compute_comparison_fingerprint(
    baseline_af: str | None,
    current_af: str | None,
    schema_version: str,
) -> str:
    raw = f"{baseline_af or 'null'}|{current_af or 'null'}|{schema_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _diff_nc_blocks(
    baseline_lines: list[str],
    current_lines: list[str],
    baseline_review_id: str | None,
    current_review_id: str | None,
    baseline_af: str | None,
    current_af: str | None,
    max_blocks: int = 5000,
) -> list[NcBlockChange]:
    """Deterministic block diff using difflib.SequenceMatcher."""
    b_lines = baseline_lines[:max_blocks]
    c_lines = current_lines[:max_blocks]

    matcher = difflib.SequenceMatcher(None, b_lines, c_lines, autojunk=False)
    changes: list[NcBlockChange] = []

    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            for k in range(i2 - i1):
                changes.append(NcBlockChange(
                    change_type=NcBlockChangeType.UNCHANGED,
                    baseline_line_index=i1 + k + 1,
                    current_line_index=j1 + k + 1,
                    baseline_text=b_lines[i1 + k],
                    current_text=c_lines[j1 + k],
                    block_classification=_classify_block(b_lines[i1 + k]),
                    semantic_change_type=SemanticChangeType.FORMAT_ONLY_CHANGE,
                    baseline_review_id=baseline_review_id,
                    current_review_id=current_review_id,
                    baseline_analysis_fingerprint=baseline_af,
                    current_analysis_fingerprint=current_af,
                ))
        elif opcode == "insert":
            for k in range(j2 - j1):
                text = c_lines[j1 + k]
                changes.append(NcBlockChange(
                    change_type=NcBlockChangeType.ADDED,
                    baseline_line_index=None,
                    current_line_index=j1 + k + 1,
                    baseline_text=None,
                    current_text=text,
                    block_classification=_classify_block(text),
                    semantic_change_type=SemanticChangeType.SEMANTIC_CHANGE,
                    baseline_review_id=baseline_review_id,
                    current_review_id=current_review_id,
                    baseline_analysis_fingerprint=baseline_af,
                    current_analysis_fingerprint=current_af,
                ))
        elif opcode == "delete":
            for k in range(i2 - i1):
                text = b_lines[i1 + k]
                changes.append(NcBlockChange(
                    change_type=NcBlockChangeType.REMOVED,
                    baseline_line_index=i1 + k + 1,
                    current_line_index=None,
                    baseline_text=text,
                    current_text=None,
                    block_classification=_classify_block(text),
                    semantic_change_type=SemanticChangeType.SEMANTIC_CHANGE,
                    baseline_review_id=baseline_review_id,
                    current_review_id=current_review_id,
                    baseline_analysis_fingerprint=baseline_af,
                    current_analysis_fingerprint=current_af,
                ))
        elif opcode == "replace":
            # Pair up as modified (zip shorter with longer; rest become added/removed)
            b_chunk = b_lines[i1:i2]
            c_chunk = c_lines[j1:j2]
            for k in range(max(len(b_chunk), len(c_chunk))):
                if k < len(b_chunk) and k < len(c_chunk):
                    bt = b_chunk[k]
                    ct = c_chunk[k]
                    changes.append(NcBlockChange(
                        change_type=NcBlockChangeType.MODIFIED,
                        baseline_line_index=i1 + k + 1,
                        current_line_index=j1 + k + 1,
                        baseline_text=bt,
                        current_text=ct,
                        block_classification=_classify_block(ct),
                        semantic_change_type=_classify_semantic(bt, ct),
                        baseline_review_id=baseline_review_id,
                        current_review_id=current_review_id,
                        baseline_analysis_fingerprint=baseline_af,
                        current_analysis_fingerprint=current_af,
                    ))
                elif k < len(b_chunk):
                    text = b_chunk[k]
                    changes.append(NcBlockChange(
                        change_type=NcBlockChangeType.REMOVED,
                        baseline_line_index=i1 + k + 1,
                        current_line_index=None,
                        baseline_text=text,
                        current_text=None,
                        block_classification=_classify_block(text),
                        semantic_change_type=SemanticChangeType.SEMANTIC_CHANGE,
                        baseline_review_id=baseline_review_id,
                        current_review_id=current_review_id,
                        baseline_analysis_fingerprint=baseline_af,
                        current_analysis_fingerprint=current_af,
                    ))
                else:
                    text = c_chunk[k]
                    changes.append(NcBlockChange(
                        change_type=NcBlockChangeType.ADDED,
                        baseline_line_index=None,
                        current_line_index=j1 + k + 1,
                        baseline_text=None,
                        current_text=text,
                        block_classification=_classify_block(text),
                        semantic_change_type=SemanticChangeType.SEMANTIC_CHANGE,
                        baseline_review_id=baseline_review_id,
                        current_review_id=current_review_id,
                        baseline_analysis_fingerprint=baseline_af,
                        current_analysis_fingerprint=current_af,
                    ))
    return changes


def _diff_segments(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
    baseline_review_id: str | None,
    current_review_id: str | None,
    baseline_af: str | None,
    current_af: str | None,
) -> list[NcSegmentChange]:
    b_segs = baseline.segments
    c_segs = current.segments
    b_by_id = {s.segment_id: s for s in b_segs}
    c_by_id = {s.segment_id: s for s in c_segs}
    results: list[NcSegmentChange] = []

    b_tc = baseline.tool_change_count
    c_tc = current.tool_change_count
    tc_changed = b_tc != c_tc

    all_ids = list(dict.fromkeys(
        [s.segment_id for s in b_segs] + [s.segment_id for s in c_segs]
    ))

    for seg_id in all_ids:
        b_seg = b_by_id.get(seg_id)
        c_seg = c_by_id.get(seg_id)

        if b_seg is None and c_seg is not None:
            results.append(NcSegmentChange(
                baseline_segment_id=None,
                current_segment_id=seg_id,
                change_type=SegmentChangeType.SEGMENT_ADDED,
                baseline_review_id=baseline_review_id,
                current_review_id=current_review_id,
                baseline_analysis_fingerprint=baseline_af,
                current_analysis_fingerprint=current_af,
            ))
        elif b_seg is not None and c_seg is None:
            results.append(NcSegmentChange(
                baseline_segment_id=seg_id,
                current_segment_id=None,
                change_type=SegmentChangeType.SEGMENT_REMOVED,
                baseline_review_id=baseline_review_id,
                current_review_id=current_review_id,
                baseline_analysis_fingerprint=baseline_af,
                current_analysis_fingerprint=current_af,
            ))
        elif b_seg is not None and c_seg is not None:
            # If tool_change_count differs, mark uncertain
            ctype = (
                SegmentChangeType.SEGMENT_MATCH_UNCERTAIN
                if tc_changed
                else SegmentChangeType.SEGMENT_UNCHANGED
            )
            tool_changed = b_seg.tool_id_raw != c_seg.tool_id_raw
            feed_delta = c_seg.feed_motion_distance_mm - b_seg.feed_motion_distance_mm
            rapid_delta = c_seg.rapid_motion_distance_mm - b_seg.rapid_motion_distance_mm
            # Determine if modified
            cmd_feed_changed = (
                b_seg.commanded_feed_min != c_seg.commanded_feed_min or
                b_seg.commanded_feed_max != c_seg.commanded_feed_max or
                b_seg.feed_mode != c_seg.feed_mode
            )
            cmd_spin_changed = b_seg.commanded_spindle_rpm != c_seg.commanded_spindle_rpm
            status_changed = b_seg.analysis_status != c_seg.analysis_status
            new_unsupported = [
                f for f in c_seg.unsupported_features
                if f not in b_seg.unsupported_features
            ]
            is_modified = (
                tool_changed or abs(feed_delta) > 1e-9 or abs(rapid_delta) > 1e-9 or
                cmd_feed_changed or cmd_spin_changed or status_changed or new_unsupported
            )
            if is_modified and not tc_changed:
                ctype = SegmentChangeType.SEGMENT_MODIFIED
            elif is_modified and tc_changed:
                ctype = SegmentChangeType.SEGMENT_MATCH_UNCERTAIN
            elif not tc_changed:
                ctype = SegmentChangeType.SEGMENT_UNCHANGED

            results.append(NcSegmentChange(
                baseline_segment_id=seg_id,
                current_segment_id=seg_id,
                change_type=ctype,
                tool_id_raw_changed=tool_changed,
                baseline_tool_id_raw=b_seg.tool_id_raw,
                current_tool_id_raw=c_seg.tool_id_raw,
                feed_distance_delta_mm=round(feed_delta, 6),
                rapid_distance_delta_mm=round(rapid_delta, 6),
                feed_distance_note="PROGRAMMED_DELTA_NOT_EXECUTED_DELTA",
                commanded_feed_changed=cmd_feed_changed,
                commanded_spindle_changed=cmd_spin_changed,
                analysis_status_changed=status_changed,
                new_unsupported_features=new_unsupported,
                baseline_review_id=baseline_review_id,
                current_review_id=current_review_id,
                baseline_analysis_fingerprint=baseline_af,
                current_analysis_fingerprint=current_af,
            ))
    return results


def _diff_findings(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
    baseline_review_id: str | None,
    current_review_id: str | None,
    baseline_af: str | None,
    current_af: str | None,
) -> list[NcFindingChange]:
    b_map = {f.finding_code: f for f in baseline.findings}
    c_map = {f.finding_code: f for f in current.findings}
    results: list[NcFindingChange] = []

    all_codes = list(dict.fromkeys(list(b_map) + list(c_map)))
    for code in all_codes:
        b_f = b_map.get(code)
        c_f = c_map.get(code)
        if b_f is None and c_f is not None:
            results.append(NcFindingChange(
                finding_code=code,
                category=c_f.category,
                change_type=FindingChangeType.FINDING_ADDED,
                current_severity=c_f.severity.value,
                current_observed_value=c_f.observed_value,
                current_limit_value=c_f.limit_value,
                unit=c_f.unit,
                baseline_review_id=baseline_review_id,
                current_review_id=current_review_id,
                baseline_analysis_fingerprint=baseline_af,
                current_analysis_fingerprint=current_af,
            ))
        elif b_f is not None and c_f is None:
            results.append(NcFindingChange(
                finding_code=code,
                category=b_f.category,
                change_type=FindingChangeType.FINDING_RESOLVED,
                baseline_severity=b_f.severity.value,
                baseline_observed_value=b_f.observed_value,
                baseline_limit_value=b_f.limit_value,
                unit=b_f.unit,
                baseline_review_id=baseline_review_id,
                current_review_id=current_review_id,
                baseline_analysis_fingerprint=baseline_af,
                current_analysis_fingerprint=current_af,
            ))
        elif b_f is not None and c_f is not None:
            sev_changed = b_f.severity != c_f.severity
            val_changed = b_f.observed_value != c_f.observed_value
            lim_changed = b_f.limit_value != c_f.limit_value
            src_changed = b_f.source != c_f.source
            if sev_changed:
                ctype = FindingChangeType.FINDING_SEVERITY_CHANGED
            elif val_changed:
                ctype = FindingChangeType.FINDING_VALUE_CHANGED
            elif lim_changed:
                ctype = FindingChangeType.FINDING_LIMIT_CHANGED
            elif src_changed:
                ctype = FindingChangeType.FINDING_SOURCE_CHANGED
            else:
                ctype = FindingChangeType.FINDING_UNCHANGED
            results.append(NcFindingChange(
                finding_code=code,
                category=c_f.category,
                change_type=ctype,
                baseline_severity=b_f.severity.value,
                current_severity=c_f.severity.value,
                baseline_observed_value=b_f.observed_value,
                current_observed_value=c_f.observed_value,
                baseline_limit_value=b_f.limit_value,
                current_limit_value=c_f.limit_value,
                unit=c_f.unit,
                source_changed=src_changed,
                baseline_review_id=baseline_review_id,
                current_review_id=current_review_id,
                baseline_analysis_fingerprint=baseline_af,
                current_analysis_fingerprint=current_af,
            ))
    return results


def _diff_coverage(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
    baseline_review_id: str | None,
    current_review_id: str | None,
    baseline_af: str | None,
    current_af: str | None,
) -> list[NcCoverageChange]:
    b_map: dict[str, ParserFeatureCoverage] = {f.feature: f for f in baseline.feature_coverage}
    c_map: dict[str, ParserFeatureCoverage] = {f.feature: f for f in current.feature_coverage}
    results: list[NcCoverageChange] = []
    all_features = list(dict.fromkeys(list(b_map) + list(c_map)))
    for feat in all_features:
        b_fc = b_map.get(feat)
        c_fc = c_map.get(feat)
        b_state = b_fc.state.value if b_fc else None
        c_state = c_fc.state.value if c_fc else None
        b_det = b_fc.detected if b_fc else False
        c_det = c_fc.detected if c_fc else False
        state_changed = b_state != c_state
        det_changed = b_det != c_det
        if not state_changed and not det_changed:
            ctype = "FEATURE_UNCHANGED"
        elif det_changed and c_det and not b_det:
            ctype = "FEATURE_NEWLY_DETECTED"
        elif det_changed and b_det and not c_det:
            ctype = "FEATURE_NO_LONGER_DETECTED"
        else:
            ctype = "FEATURE_STATE_CHANGED"
        results.append(NcCoverageChange(
            feature=feat,
            change_type=ctype,  # type: ignore[arg-type]
            baseline_state=b_state,
            current_state=c_state,
            baseline_detected=b_det,
            current_detected=c_det,
            baseline_review_id=baseline_review_id,
            current_review_id=current_review_id,
            baseline_analysis_fingerprint=baseline_af,
            current_analysis_fingerprint=current_af,
        ))
    return results


def _diff_feed_spindle(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
) -> FeedSpindleChangeSummary:
    b_v = baseline.validation_summary
    c_v = current.validation_summary
    return FeedSpindleChangeSummary(
        feed_mode_changed=b_v.nc_feed_mode != c_v.nc_feed_mode,
        baseline_feed_mode=b_v.nc_feed_mode,
        current_feed_mode=c_v.nc_feed_mode,
        commanded_feed_mm_min_changed=b_v.nc_commanded_feed_mm_min != c_v.nc_commanded_feed_mm_min,
        baseline_commanded_feed_mm_min=b_v.nc_commanded_feed_mm_min,
        current_commanded_feed_mm_min=c_v.nc_commanded_feed_mm_min,
        commanded_feed_mm_rev_changed=b_v.nc_commanded_feed_mm_rev != c_v.nc_commanded_feed_mm_rev,
        baseline_commanded_feed_mm_rev=b_v.nc_commanded_feed_mm_rev,
        current_commanded_feed_mm_rev=c_v.nc_commanded_feed_mm_rev,
        commanded_spindle_rpm_changed=b_v.nc_commanded_spindle_rpm != c_v.nc_commanded_spindle_rpm,
        baseline_commanded_spindle_rpm=b_v.nc_commanded_spindle_rpm,
        current_commanded_spindle_rpm=c_v.nc_commanded_spindle_rpm,
        spindle_state_changed=b_v.nc_spindle_state != c_v.nc_spindle_state,
        effective_rpm_limit_changed=(
            baseline.equipment.effective_rpm_limit != current.equipment.effective_rpm_limit
        ),
        baseline_effective_rpm_limit=baseline.equipment.effective_rpm_limit,
        current_effective_rpm_limit=current.equipment.effective_rpm_limit,
        commanded_feed_delta_equals_actual_feed_delta=False,
        commanded_rpm_delta_equals_actual_rpm_delta=False,
    )


def _diff_cycle_time(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
) -> CycleTimeChangeSummary:
    b_sec = baseline.cycle_time_known_subtotal_sec
    c_sec = current.cycle_time_known_subtotal_sec
    comparable = b_sec is not None and c_sec is not None
    delta = round(c_sec - b_sec, 6) if comparable else None
    return CycleTimeChangeSummary(
        baseline_known_subtotal_sec=b_sec,
        current_known_subtotal_sec=c_sec,
        delta_sec=delta,
        baseline_status=baseline.cycle_time_status,
        current_status=current.cycle_time_status,
        comparable=comparable,
        note=(
            "" if comparable
            else "PARTIAL_CYCLE_TIME_NOT_COMPARABLE"
        ),
        partial_cycle_time_delta_exported_as_total_delta=False,
    )


def _diff_config(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
    baseline_traceability: object | None,
    current_traceability: object | None,
) -> list[ConfigFieldChange]:
    b_eq = baseline.equipment
    c_eq = current.equipment

    def _get_t(t: object | None, field: str) -> str | None:
        if t is None:
            return None
        return getattr(t, field, None)

    fields = [
        ("machine_id", b_eq.machine_id, c_eq.machine_id),
        ("cutting_tool_id", b_eq.cutting_tool_id, c_eq.cutting_tool_id),
        ("tool_holder_id", b_eq.tool_holder_id, c_eq.tool_holder_id),
        ("operation", baseline.operation_association, current.operation_association),
        ("process_step_id",
         _get_t(baseline_traceability, "process_step_id"),
         _get_t(current_traceability, "process_step_id")),
        ("material_iso_group",
         _get_t(baseline_traceability, "material_iso_group"),
         _get_t(current_traceability, "material_iso_group")),
    ]
    return [
        ConfigFieldChange(field_name=name, baseline_value=bv, current_value=cv, changed=(bv != cv))
        for name, bv, cv in fields
    ]


def _determine_program_change_status(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
) -> str:
    b_t = baseline.traceability
    c_t = current.traceability
    if b_t is None or c_t is None:
        return "UNKNOWN"
    b_pf = b_t.program_fingerprint
    c_pf = c_t.program_fingerprint
    b_cf = b_t.configuration_fingerprint
    c_cf = c_t.configuration_fingerprint
    if b_pf is None or c_pf is None or b_cf is None or c_cf is None:
        return "UNKNOWN"
    prog_changed = b_pf != c_pf
    conf_changed = b_cf != c_cf
    if not prog_changed and not conf_changed:
        return "UNCHANGED"
    if prog_changed and conf_changed:
        return "PROGRAM_AND_CONFIGURATION_CHANGED"
    if prog_changed:
        return "PROGRAM_CHANGED"
    return "CONFIGURATION_CHANGED"


def _determine_version_change_status(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
) -> str:
    reasons = []
    if baseline.parser_version != current.parser_version:
        reasons.append("PARSER_VERSION_CHANGED")
    if baseline.review_schema_version != current.review_schema_version:
        reasons.append("SCHEMA_VERSION_CHANGED")
    if baseline.parser_profile != current.parser_profile:
        reasons.append("PROFILE_CHANGED")
    return "|".join(reasons) if reasons else "NO_VERSION_CHANGE"


def _determine_comparability(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
) -> tuple[ComparabilityStatus, list[str]]:
    notes: list[str] = []
    if baseline.review_schema_version != current.review_schema_version:
        b_major = baseline.review_schema_version.split(".")[0]
        c_major = current.review_schema_version.split(".")[0]
        if b_major != c_major:
            notes.append("REVIEW_SCHEMA_VERSION_MISMATCH")
            return ComparabilityStatus.NOT_COMPARABLE, notes
        notes.append("REVIEW_SCHEMA_MINOR_VERSION_MISMATCH")
    if baseline.parser_profile != current.parser_profile:
        notes.append("PARSER_PROFILE_MISMATCH")
        return ComparabilityStatus.NOT_COMPARABLE, notes
    # Units
    b_units = baseline.units_declared
    c_units = current.units_declared
    if b_units is not None and c_units is not None:
        b_inch = b_units.lower() in ("inch", "in", "g20")
        c_inch = c_units.lower() in ("inch", "in", "g20")
        if b_inch != c_inch:
            notes.append("UNITS_DECLARED_INCOMPATIBLE")
            return ComparabilityStatus.NOT_COMPARABLE, notes
    if baseline.traceability is None or current.traceability is None:
        notes.append("MISSING_TRACEABILITY")
        return ComparabilityStatus.PARTIALLY_COMPARABLE, notes
    if not notes:
        return ComparabilityStatus.COMPARABLE, notes
    return ComparabilityStatus.PARTIALLY_COMPARABLE, notes


def _compute_re_review_required(
    program_change_status: str,
    config_change_status: str,
    version_change_status: str,
    finding_changes: list[NcFindingChange],
    coverage_changes: list[NcCoverageChange],
    comparability: ComparabilityStatus,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    # 1. New blocking finding
    for fc in finding_changes:
        if fc.change_type == FindingChangeType.FINDING_ADDED and fc.current_severity == "BLOCKING":
            reasons.append(f"NEW_BLOCKING_FINDING: {fc.finding_code}")
    # 2. New unsupported feature
    for cc in coverage_changes:
        if cc.change_type == "FEATURE_NEWLY_DETECTED" and cc.current_state == "UNSUPPORTED":
            reasons.append(f"NEW_UNSUPPORTED_FEATURE: {cc.feature}")
    # 3. NC program changed
    if program_change_status in ("PROGRAM_CHANGED", "PROGRAM_AND_CONFIGURATION_CHANGED"):
        reasons.append("NC_PROGRAM_CHANGED")
    # 4. Configuration changed
    if config_change_status in ("CONFIGURATION_CHANGED", "PROGRAM_AND_CONFIGURATION_CHANGED"):
        reasons.append("CONFIGURATION_CHANGED")
    # 5. Version changes
    if "PARSER_VERSION_CHANGED" in version_change_status:
        reasons.append("PARSER_VERSION_CHANGED")
    if "SCHEMA_VERSION_CHANGED" in version_change_status:
        reasons.append("REVIEW_SCHEMA_VERSION_CHANGED")
    # 6. Not comparable
    if comparability == ComparabilityStatus.NOT_COMPARABLE:
        reasons.append("COMPARISON_NOT_COMPARABLE")
    return bool(reasons), reasons


def _compute_change_severity(
    finding_changes: list[NcFindingChange],
    program_change_status: str,
    config_change_status: str,
    block_changes: list[NcBlockChange] | None,
) -> ChangeSeverity:
    # Critical: new blocking finding
    for fc in finding_changes:
        if fc.change_type == FindingChangeType.FINDING_ADDED and fc.current_severity == "BLOCKING":
            return ChangeSeverity.CRITICAL_REVIEW_REQUIRED
    # Major: new unsupported feature, machine/tool/holder change, NC text changed with warning
    if program_change_status in ("PROGRAM_CHANGED", "PROGRAM_AND_CONFIGURATION_CHANGED"):
        for fc in finding_changes:
            if (fc.change_type == FindingChangeType.FINDING_ADDED and
                    fc.current_severity in ("BLOCKING", "WARNING")):
                return ChangeSeverity.MAJOR_REVIEW_REQUIRED
    if config_change_status in ("CONFIGURATION_CHANGED", "PROGRAM_AND_CONFIGURATION_CHANGED"):
        return ChangeSeverity.MAJOR_REVIEW_REQUIRED
    if program_change_status in ("PROGRAM_CHANGED", "PROGRAM_AND_CONFIGURATION_CHANGED"):
        return ChangeSeverity.MINOR_CHANGE
    # If block changes exist but only comment/format changes
    if block_changes is not None:
        has_semantic = any(
            c.semantic_change_type == SemanticChangeType.SEMANTIC_CHANGE
            for c in block_changes
        )
        _comment_types = (
            SemanticChangeType.FORMAT_ONLY_CHANGE,
            SemanticChangeType.COMMENT_CHANGE,
        )
        has_comment = any(
            c.semantic_change_type in _comment_types
            and c.change_type != NcBlockChangeType.UNCHANGED
            for c in block_changes
        )
        if has_comment and not has_semantic:
            return ChangeSeverity.INFORMATIONAL_CHANGE
    if program_change_status == "UNCHANGED" and config_change_status == "UNCHANGED":
        return ChangeSeverity.NO_CHANGE
    return ChangeSeverity.UNKNOWN


def _compute_overall_status(
    program_change_status: str,
    config_change_status: str,
    comparability: ComparabilityStatus,
    review_required: bool,
) -> OverallChangeStatus:
    if comparability == ComparabilityStatus.NOT_COMPARABLE:
        return OverallChangeStatus.NOT_COMPARABLE
    if review_required:
        return OverallChangeStatus.REVIEW_REQUIRED
    if program_change_status in ("PROGRAM_CHANGED", "PROGRAM_AND_CONFIGURATION_CHANGED",
                                  "CONFIGURATION_CHANGED"):
        return OverallChangeStatus.ENGINEERING_CHANGE_DETECTED
    if comparability == ComparabilityStatus.PARTIALLY_COMPARABLE:
        return OverallChangeStatus.COMPARISON_INCOMPLETE
    if program_change_status == "UNCHANGED":
        return OverallChangeStatus.NO_ENGINEERING_CHANGE
    return OverallChangeStatus.COMPARISON_INCOMPLETE


def _build_summary(
    block_changes: list[NcBlockChange] | None,
    segment_changes: list[NcSegmentChange],
    finding_changes: list[NcFindingChange],
    coverage_changes: list[NcCoverageChange],
    config_changes: list[ConfigFieldChange],
    fs_changes: FeedSpindleChangeSummary | None,
    ct_changes: CycleTimeChangeSummary | None,
) -> NcChangeSummary:
    if block_changes is not None:
        _A = NcBlockChangeType.ADDED
        _R = NcBlockChangeType.REMOVED
        _M = NcBlockChangeType.MODIFIED
        _U = NcBlockChangeType.UNCHANGED
        blocks_added = sum(1 for c in block_changes if c.change_type == _A)
        blocks_removed = sum(1 for c in block_changes if c.change_type == _R)
        blocks_modified = sum(1 for c in block_changes if c.change_type == _M)
        blocks_unchanged = sum(1 for c in block_changes if c.change_type == _U)
    else:
        blocks_added = blocks_removed = blocks_modified = blocks_unchanged = None

    _SA = SegmentChangeType.SEGMENT_ADDED
    _SR = SegmentChangeType.SEGMENT_REMOVED
    seg_added = sum(1 for c in segment_changes if c.change_type == _SA)
    seg_removed = sum(1 for c in segment_changes if c.change_type == _SR)
    seg_modified = sum(1 for c in segment_changes if c.change_type in (
        SegmentChangeType.SEGMENT_MODIFIED, SegmentChangeType.SEGMENT_MATCH_UNCERTAIN
    ))
    new_f = sum(1 for c in finding_changes if c.change_type == FindingChangeType.FINDING_ADDED)
    res_f = sum(1 for c in finding_changes if c.change_type == FindingChangeType.FINDING_RESOLVED)
    unch_f = sum(1 for c in finding_changes if c.change_type == FindingChangeType.FINDING_UNCHANGED)
    chd_f = sum(1 for c in finding_changes if c.change_type not in (
        FindingChangeType.FINDING_ADDED, FindingChangeType.FINDING_RESOLVED,
        FindingChangeType.FINDING_UNCHANGED
    ))
    _FADD = FindingChangeType.FINDING_ADDED
    _FRES = FindingChangeType.FINDING_RESOLVED
    _FUCH = FindingChangeType.FINDING_UNCHANGED
    new_bl = sum(
        1 for c in finding_changes
        if c.change_type == _FADD and c.current_severity == "BLOCKING"
    )
    res_bl = sum(
        1 for c in finding_changes
        if c.change_type == _FRES and c.baseline_severity == "BLOCKING"
    )
    unch_bl = sum(
        1 for c in finding_changes
        if c.change_type == _FUCH and c.baseline_severity == "BLOCKING"
    )
    new_wa = sum(
        1 for c in finding_changes
        if c.change_type == _FADD and c.current_severity == "WARNING"
    )
    res_wa = sum(
        1 for c in finding_changes
        if c.change_type == _FRES and c.baseline_severity == "WARNING"
    )
    new_ad = sum(
        1 for c in finding_changes
        if c.change_type == _FADD and c.current_severity == "ADVISORY"
    )
    res_ad = sum(
        1 for c in finding_changes
        if c.change_type == _FRES and c.baseline_severity == "ADVISORY"
    )
    cov_chg = sum(1 for c in coverage_changes if c.change_type != "FEATURE_UNCHANGED")
    cfg_chg = sum(1 for c in config_changes if c.changed)
    feed_chg = bool(fs_changes and (
        fs_changes.commanded_feed_mm_min_changed or
        fs_changes.commanded_feed_mm_rev_changed or
        fs_changes.feed_mode_changed
    ))
    spin_chg = bool(fs_changes and (
        fs_changes.commanded_spindle_rpm_changed or fs_changes.spindle_state_changed
    ))
    ct_chg: bool | None = None
    if ct_changes is not None:
        ct_chg = ct_changes.delta_sec is not None and ct_changes.delta_sec != 0.0

    return NcChangeSummary(
        blocks_added=blocks_added,
        blocks_removed=blocks_removed,
        blocks_modified=blocks_modified,
        blocks_unchanged=blocks_unchanged,
        segments_added=seg_added,
        segments_removed=seg_removed,
        segments_modified=seg_modified,
        new_findings=new_f,
        resolved_findings=res_f,
        unchanged_findings=unch_f,
        changed_findings=chd_f,
        new_blocking_findings=new_bl,
        resolved_blocking_findings=res_bl,
        unchanged_blocking_findings=unch_bl,
        new_warning_findings=new_wa,
        resolved_warning_findings=res_wa,
        new_advisory_findings=new_ad,
        resolved_advisory_findings=res_ad,
        coverage_changes=cov_chg,
        configuration_changes=cfg_chg,
        feed_changed=feed_chg,
        spindle_changed=spin_chg,
        cycle_time_changed=ct_chg,
    )


# ---------------------------------------------------------------------------
# Central comparison engine
# ---------------------------------------------------------------------------


def compare_engineering_reviews(
    baseline: NCProgramEngineeringReview,
    current: NCProgramEngineeringReview,
    nc_text_baseline: str | None = None,
    nc_text_current: str | None = None,
    change_review_id: str | None = None,
) -> NCProgramChangeReview:
    """Deterministic comparison of two NCProgramEngineeringReview snapshots.

    NC_PROGRAM_CHANGE_MANAGEMENT_01
    CENTRAL_CHANGE_COMPARISON_ENGINE_IMPLEMENTED=YES
    ARBITRARY_CHANGE_SCORE_IMPLEMENTED=NO
    PROGRAMMED_MOTION_DELTA_EQUALS_EXECUTED_MOTION_DELTA=NO
    COMMANDED_FEED_DELTA_EQUALS_ACTUAL_FEED_DELTA=NO
    COMMANDED_RPM_DELTA_EQUALS_ACTUAL_RPM_DELTA=NO
    T_WORD_CHANGE_EQUALS_CONFIRMED_TOOL_CHANGE=NO
    PARTIAL_CYCLE_TIME_DELTA_EXPORTED_AS_TOTAL_DELTA=NO
    FALSE_CHANGE_APPROVAL_CLAIM=NO
    FALSE_SAFE_CHANGE_CLAIM=NO
    NC_CHANGE_REVIEW_IS_NOT_APPROVAL=YES

    Args:
        baseline: The prior NCProgramEngineeringReview.
        current: The newly computed NCProgramEngineeringReview.
        nc_text_baseline: Optional raw NC text for baseline (enables block diff).
        nc_text_current: Optional raw NC text for current (enables block diff).
        change_review_id: Optional caller-supplied UUID v4; generated if absent.
    """
    if change_review_id is None:
        change_review_id = str(uuid.uuid4())

    b_t = baseline.traceability
    c_t = current.traceability
    b_af = b_t.analysis_fingerprint if b_t else None
    c_af = c_t.analysis_fingerprint if c_t else None
    b_pf = b_t.program_fingerprint if b_t else None
    c_pf = c_t.program_fingerprint if c_t else None
    b_cf = b_t.configuration_fingerprint if b_t else None
    c_cf = c_t.configuration_fingerprint if c_t else None
    b_rid = b_t.review_id if b_t else None
    c_rid = c_t.review_id if c_t else None

    comparison_fingerprint = _compute_comparison_fingerprint(
        b_af, c_af, CHANGE_REVIEW_SCHEMA_VERSION
    )

    # Comparability
    comparability, compat_notes = _determine_comparability(baseline, current)

    # High-level change statuses
    program_change_status = _determine_program_change_status(baseline, current)
    config_change_status = program_change_status  # same fingerprint set encodes config
    # Correct: configuration change status is separate — use config_fingerprint delta
    # Re-derive: config_change_status from fingerprints directly
    if b_t and c_t and b_cf and c_cf:
        if b_cf != c_cf and b_pf == c_pf:
            config_change_status = "CONFIGURATION_CHANGED"
        elif b_cf == c_cf:
            config_change_status = "UNCHANGED"
        else:
            config_change_status = program_change_status
    else:
        config_change_status = "UNKNOWN"

    version_change_status = _determine_version_change_status(baseline, current)

    # Block diff
    block_changes: list[NcBlockChange] | None = None
    if nc_text_baseline is not None and nc_text_current is not None:
        b_lines = _normalize_nc_lines(nc_text_baseline)
        c_lines = _normalize_nc_lines(nc_text_current)
        block_changes = _diff_nc_blocks(b_lines, c_lines, b_rid, c_rid, b_af, c_af)

    # Detailed diffs
    segment_changes = _diff_segments(baseline, current, b_rid, c_rid, b_af, c_af)
    finding_changes = _diff_findings(baseline, current, b_rid, c_rid, b_af, c_af)
    coverage_changes_list = _diff_coverage(baseline, current, b_rid, c_rid, b_af, c_af)
    config_changes = _diff_config(baseline, current, b_t, c_t)
    fs_changes = _diff_feed_spindle(baseline, current)
    ct_changes = _diff_cycle_time(baseline, current)

    # Re-review logic
    review_required, rr_reasons = _compute_re_review_required(
        program_change_status=program_change_status,
        config_change_status=config_change_status,
        version_change_status=version_change_status,
        finding_changes=finding_changes,
        coverage_changes=coverage_changes_list,
        comparability=comparability,
    )

    # Severity and overall status
    change_severity = _compute_change_severity(
        finding_changes=finding_changes,
        program_change_status=program_change_status,
        config_change_status=config_change_status,
        block_changes=block_changes,
    )
    overall_status = _compute_overall_status(
        program_change_status=program_change_status,
        config_change_status=config_change_status,
        comparability=comparability,
        review_required=review_required,
    )

    # Summary
    change_summary = _build_summary(
        block_changes=block_changes,
        segment_changes=segment_changes,
        finding_changes=finding_changes,
        coverage_changes=coverage_changes_list,
        config_changes=config_changes,
        fs_changes=fs_changes,
        ct_changes=ct_changes,
    )

    limitations: list[str] = list(baseline.limitations) + [
        lim for lim in current.limitations if lim not in baseline.limitations
    ]

    return NCProgramChangeReview(
        change_review_id=change_review_id,
        comparison_schema_version=CHANGE_REVIEW_SCHEMA_VERSION,
        comparison_fingerprint=comparison_fingerprint,
        baseline_review_id=b_rid,
        current_review_id=c_rid,
        baseline_analysis_fingerprint=b_af,
        current_analysis_fingerprint=c_af,
        baseline_program_fingerprint=b_pf,
        current_program_fingerprint=c_pf,
        baseline_configuration_fingerprint=b_cf,
        current_configuration_fingerprint=c_cf,
        baseline_review_schema_version=baseline.review_schema_version,
        current_review_schema_version=current.review_schema_version,
        baseline_parser_version=baseline.parser_version,
        current_parser_version=current.parser_version,
        baseline_parser_profile=baseline.parser_profile,
        current_parser_profile=current.parser_profile,
        baseline_generated_at=b_t.generated_at if b_t else None,
        current_generated_at=c_t.generated_at if c_t else None,
        program_change_status=program_change_status,
        configuration_change_status=config_change_status,
        version_change_status=version_change_status,
        configuration_changes=config_changes,
        block_changes=block_changes,
        segment_changes=segment_changes,
        finding_changes=finding_changes,
        coverage_changes=coverage_changes_list,
        feed_spindle_changes=fs_changes,
        cycle_time_changes=ct_changes,
        change_summary=change_summary,
        comparability_status=comparability,
        comparability_notes=compat_notes,
        change_severity=change_severity,
        overall_change_status=overall_status,
        review_required=review_required,
        review_required_reasons=rr_reasons,
        limitations=limitations,
        programmed_motion_delta_equals_executed_motion_delta=False,
        commanded_feed_delta_equals_actual_feed_delta=False,
        commanded_rpm_delta_equals_actual_rpm_delta=False,
        t_word_change_equals_confirmed_tool_change=False,
        partial_cycle_time_delta_exported_as_total_delta=False,
        false_change_approval_claim=False,
        false_safe_change_claim=False,
        false_controller_certification_claim=False,
        false_collision_free_change_claim=False,
        nc_change_review_is_not_approval=True,
        nc_change_review_is_not_safety_certification=True,
    )
