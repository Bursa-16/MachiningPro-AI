"""NC path evidence analysis API.

POST /api/nc-path/analyze  — parse NC text, return PathEvidence records.

Safety constants:
    NC_FILE_EXECUTED=NO
    NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO
    ARC_AS_CHORD_APPROXIMATION=NO
    PRIVATE_PATH_IN_API_RESPONSE=NO    (source_name is user-supplied label, not a path)
    FALSE_CONTROLLER_COMPATIBILITY_CLAIM=NO
    FALSE_CUTTING_PATH_CLAIM=NO
    NC_FEED_AUTOMATICALLY_PROMOTED_TO_CUTTING_PATH=NO
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.interoperability.nc_motion import NcMotionResult, parse_nc_motion
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
    # Caller must NOT pass an absolute filesystem path here.
    source_name: str | None = Field(
        None,
        max_length=256,
        description="Safe display name for the source (filename only, no path).",
    )

    # Optional initial position. Supply (0, 0, 0) to declare origin start.
    # UNKNOWN_INITIAL_POSITION_GUESSED=NO — if not supplied, moves from
    # unknown start positions are skipped rather than guessed.
    initial_x: float | None = None
    initial_y: float | None = None
    initial_z: float | None = None


class NcAnalyzeResponse(BaseModel):
    """NC motion analysis result with PathEvidence records."""

    feed_evidence: PathEvidence
    rapid_evidence: PathEvidence
    motion_result: NcMotionResult

    # Immutable safety flags — always constant; present for explicit audit
    nc_feed_move_equals_confirmed_cutting: bool = False
    arc_chord_approximation_used: bool = False
    nc_file_executed: bool = False
    nc_feed_automatically_promoted_to_cutting_path: bool = False


@router.post("/analyze", response_model=NcAnalyzeResponse)
def analyze_nc_path(req: NcAnalyzeRequest) -> NcAnalyzeResponse:
    """
    Parse NC program text and extract deterministic motion distances.

    Returns two PathEvidence records:
    - feed_evidence: sum of G1 (feed) linear motion (semantic_type=FEED_MOTION)
    - rapid_evidence: sum of G0 (rapid) linear motion (semantic_type=RAPID_MOTION)

    Constraints:
        NC_FILE_EXECUTED=NO — text is parsed as data only; never executed.
        NC_FEED_MOVE_EQUALS_CONFIRMED_CUTTING=NO — G1 distance is NC commanded
            feed path, not confirmed cutting engagement.
        ARC_AS_CHORD_APPROXIMATION=NO — G2/G3 detected and flagged, not measured.
        NC_FEED_AUTOMATICALLY_PROMOTED_TO_CUTTING_PATH=NO — caller must
            explicitly decide whether to use feed_evidence as cutting path input.
        PRIVATE_PATH_IN_API_RESPONSE=NO — source_name is a display label only.
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
            or (len(name) >= 2 and name[1] == ":")  # Windows C:\...
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

    return NcAnalyzeResponse(
        feed_evidence=feed_ev,
        rapid_evidence=rapid_ev,
        motion_result=result,
        nc_feed_move_equals_confirmed_cutting=False,
        arc_chord_approximation_used=False,
        nc_file_executed=False,
        nc_feed_automatically_promoted_to_cutting_path=False,
    )
