"""
Deterministic Process Planning API (PROCESS_PLANNING_ENGINE_01).

GET  /api/process-planning/schema   — operations, ISO groups, machines, tools
POST /api/process-planning/plan     — generate deterministic process plan

Constraints:
  FALSE_AI_CLAIM=NO
  FALSE_OPTIMIZATION_CLAIM=NO
  FALSE_CYCLE_TIME_CLAIM=NO
  FALSE_COST_CLAIM=NO
  FALSE_PRODUCTION_VALIDATION_CLAIM=NO
  COMPATIBILITY_LOGIC_DUPLICATED=NO
  SELECTION_LOGIC_DUPLICATED=NO
  CUTTING_PARAMETERS_LIBRARY_DUPLICATED=NO
  TOOLLIFE_USED_FOR_PROCESS_PLAN_PREDICTION=NO
  PRIVATE_PATH_IN_API_RESPONSE=NO
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.cutting_parameters import _get_registry
from backend.compatibility.engine import (
    _MACHINES,
    _TOOLS,
    get_schema_machines,
    get_schema_tools,
)
from backend.compatibility.models import VALID_ISO_GROUPS, VALID_OPERATIONS
from backend.process_planning.plan_models import (
    ProcessPlanRequest,
    ProcessPlanResponse,
)
from backend.process_planning.planner import generate_plan

router = APIRouter(prefix="/api/process-planning", tags=["process-planning"])


@router.get("/schema")
def process_planning_schema() -> dict:
    """Return machines, cutting tools, operations, and ISO groups for UI selectors."""
    return {
        "machines": [e.model_dump() for e in get_schema_machines()],
        "cutting_tools": [e.model_dump() for e in get_schema_tools()],
        "valid_operations": sorted(VALID_OPERATIONS),
        "valid_iso_groups": sorted(VALID_ISO_GROUPS),
    }


@router.post("/plan", response_model=ProcessPlanResponse)
def plan_process(req: ProcessPlanRequest) -> ProcessPlanResponse:
    """
    Generate a deterministic process plan for the given part and operations.

    For each requested operation, evaluates compatible machine/holder/tool
    configurations via the selection engine and queries reference cutting
    parameter evidence. All planning decisions are deterministic and traceable.

    Plan status states:
      PLAN_COMPLETE         — all required steps are PLANNED
      PLAN_PARTIAL          — some steps PLANNED, some BLOCKED or INSUFFICIENT_DATA
      PLAN_BLOCKED          — no steps planned; hard incompatibility dominates
      PLAN_INSUFFICIENT_DATA — no steps planned; missing catalog data dominates

    Step status states:
      PLANNED           — compatible configuration(s) found
      BLOCKED           — hard incompatibility prevents configuration
      INSUFFICIENT_DATA — missing catalog data prevents determination
      NOT_SUPPORTED     — operation not in current supported set

    Raises:
        422 — empty operations, empty part_name, invalid ISO group, unknown IDs,
              negative numerics, empty step_id.
    """
    # --- Validate part_name ---
    if not req.part_name or not req.part_name.strip():
        raise HTTPException(status_code=422, detail="part_name must not be empty")

    # --- Validate operations list ---
    if not req.operations:
        raise HTTPException(status_code=422, detail="operations must not be empty")

    # --- Validate ISO group ---
    iso_group = req.material_iso_group.upper()
    if iso_group not in VALID_ISO_GROUPS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid material_iso_group: {req.material_iso_group!r}. "
                f"Valid: {sorted(VALID_ISO_GROUPS)}"
            ),
        )

    # --- Validate each step ---
    for step in req.operations:
        if not step.step_id or not step.step_id.strip():
            raise HTTPException(status_code=422, detail="Each step must have a non-empty step_id")

        if step.sequence_number < 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"sequence_number must be >= 0, got {step.sequence_number} "
                    f"in step {step.step_id!r}"
                ),
            )

        if step.machine_id is not None and step.machine_id not in _MACHINES:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown machine_id: {step.machine_id!r} in step {step.step_id!r}",
            )

        if step.cutting_tool_id is not None and step.cutting_tool_id not in _TOOLS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Unknown cutting_tool_id: {step.cutting_tool_id!r} "
                    f"in step {step.step_id!r}"
                ),
            )

        if step.cutting_speed_m_min is not None and step.cutting_speed_m_min < 0:
            raise HTTPException(
                status_code=422,
                detail=f"cutting_speed_m_min must be >= 0 in step {step.step_id!r}",
            )

        if step.tool_diameter_mm is not None and step.tool_diameter_mm <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"tool_diameter_mm must be > 0 in step {step.step_id!r}",
            )

    # --- Duplicate step IDs check (early, before hitting the engine) ---
    step_id_counts: dict[str, int] = {}
    for step in req.operations:
        step_id_counts[step.step_id] = step_id_counts.get(step.step_id, 0) + 1
    duplicates = [sid for sid, cnt in step_id_counts.items() if cnt > 1]
    if duplicates:
        raise HTTPException(
            status_code=422,
            detail=f"Duplicate step_id(s): {duplicates}",
        )

    # --- Normalise casing ---
    from backend.process_planning.plan_models import OperationStepRequest
    from backend.process_planning.plan_models import ProcessPlanRequest as PPR

    normalised = PPR(
        part_name=req.part_name.strip(),
        material_iso_group=iso_group,
        operations=[
            OperationStepRequest(
                step_id=s.step_id.strip(),
                sequence_number=s.sequence_number,
                operation=s.operation.lower(),
                feature_id=s.feature_id,
                machine_id=s.machine_id,
                cutting_tool_id=s.cutting_tool_id,
                cutting_speed_m_min=s.cutting_speed_m_min,
                tool_diameter_mm=s.tool_diameter_mm,
                predecessor_step_ids=s.predecessor_step_ids,
                cutting_path_length_mm=s.cutting_path_length_mm,
                cutting_path_source=s.cutting_path_source,
                rapid_distance_mm=s.rapid_distance_mm,
                dwell_sec=s.dwell_sec,
            )
            for s in req.operations
        ],
    )

    registry = _get_registry()
    return generate_plan(normalised, registry)
