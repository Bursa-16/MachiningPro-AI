"""Manufacturing plan API — 10 endpoints.

AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.manufacturing_plan.builder import build_manufacturing_plan, build_nc_handoff_packages
from backend.manufacturing_plan.export import (
    export_csv_inspection,
    export_csv_operations,
    export_html,
    export_json,
    export_report_package,
)
from backend.manufacturing_plan.models import ManufacturingPlanStatus
from backend.manufacturing_plan.store import PlanApprovalError, PlanNotFoundError, get_store
from backend.manufacturing_plan.validator import validate_manufacturing_plan

router = APIRouter(prefix="/api/manufacturing-plan", tags=["manufacturing-plan"])


def _cv(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "value"):
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _cv(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_cv(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _cv(v) for k, v in obj.items()}
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return {k: _cv(v) for k, v in vars(obj).items() if not k.startswith("_")}
    try:
        if isinstance(obj, datetime):
            return obj.isoformat()
    except Exception:
        pass
    return obj


def _plan_summary(plan: Any) -> dict:
    return {
        "plan_id": plan.plan_id,
        "source_id": plan.source_id,
        "drawing_number": plan.drawing_number,
        "revision": plan.revision,
        "status": plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        "release_gate": plan.release_gate.value if hasattr(plan.release_gate, "value") else str(plan.release_gate),
        "overall_completeness": plan.completeness.overall_completeness,
        "completeness_status": plan.completeness.completeness_status.value
            if hasattr(plan.completeness.completeness_status, "value")
            else str(plan.completeness.completeness_status),
        "characteristics_count": len(plan.characteristics),
        "operations_count": len(plan.operations),
        "open_items_count": len([i for i in plan.open_items if i.status.value == "OPEN"]),
        "traceability_fingerprint": plan.traceability_fingerprint,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "disclaimer": plan.disclaimer,
        "AUTO_GENERATED_PLAN_MARKED_APPROVED": plan.AUTO_GENERATED_PLAN_MARKED_APPROVED,
        "generation_warnings": plan.generation_warnings,
    }


def _plan_detail(plan: Any) -> dict:
    return _cv(plan)


# ─────────────────────────────── Request models ───────────────────────────────

class CreatePlanRequest(BaseModel):
    source_id: str
    optimized_plan: Any | None = None
    req_set: Any | None = None
    drawing_number: str | None = None
    revision: str | None = None
    calibration_profile_ids: list[str] = []


class ReviewActionRequest(BaseModel):
    engineer_note: str = ""


class ApproveRequest(BaseModel):
    engineer_note: str = ""


class ReviseRequest(BaseModel):
    change_driver: str = "OTHER"
    engineer_note: str = ""


# ─────────────────────────────── Endpoints ───────────────────────────────────

@router.post("/create")
@router.post("/generate")
async def create_plan(body: CreatePlanRequest) -> dict:
    """EP-01: Generate manufacturing plan. Always DRAFT. AUTO_GENERATED_PLAN_MARKED_APPROVED=NO."""
    plan = build_manufacturing_plan(
        source_id=body.source_id,
        optimized_plan=body.optimized_plan,
        req_set=body.req_set,
        drawing_number=body.drawing_number,
        revision=body.revision,
        calibration_profile_ids=body.calibration_profile_ids,
    )
    get_store().save(plan)
    return _plan_summary(plan)


@router.get("")
async def list_plans(
    drawing_number: str | None = Query(None),
    source_id: str | None = Query(None),
) -> list[dict]:
    """EP-02: List manufacturing plans."""
    store = get_store()
    if drawing_number:
        plans = store.find_by_drawing(drawing_number)
    elif source_id:
        plans = store.find_by_source(source_id)
    else:
        plans = store.list_all()
    return [_plan_summary(p) for p in plans]


@router.get("/{plan_id}/summary")
async def get_plan_summary(plan_id: str) -> dict:
    """EP-04: Get plan summary."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return _plan_summary(plan)


@router.get("/{plan_id}/setups")
async def get_setups(plan_id: str) -> list[dict]:
    """EP: Get plan setups."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return [_cv(s) for s in plan.setups]


@router.get("/{plan_id}/inspection-plan")
async def get_inspection_plan(plan_id: str) -> dict:
    """EP: Get inspection plan."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    if plan.inspection_plan is None:
        return {"rows": [], "coverage_rate": 0.0, "disclaimer": "No inspection plan"}
    return _cv(plan.inspection_plan)


@router.get("/{plan_id}/control-plan")
async def get_control_plan(plan_id: str) -> dict:
    """EP: Get control plan."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    if plan.control_plan is None:
        return {"rows": [], "disclaimer": "No control plan"}
    return _cv(plan.control_plan)


@router.get("/{plan_id}")
async def get_plan(plan_id: str) -> dict:
    """EP-03: Get full manufacturing plan."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return _plan_detail(plan)


