"""Typed path evidence model for NC/CAD/user-input path sources.

PROCESS_PLAN_CYCLE_TIME_CAD_CAM_INTEGRATION_01 — Phase 2

A PathEvidence record documents WHAT produced a path distance value,
HOW reliable that distance is, and WHAT semantic claims can be made.

Safety constants enforced here:
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    PRIVATE_PATH_IN_PATH_EVIDENCE=NO  (only filename, no absolute path)
    ARC_AS_CHORD_APPROXIMATION=NO
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from backend.interoperability.nc_motion import NcAnalysisStatus, NcMotionResult

__all__ = [
    "PathSourceType",
    "PathSemanticType",
    "PathValidationStatus",
    "PathEvidence",
    "feed_evidence_from_nc",
    "rapid_evidence_from_nc",
]

# ---------------------------------------------------------------------------
# Enums (plain strings — StrEnum available from 3.11; kept as literals for
# compatibility with current Python floor)
# ---------------------------------------------------------------------------

# "NC_PROGRAM" | "USER_INPUT" | "CAM_TOOLPATH" | "DXF_CONTOUR" | "CAD_FEATURE"
PathSourceType = str
# "FEED_MOTION" | "RAPID_MOTION" | "USER_CONFIRMED_CUTTING" | "DESIGN_GEOMETRY"
PathSemanticType = str
# "COMPUTED_FROM_NC" | "VERIFIED_EXPLICIT" | "INSUFFICIENT_DATA"
PathValidationStatus = str

NC_PROGRAM: PathSourceType = "NC_PROGRAM"
USER_INPUT: PathSourceType = "USER_INPUT"

FEED_MOTION: PathSemanticType = "FEED_MOTION"
RAPID_MOTION: PathSemanticType = "RAPID_MOTION"

COMPUTED_FROM_NC: PathValidationStatus = "COMPUTED_FROM_NC"
VERIFIED_EXPLICIT: PathValidationStatus = "VERIFIED_EXPLICIT"
INSUFFICIENT_DATA_STATUS: PathValidationStatus = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# PathEvidence model
# ---------------------------------------------------------------------------


class PathEvidence(BaseModel):
    """Typed record that documents the provenance and semantics of a path distance."""

    evidence_id: str
    source_type: PathSourceType
    semantic_type: PathSemanticType
    distance_mm: float
    validation_status: PathValidationStatus

    # Source identification — PRIVATE_PATH_IN_PATH_EVIDENCE=NO
    # Only filename (not absolute path); None if from text paste
    source_name_safe: str | None = None
    source_reference_safe: str | None = None

    # Units
    units_original: str | None = None      # "mm" | "inch" as declared in source
    units_canonical: str = "mm"            # always mm after conversion

    # Parser metadata
    parser_profile: str | None = None
    parser_version: str | None = None

    # Analysis quality
    analysis_status: str | None = None     # NcAnalysisStatus value
    supported_motion_count: int = 0
    unsupported_construct_count: int = 0
    unknown_start_count: int = 0
    tool_change_count: int = 0

    # Commanded feed from NC (NOT reference guidance)
    # REFERENCE_FEED_OVERWRITTEN_BY_NC=NO — this field is evidence only
    nc_commanded_feed_mm_min: float | None = None

    # Detailed diagnostics
    unsupported_features: list[str] = []
    limitations: list[str] = []

    # Operation association (explicit user assignment)
    # PATH_TO_OPERATION_MAPPING_METHOD=EXPLICIT_USER_ASSIGNMENT
    operation_association: str | None = None  # step_id when user associates

    # Immutable safety flags — always False; present for explicit audit
    nc_feed_move_equals_confirmed_cutting: bool = False
    arc_chord_approximation_used: bool = False


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def feed_evidence_from_nc(
    result: NcMotionResult,
    source_name_safe: str | None = None,
) -> PathEvidence:
    """Build a FEED_MOTION PathEvidence from an NcMotionResult.

    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — semantic_type is FEED_MOTION,
    not CUTTING_CONFIRMED. Use only when user explicitly confirms engagement.
    """
    validation = (
        COMPUTED_FROM_NC
        if result.analysis_status not in (
            NcAnalysisStatus.INVALID_PROGRAM,
            NcAnalysisStatus.INSUFFICIENT_DATA,
        )
        else INSUFFICIENT_DATA_STATUS
    )

    return PathEvidence(
        evidence_id=str(uuid.uuid4()),
        source_type=NC_PROGRAM,
        semantic_type=FEED_MOTION,
        distance_mm=result.feed_distance_mm,
        validation_status=validation,
        source_name_safe=source_name_safe,
        units_original=result.units_declared,
        units_canonical="mm",
        parser_profile=result.parser_profile,
        parser_version=result.parser_version,
        analysis_status=str(result.analysis_status),
        supported_motion_count=result.supported_motion_count,
        unsupported_construct_count=result.unsupported_construct_count,
        unknown_start_count=result.unknown_start_count,
        tool_change_count=result.tool_change_count,
        nc_commanded_feed_mm_min=result.nc_commanded_feed_mm_min,
        unsupported_features=list(result.unsupported_features),
        limitations=list(result.limitations),
        nc_feed_move_equals_confirmed_cutting=False,
        arc_chord_approximation_used=False,
    )


def rapid_evidence_from_nc(
    result: NcMotionResult,
    source_name_safe: str | None = None,
) -> PathEvidence:
    """Build a RAPID_MOTION PathEvidence from an NcMotionResult."""
    validation = (
        COMPUTED_FROM_NC
        if result.analysis_status not in (
            NcAnalysisStatus.INVALID_PROGRAM,
            NcAnalysisStatus.INSUFFICIENT_DATA,
        )
        else INSUFFICIENT_DATA_STATUS
    )

    return PathEvidence(
        evidence_id=str(uuid.uuid4()),
        source_type=NC_PROGRAM,
        semantic_type=RAPID_MOTION,
        distance_mm=result.rapid_distance_mm,
        validation_status=validation,
        source_name_safe=source_name_safe,
        units_original=result.units_declared,
        units_canonical="mm",
        parser_profile=result.parser_profile,
        parser_version=result.parser_version,
        analysis_status=str(result.analysis_status),
        supported_motion_count=result.supported_motion_count,
        unsupported_construct_count=result.unsupported_construct_count,
        unknown_start_count=result.unknown_start_count,
        tool_change_count=result.tool_change_count,
        unsupported_features=list(result.unsupported_features),
        limitations=list(result.limitations),
        nc_feed_move_equals_confirmed_cutting=False,
        arc_chord_approximation_used=False,
    )
