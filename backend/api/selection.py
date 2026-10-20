"""
Deterministic Configuration-Selection API (COMPATIBILITY_SELECTION_ENGINE_01).

GET  /api/selection/schema     — operations, ISO groups, machine/tool lists
POST /api/selection/evaluate   — run deterministic selection across all
                                 eligible machine/holder/tool combinations

Constraints:
  FALSE_AI_CLAIM=NO
  FALSE_OPTIMIZATION_CLAIM=NO
  FALSE_RECOMMENDATION_CLAIM=NO
  FALSE_PRODUCTION_VALIDATION_CLAIM=NO
  TOOLLIFE_USED_FOR_SELECTION=NO
  ARBITRARY_SELECTION_SCORE=NO
  FORCED_WINNER_WHEN_TIED=NO
  COMPATIBILITY_LOGIC_DUPLICATED=NO
  PRIVATE_PATH_IN_API_RESPONSE=NO
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.compatibility.engine import (
    _MACHINES,
    _TOOLS,
    get_schema_machines,
    get_schema_tools,
)
from backend.compatibility.models import VALID_ISO_GROUPS, VALID_OPERATIONS
from backend.selection.engine import select
from backend.selection.models import SelectionRequest, SelectionResponse

router = APIRouter(prefix="/api/selection", tags=["selection"])


@router.get("/schema")
def selection_schema() -> dict:
    """Return machines, cutting tools, operations, and ISO groups for UI selectors.

    Tool holders are not exposed as user-selectable constraints — the engine
    evaluates all holders automatically.
    """
    return {
        "machines": [e.model_dump() for e in get_schema_machines()],
        "cutting_tools": [e.model_dump() for e in get_schema_tools()],
        "valid_operations": sorted(VALID_OPERATIONS),
        "valid_iso_groups": sorted(VALID_ISO_GROUPS),
    }


@router.post("/evaluate", response_model=SelectionResponse)
def evaluate_selection(req: SelectionRequest) -> SelectionResponse:
    """
    Evaluate all eligible machine/holder/tool combinations for the given
    operation and ISO material group, then rank COMPATIBLE ones deterministically.

    Optional machine_id and cutting_tool_id constraints restrict the candidate pool.
    Optional cutting_speed_m_min + tool_diameter_mm enable RPM margin criterion.

    Overall states returned:
      SELECTION_AVAILABLE                    — ranked candidates with differentiation
      COMPATIBLE_BUT_NO_DIFFERENTIATING_EVIDENCE — ranked but all tied
      NO_COMPATIBLE_CONFIGURATION            — zero COMPATIBLE combinations found
      INSUFFICIENT_DATA_FOR_SELECTION        — all candidates INSUFFICIENT_DATA

    Raises:
        422 — unknown IDs, invalid operation, invalid ISO group, bad numeric values.
    """
    # --- Validate operation ---
    if req.operation.lower() not in VALID_OPERATIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid operation: {req.operation!r}. "
                f"Valid: {sorted(VALID_OPERATIONS)}"
            ),
        )

    # --- Validate ISO group ---
    if req.iso_material_group.upper() not in VALID_ISO_GROUPS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid iso_material_group: {req.iso_material_group!r}. "
                f"Valid: {sorted(VALID_ISO_GROUPS)}"
            ),
        )

    # --- Validate optional machine filter ---
    if req.machine_id is not None and req.machine_id not in _MACHINES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown machine_id: {req.machine_id!r}",
        )

    # --- Validate optional tool filter ---
    if req.cutting_tool_id is not None and req.cutting_tool_id not in _TOOLS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown cutting_tool_id: {req.cutting_tool_id!r}",
        )

    # --- Validate optional numeric inputs ---
    if req.cutting_speed_m_min is not None and req.cutting_speed_m_min < 0:
        raise HTTPException(
            status_code=422,
            detail=f"cutting_speed_m_min must be >= 0, got {req.cutting_speed_m_min}",
        )
    if req.tool_diameter_mm is not None and req.tool_diameter_mm <= 0:
        raise HTTPException(
            status_code=422,
            detail=f"tool_diameter_mm must be > 0, got {req.tool_diameter_mm}",
        )

    # --- Validate max_eligible_returned ---
    if req.max_eligible_returned < 1:
        raise HTTPException(
            status_code=422,
            detail=f"max_eligible_returned must be >= 1, got {req.max_eligible_returned}",
        )

    # Normalise casing
    normalised = SelectionRequest(
        operation=req.operation.lower(),
        iso_material_group=req.iso_material_group.upper(),
        machine_id=req.machine_id,
        cutting_tool_id=req.cutting_tool_id,
        cutting_speed_m_min=req.cutting_speed_m_min,
        tool_diameter_mm=req.tool_diameter_mm,
        max_eligible_returned=req.max_eligible_returned,
    )

    return select(normalised)