@router.post("/{plan_id}/validate")
async def validate_plan(plan_id: str) -> dict:
    """EP-05: Validate plan — returns open_items, completeness, release_gate."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    result = validate_manufacturing_plan(plan)
    return {
        "plan_id": plan_id,
        "passed": result.passed,
        "findings": [_cv(f) for f in result.findings],
        "open_items": [_cv(f) for f in result.findings],
        "completeness": _cv(plan.completeness),
        "release_gate": plan.release_gate.value if hasattr(plan.release_gate, "value") else str(plan.release_gate),
        "blocking_count": result.blocking_count,
        "review_required_count": result.review_required_count,
        "advisory_count": result.advisory_count,
    }


@router.post("/{plan_id}/review")
async def mark_reviewed(plan_id: str, body: ReviewActionRequest = ReviewActionRequest()) -> dict:
    """EP-06: Mark plan as engineer-reviewed."""
    try:
        plan = get_store().mark_engineer_reviewed(plan_id, body.engineer_note)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    except PlanApprovalError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _plan_summary(plan)


@router.post("/{plan_id}/approve")
async def approve_plan(plan_id: str, body: ApproveRequest = ApproveRequest()) -> dict:
    """EP-07: Approve plan. AUTO_GENERATED_PLAN_MARKED_APPROVED=NO.

    For compatibility, allows approval from any non-terminal status
    (engineer mark is recommended but not enforced by API).
    """
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    if plan.AUTO_GENERATED_PLAN_MARKED_APPROVED:
        raise HTTPException(status_code=422, detail="AUTO_GENERATED_PLAN_MARKED_APPROVED=True — approval not permitted")
    if plan.status == ManufacturingPlanStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Plan must be ENGINEER_REVIEWED before approval — call /review first")
    try:
        approved = get_store().approve(plan_id, body.engineer_note)
    except PlanApprovalError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _plan_summary(approved)


@router.post("/{plan_id}/reject")
async def reject_plan(plan_id: str, body: ReviewActionRequest = ReviewActionRequest()) -> dict:
    """EP-08: Reject plan."""
    try:
        plan = get_store().reject(plan_id, body.engineer_note)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    except PlanApprovalError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _plan_summary(plan)


@router.post("/{plan_id}/revise")
async def revise_plan(plan_id: str, body: ReviseRequest) -> dict:
    """EP: Revise plan — supersedes old, creates new DRAFT."""
    try:
        old_plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    new_plan = build_manufacturing_plan(
        source_id=old_plan.source_id,
        optimized_plan=None,
        req_set=None,
        drawing_number=old_plan.drawing_number,
        revision=old_plan.revision,
        calibration_profile_ids=old_plan.calibration_profile_ids,
    )
    get_store().supersede(plan_id, new_plan)
    return {
        "old_plan_id": plan_id,
        "new_plan_id": new_plan.plan_id,
        "status": new_plan.status.value,
        "change_driver": body.change_driver,
    }


@router.get("/{plan_id}/nc-handoff")
async def get_nc_handoff(plan_id: str) -> dict:
    """EP-09: Get NC handoff packages. NC_FILE_EXECUTED=False always."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    packages = build_nc_handoff_packages(plan)
    return {
        "plan_id": plan_id,
        "NC_FILE_EXECUTED": False,
        "packages": [_cv(p) for p in packages],
    }


@router.get("/{plan_id}/export")
async def export_plan(
    plan_id: str,
    format: str = Query("json"),
) -> dict:
    """EP-10: Export plan in various formats."""
    try:
        plan = get_store().get(plan_id)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")

    valid_formats = {"json", "csv_operations", "csv_inspection", "html", "nc_handoff", "report", "package"}
    if format not in valid_formats:
        raise HTTPException(status_code=400, detail=f"Unknown format '{format}'. Valid: {sorted(valid_formats)}")

    if format == "json":
        return {"plan_id": plan_id, "format": "json", "content": export_json(plan)}
    if format == "csv_operations":
        return {"plan_id": plan_id, "format": "csv_operations", "content": export_csv_operations(plan)}
    if format == "csv_inspection":
        return {"plan_id": plan_id, "format": "csv_inspection", "content": export_csv_inspection(plan)}
    if format == "html":
        return {"plan_id": plan_id, "format": "html", "content": export_html(plan)}
    if format == "nc_handoff":
        packages = build_nc_handoff_packages(plan)
        return {
            "plan_id": plan_id,
            "format": "nc_handoff",
            "NC_FILE_EXECUTED": False,
            "packages": [_cv(p) for p in packages],
        }
    # report / package
    return {"plan_id": plan_id, **export_report_package(plan)}
