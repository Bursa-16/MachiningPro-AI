"""Calibration API endpoints — EPIC_04F.

EPIC04F_API_IMPLEMENTED=YES
EPIC04F_API_ENDPOINT_COUNT=7

Endpoints:
  GET  /api/calibration/schema
  POST /api/calibration/tolerance/evaluate
  POST /api/calibration/surface/evaluate
  POST /api/calibration/cycle-time/estimate
  POST /api/calibration/profiles
  GET  /api/calibration/profiles
  GET  /api/calibration/profiles/{profile_id}
  PATCH /api/calibration/profiles/{profile_id}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.calibration.cycle_components import (
    assemble_cycle_time_estimate,
    compute_batch_model,
    make_cutting_component,
    make_dwell_component,
    make_load_unload_component,
    make_probing_component,
    make_rapid_component,
    make_setup_component,
    make_tool_change_component,
)
from backend.calibration.models import CalibrationSource
from backend.calibration.shop_profile import PROFILE_STORE, ShopCalibrationProfile
from backend.calibration.surface_capability import (
    SurfaceOperationFamily,
    surface_capability_margin,
)
from backend.calibration.tolerance_capability import (
    ToleranceOperationFamily,
    can_achieve_tolerance,
)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])

_DISCLAIMER = (
    "All capability values are REFERENCE_ONLY from public engineering handbooks. "
    "FABRICATED_PROCESS_CAPABILITY=NO. FABRICATED_SURFACE_CAPABILITY=NO. "
    "Not a production guarantee. Engineer must validate before manufacturing use."
)


@router.get("/schema")
def get_schema():
    """Return enumeration schemas for the calibration domain."""
    return {
        "tolerance_operations": [op.value for op in ToleranceOperationFamily],
        "surface_operations": [op.value for op in SurfaceOperationFamily],
        "calibration_sources": [s.value for s in CalibrationSource],
        "disclaimer": _DISCLAIMER,
    }


class ToleranceEvalRequest(BaseModel):
    operation: str
    required_tolerance_um: float
    nominal_size_mm: float
    machine_validated: bool = False


@router.post("/tolerance/evaluate")
def evaluate_tolerance(req: ToleranceEvalRequest):
    """Evaluate tolerance capability margin for an operation."""
    result = can_achieve_tolerance(
        req.operation,
        req.required_tolerance_um,
        req.nominal_size_mm,
        req.machine_validated,
    )
    return result.model_dump()


class SurfaceEvalRequest(BaseModel):
    operation: str
    required_ra_um: float
    use_typical: bool = False


@router.post("/surface/evaluate")
def evaluate_surface(req: SurfaceEvalRequest):
    """Evaluate surface finish capability margin."""
    result = surface_capability_margin(
        req.operation,
        req.required_ra_um,
        req.use_typical,
    )
    return result.model_dump()


class CycleTimeEstimateRequest(BaseModel):
    cutting_sec_min: float | None = None
    cutting_sec_max: float | None = None
    rapid_sec: float | None = None
    dwell_sec: float | None = None
    atc_time_sec: float | None = None
    tool_changes: int = 0
    setup_sec: float | None = None
    load_unload_sec: float | None = None
    probing_sec: float | None = None
    machine_id: str | None = None
    batch_quantity: int | None = None


@router.post("/cycle-time/estimate")
def estimate_cycle_time(req: CycleTimeEstimateRequest):
    """Assemble a cycle time estimate from explicit component inputs."""
    components = []
    components.append(make_cutting_component(req.cutting_sec_min, req.cutting_sec_max))

    if req.rapid_sec is not None:
        components.append(make_rapid_component(req.rapid_sec))
    if req.dwell_sec is not None and req.dwell_sec > 0:
        components.append(make_dwell_component(req.dwell_sec))

    components.append(
        make_tool_change_component(req.atc_time_sec, req.tool_changes, req.machine_id)
    )
    components.append(make_setup_component(req.setup_sec))

    if req.load_unload_sec is not None:
        components.append(make_load_unload_component(req.load_unload_sec))
    if req.probing_sec is not None:
        components.append(make_probing_component(req.probing_sec))

    estimate = assemble_cycle_time_estimate(components)
    result = estimate.model_dump()

    if req.batch_quantity and req.batch_quantity > 0:
        batch = compute_batch_model(
            req.batch_quantity,
            req.setup_sec,
            estimate.known_total_sec_min,
            estimate.known_total_sec_max,
        )
        result["batch_model"] = batch.model_dump()

    return result


@router.post("/profiles")
def create_profile(profile: ShopCalibrationProfile):
    """Create a shop calibration profile."""
    created = PROFILE_STORE.create(profile)
    return created.model_dump()


@router.get("/profiles")
def list_profiles(
    site_id: str | None = Query(None),
    machine_id: str | None = Query(None),
    operation_family: str | None = Query(None),
):
    """List shop calibration profiles."""
    profiles = PROFILE_STORE.list(site_id, machine_id, operation_family)
    return [p.model_dump() for p in profiles]


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: str):
    """Get a shop calibration profile by ID."""
    profile = PROFILE_STORE.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found.")
    return profile.model_dump()


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, updates: dict):
    """Update a shop calibration profile."""
    updated = PROFILE_STORE.update(profile_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found.")
    return updated.model_dump()
