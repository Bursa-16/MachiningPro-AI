"""NC path evidence analysis API.

POST /api/nc-path/analyze  — parse NC text, return PathEvidence records
                             and optional feed/spindle validation summary.

Safety constants:
    NC_FILE_EXECUTED=NO
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    ARC_AS_CHORD_APPROXIMATION=NO
    PRIVATE_PATH_IN_API_RESPONSE=NO    (source_name is user-supplied label, not a path)
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO
    FALSE_CUTTING_PATH_CLAIM=NO
    NC_FEED_AUTOMATICALLY_PROMOTED_TO_CUTTING_PATH=NO
    NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO
    NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO
    REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
    NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO
    MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=NO
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.cutting_parameters import _get_registry
from backend.compatibility.engine import (
    _HOLDERS,  # tool holders
    _MACHINES,
    _TOOLS,
)
from backend.interoperability.nc_motion import NcMotionResult, parse_nc_motion
from backend.process_planning.engineering_review import (
    NCProgramEngineeringReview,
    build_engineering_review,
)
from backend.process_planning.nc_validation import (
    NCProgramValidationSummary,
    validate_nc_feed_spindle,
)
from backend.process_planning.path_evidence import (
    PathEvidence,
    feed_evidence_from_nc,
    rapid_evidence_from_nc,
)

router = APIRouter(prefix="/api/nc-path", tags=["nc-path"])

_MAX_NC_TEXT_CHARS = 4_000_000  # ~4 MB of text


class NcAnalyzeRequest(BaseModel):
    """Request body for NC motion analysis."""

    nc_text: str = Field(..., description="NC program text (not executed — data only).")

    # PRIVATE_PATH_IN_API_RESPONSE=NO — source_name is a display label only.
    source_name: str | None = Field(
        None,
        max_length=256,
        description="Safe display name for the source (filename only, no path).",
    )

    # Optional initial position. Supply (0, 0, 0) to declare origin start.
    initial_x: float | None = None
    initial_y: float | None = None
    initial_z: float | None = None

    # Optional context for feed/spindle validation (NC_FEED_SPINDLE_PROGRAM_VALIDATION_01)
    # NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO — caller must supply operation explicitly.
    machine_id: str | None = Field(
        None, description="Catalog machine ID for RPM limit check."
    )
    cutting_tool_id: str | None = Field(
        None, description="Catalog cutting tool ID for RPM limit and Vc/fz derivation."
    )
    tool_holder_id: str | None = Field(
        None, description="Catalog tool holder ID for RPM limit check."
    )
    operation: str | None = Field(
        None,
        description=(
            "Explicit operation type (e.g. MILLING, DRILLING). "
            "NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO — never inferred from NC."
        ),
    )
    material_iso_group: str | None = Field(
        None, description="ISO material group (P, M, K, N, S, H) for reference range lookup."
    )


class NcAnalyzeResponse(BaseModel):
    """NC motion analysis result with PathEvidence records and validation summary."""

    feed_evidence: PathEvidence
    rapid_evidence: PathEvidence
    motion_result: NcMotionResult

    # Feed/spindle validation summary (NC_FEED_SPINDLE_PROGRAM_VALIDATION_01)
    # PATH_EVIDENCE_SHOULD_CARRY_VALIDATION_RESULTS=NO — separate model.
    validation_summary: NCProgramValidationSummary

    # Engineering review (NC_PROGRAM_ENGINEERING_REVIEW_01)
    # ENGINEERING_REVIEW_MODEL_IMPLEMENTED=YES
    # VALIDATION_SUMMARY_REMAINS_SEPARATE=YES
    # API_BACKWARD_COMPATIBILITY_PRESERVED=YES — optional field addition
    engineering_review: NCProgramEngineeringReview | None = None

    # Immutable safety flags — always constant; present for explicit audit
    nc_feed_move_equals_confirmed_cutting: bool = False
    arc_chord_approximation_used: bool = False
    nc_file_executed: bool = False
    nc_feed_automatically_promoted_to_cutting_path: bool = False
    nc_commanded_spindle_speed_equals_actual_rpm: bool = False
    nc_commanded_feed_equals_actual_feed: bool = False


@router.post("/analyze", response_model=NcAnalyzeResponse)
def analyze_nc_path(req: NcAnalyzeRequest) -> NcAnalyzeResponse:
    """
    Parse NC program text and extract deterministic motion distances
    and optional feed/spindle validation.

    Returns:
    - feed_evidence: sum of G1 (feed) linear motion (semantic_type=FEED_MOTION)
    - rapid_evidence: sum of G0 (rapid) linear motion (semantic_type=RAPID_MOTION)
    - validation_summary: feed mode, spindle state, RPM limit checks, Vc/fz/feed-rev

    Constraints:
        NC_FILE_EXECUTED=NO — text is parsed as data only; never executed.
        NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
        ARC_AS_CHORD_APPROXIMATION=NO
        NC_FEED_AUTOMATICALLY_PROMOTED_TO_CUTTING_PATH=NO
        NC_COMMANDED_SPINDLE_SPEED_EQUALS_ACTUAL_RPM=NO
        NC_COMMANDED_FEED_EQUALS_ACTUAL_FEED=NO
        REFERENCE_RANGE_VALIDATION_IS_OPTIMIZATION=NO
        NC_PROGRAM_AUTOMATIC_OPERATION_CLASSIFICATION=NO
        MACHINE_FEED_LIMIT_VALIDATION_IMPLEMENTED=NO
        PRIVATE_PATH_IN_API_RESPONSE=NO
    """
    if not req.nc_text or not req.nc_text.strip():
        raise HTTPException(status_code=422, detail="nc_text must not be empty")

    if len(req.nc_text) > _MAX_NC_TEXT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"nc_text exceeds maximum size ({_MAX_NC_TEXT_CHARS} characters)",
        )

    # PRIVATE_PATH_IN_API_RESPONSE=NO — reject absolute path patterns in source_name
    if req.source_name:
        name = req.source_name
        if (
            name.startswith("/")
            or (len(name) >= 2 and name[1] == ":")
            or "\\" in name
            or "/../" in name
            or name.startswith("../")
        ):
            raise HTTPException(
                status_code=422,
                detail="source_name must be a filename only, not an absolute path.",
            )

    result: NcMotionResult = parse_nc_motion(
        req.nc_text,
        initial_x=req.initial_x,
        initial_y=req.initial_y,
        initial_z=req.initial_z,
    )

    feed_ev = feed_evidence_from_nc(result, source_name_safe=req.source_name)
    rapid_ev = rapid_evidence_from_nc(result, source_name_safe=req.source_name)

    # -----------------------------------------------------------------------
    # Resolve catalog context for validation
    # -----------------------------------------------------------------------
    machine_spindle_max_rpm: int | None = None
    tool_max_rpm: int | None = None
    tool_cutting_diameter_mm: float | None = None
    tool_number_of_flutes: int | None = None
    holder_max_rpm: int | None = None

    if req.machine_id and req.machine_id in _MACHINES:
        machine_spindle_max_rpm = _MACHINES[req.machine_id].spindle_max_rpm

    if req.cutting_tool_id and req.cutting_tool_id in _TOOLS:
        t = _TOOLS[req.cutting_tool_id]
        tool_max_rpm = t.max_rpm
        tool_cutting_diameter_mm = t.cutting_diameter_mm
        tool_number_of_flutes = t.number_of_flutes

    if req.tool_holder_id and req.tool_holder_id in _HOLDERS:
        holder_max_rpm = _HOLDERS[req.tool_holder_id].max_rpm

    registry = _get_registry()

    validation = validate_nc_feed_spindle(
        result,
        machine_spindle_max_rpm=machine_spindle_max_rpm,
        machine_id=req.machine_id,
        tool_max_rpm=tool_max_rpm,
        tool_cutting_diameter_mm=tool_cutting_diameter_mm,
        tool_number_of_flutes=tool_number_of_flutes,
        tool_id=req.cutting_tool_id,
        holder_max_rpm=holder_max_rpm,
        holder_id=req.tool_holder_id,
        operation_type=req.operation,
        material_iso_group=req.material_iso_group,
        cutting_param_registry=registry,
    )

    # -----------------------------------------------------------------------
    # Engineering review synthesis (NC_PROGRAM_ENGINEERING_REVIEW_01)
    # NC_PARSE_RESULT_REUSED=YES, PATH_EVIDENCE_REUSED=YES
    # NC_VALIDATION_SUMMARY_REUSED=YES, FEED_SPINDLE_VALIDATION_DUPLICATED=NO
    # -----------------------------------------------------------------------
    machine_display: str | None = None
    cutting_tool_display: str | None = None
    tool_holder_display: str | None = None
    if req.machine_id and req.machine_id in _MACHINES:
        m = _MACHINES[req.machine_id]
        machine_display = f"{m.manufacturer} {m.model}"
    if req.cutting_tool_id and req.cutting_tool_id in _TOOLS:
        t = _TOOLS[req.cutting_tool_id]
        cutting_tool_display = f"{t.manufacturer} {t.product_name}"
    if req.tool_holder_id and req.tool_holder_id in _HOLDERS:
        h = _HOLDERS[req.tool_holder_id]
        tool_holder_display = f"{h.manufacturer} {h.product_name}"

    engineering_review = build_engineering_review(
        result,
        feed_ev,
        rapid_ev,
        validation,
        source_name_safe=req.source_name,
        machine_id=req.machine_id,
        machine_spindle_max_rpm=machine_spindle_max_rpm,
        machine_display=machine_display,
        cutting_tool_id=req.cutting_tool_id,
        tool_max_rpm=tool_max_rpm,
        cutting_tool_display=cutting_tool_display,
        tool_holder_id=req.tool_holder_id,
        holder_max_rpm=holder_max_rpm,
        tool_holder_display=tool_holder_display,
        operation_association=req.operation,
    )

    return NcAnalyzeResponse(
        feed_evidence=feed_ev,
        rapid_evidence=rapid_ev,
        motion_result=result,
        validation_summary=validation,
        engineering_review=engineering_review,
        nc_feed_move_equals_confirmed_cutting=False,
        arc_chord_approximation_used=False,
        nc_file_executed=False,
        nc_feed_automatically_promoted_to_cutting_path=False,
        nc_commanded_spindle_speed_equals_actual_rpm=False,
        nc_commanded_feed_equals_actual_feed=False,
    )
