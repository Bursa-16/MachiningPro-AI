"""
Deterministic Compatibility Evaluation API (MACHINE_TOOL_HOLDER_COMPATIBILITY_ENGINE_01).

GET  /api/compatibility/schema        — machines, holders, tools for UI selectors
GET  /api/compatibility/reason-codes  — stable reason-code catalogue
POST /api/compatibility/evaluate      — three-state deterministic evaluation

Constraints:
  FALSE_COMPATIBILITY_CLAIM=NO
  FALSE_AI_CLAIM=NO
  MISSING_LIMIT_AS_ZERO=NO
  PORT_8010_USED=NO
  PRIVATE_PATH_IN_API_RESPONSE=NO
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.compatibility.engine import (
    evaluate,
    get_schema_holders,
    get_schema_machines,
    get_schema_tools,
)
from backend.compatibility.models import (
    RC,
    VALID_ISO_GROUPS,
    VALID_OPERATIONS,
    CompatibilityRequest,
    CompatibilityResponse,
    CompatibilitySchema,
)

router = APIRouter(prefix="/api/compatibility", tags=["compatibility"])

_DISCLAIMER = (
    "Results are REFERENCE_ONLY. No production validation has been performed. "
    "Validate all combinations through production trials before manufacturing use."
)


@router.get("/schema", response_model=CompatibilitySchema)
def compatibility_schema() -> CompatibilitySchema:
    """Return all catalog entries and valid option sets for the UI selectors."""
    return CompatibilitySchema(
        machines=get_schema_machines(),
        holders=get_schema_holders(),
        cutting_tools=get_schema_tools(),
        valid_operations=sorted(VALID_OPERATIONS),
        valid_iso_groups=sorted(VALID_ISO_GROUPS),
    )


@router.get("/reason-codes")
def reason_codes() -> dict:
    """Return all stable reason-code constants used in rule results."""
    return {
        k: v
        for k, v in vars(RC).items()
        if not k.startswith("_") and isinstance(v, str)
    }


@router.post("/evaluate", response_model=CompatibilityResponse)
def evaluate_compatibility(req: CompatibilityRequest) -> CompatibilityResponse:
    """Evaluate machine → holder → tool → operation → ISO material compatibility.

    Returns exactly one of: COMPATIBLE / INCOMPATIBLE / INSUFFICIENT_DATA.

    Raises:
        422 — unknown IDs, invalid operation, invalid ISO group, negative Vc,
              non-positive diameter.
    """
    from backend.compatibility.engine import _MACHINES, _HOLDERS, _TOOLS

    # Validate IDs
    if req.machine_id not in _MACHINES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown machine_id: {req.machine_id!r}",
        )
    if req.holder_id not in _HOLDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown holder_id: {req.holder_id!r}",
        )
    if req.cutting_tool_id not in _TOOLS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown cutting_tool_id: {req.cutting_tool_id!r}",
        )

    # Validate operation
    if req.operation.lower() not in VALID_OPERATIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid operation: {req.operation!r}. "
                f"Valid operations: {sorted(VALID_OPERATIONS)}"
            ),
        )
    req = CompatibilityRequest(
        machine_id=req.machine_id,
        holder_id=req.holder_id,
        cutting_tool_id=req.cutting_tool_id,
        operation=req.operation.lower(),
        iso_material_group=req.iso_material_group.upper(),
        cutting_speed_m_min=req.cutting_speed_m_min,
        tool_diameter_mm=req.tool_diameter_mm,
    )

    # Validate ISO group
    if req.iso_material_group not in VALID_ISO_GROUPS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid iso_material_group: {req.iso_material_group!r}. "
                f"Valid groups: {sorted(VALID_ISO_GROUPS)}"
            ),
        )

    # Validate optional numeric inputs
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

    return evaluate(req)
