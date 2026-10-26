"""Drawing-to-Process Intelligence API (EPIC_04 Phase 2).

POST /api/drawing-to-process/generate

Accepts a DrawingRequirementSet (JSON) and returns a GeneratedProcessPlan.

Security invariants preserved:
  AUTO_GENERATED_PLAN_MARKED_APPROVED=NO
  FABRICATED_DRAWING_REQUIREMENT=NO
  FABRICATED_FEATURE=NO
  UNKNOWN_REQUIREMENT_TREATED_AS_SATISFIED=NO
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.drawing_intelligence.feature_recognition import recognize_features
from backend.drawing_intelligence.inspection_foundation import build_inspection_plan
from backend.drawing_intelligence.material_bridge import MaterialBridge
from backend.drawing_intelligence.plan_generator import generate_plan
from backend.drawing_intelligence.requirements import (
    DatumReference,
    DatumReferenceFrame,
    DimensionalRequirement,
    DrawingRequirementSet,
    ExpandedFeatureControlFrame,
    GdtCharacteristic,
    GdtModifier,
    GeometricRequirement,
    HeatTreatmentRequirement,
    MaterialRequirement,
    RequirementExtractionStatus,
    SurfaceFinishRequirement,
    ThreadRequirement,
)
from backend.drawing_intelligence.route_generator import RouteGenerator
from backend.drawing_intelligence.route_scoring import score_routes

router = APIRouter(prefix="/api/drawing-to-process", tags=["drawing-to-process"])

_DISCLAIMER = (
    "Results are REFERENCE_ONLY — DRAFT status, NOT approved for production. "
    "AUTO_GENERATED_PLAN_MARKED_APPROVED=NO. "
    "Validate through engineering review before manufacturing use."
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DimensionalReqIn(BaseModel):
    req_id: str
    dimension_type: str
    nominal_value: float
    unit: str = "mm"
    tolerance_upper: float | None = None
    tolerance_lower: float | None = None
    tolerance_type: str | None = None
    authority: str = "EXTRACTED"
    source_dimension_id: str | None = None
    notes: str | None = None


class DatumRefIn(BaseModel):
    label: str
    precedence: int
    modifier: str = "NONE"


class DatumFrameIn(BaseModel):
    primary: DatumRefIn
    secondary: DatumRefIn | None = None
    tertiary: DatumRefIn | None = None


class GdtFcfIn(BaseModel):
    characteristic: str
    tolerance_value: float
    tolerance_unit: str = "mm"
    diameter_zone: bool = False
    modifier: str = "NONE"
    datum_frame: DatumFrameIn | None = None
    source_fcf_id: str | None = None


class GeometricReqIn(BaseModel):
    req_id: str
    fcf: GdtFcfIn
    feature_ref: str | None = None
    authority: str = "EXTRACTED"
    source_fcf_id: str | None = None


class SurfaceFinishReqIn(BaseModel):
    req_id: str
    ra_um: float | None = None
    rz_um: float | None = None
    feature_ref: str | None = None
    authority: str = "EXTRACTED"


class ThreadReqIn(BaseModel):
    req_id: str
    designation: str | None = None
    standard: str | None = None
    hand: str = "RH"
    nominal_diameter_mm: float | None = None
    pitch_mm: float | None = None
    thread_class: str | None = None
    note_text: str | None = None


class MaterialReqIn(BaseModel):
    req_id: str
    raw_designation: str
    standard: str | None = None


class HeatTreatReqIn(BaseModel):
    req_id: str
    raw_note: str
    condition_code: str | None = None
    hardness_target_hb: int | None = None
    hardness_target_hrc: int | None = None


class DrawingToProcessRequest(BaseModel):
    source_id: str
    drawing_number: str | None = None
    revision: str | None = None
    extraction_status: str = "PARTIAL"
    dimensional: list[DimensionalReqIn] = Field(default_factory=list)
    geometric: list[GeometricReqIn] = Field(default_factory=list)
    surface_finish: list[SurfaceFinishReqIn] = Field(default_factory=list)
    threads: list[ThreadReqIn] = Field(default_factory=list)
    material: MaterialReqIn | None = None
    heat_treatment: list[HeatTreatReqIn] = Field(default_factory=list)
    part_id: str = "UNKNOWN"


# ---------------------------------------------------------------------------
# Helper converters
# ---------------------------------------------------------------------------

def _to_decimal(v: float | None, field: str) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        raise HTTPException(400, f"Invalid decimal value for {field}: {v}")


def _build_datum_ref(d: DatumRefIn) -> DatumReference:
    try:
        mod = GdtModifier(d.modifier)
    except ValueError:
        mod = GdtModifier.NONE
    return DatumReference(label=d.label, precedence=d.precedence, modifier=mod)


def _build_datum_frame(df: DatumFrameIn) -> DatumReferenceFrame:
    return DatumReferenceFrame(
        primary=_build_datum_ref(df.primary),
        secondary=_build_datum_ref(df.secondary) if df.secondary else None,
        tertiary=_build_datum_ref(df.tertiary) if df.tertiary else None,
    )


def _build_fcf(f: GdtFcfIn) -> ExpandedFeatureControlFrame:
    try:
        char = GdtCharacteristic(f.characteristic.upper())
    except ValueError:
        char = GdtCharacteristic.UNKNOWN
    try:
        mod = GdtModifier(f.modifier)
    except ValueError:
        mod = GdtModifier.NONE
    tol = _to_decimal(f.tolerance_value, "fcf.tolerance_value")
    if tol is None or tol <= Decimal(0):
        raise HTTPException(400, "fcf.tolerance_value must be > 0")
    return ExpandedFeatureControlFrame(
        characteristic=char,
        tolerance_value=tol,
        tolerance_unit=f.tolerance_unit,
        diameter_zone=f.diameter_zone,
        modifier=mod,
        datum_frame=_build_datum_frame(f.datum_frame) if f.datum_frame else None,
        source_fcf_id=f.source_fcf_id,
    )


def _build_req_set(req: DrawingToProcessRequest) -> DrawingRequirementSet:
    # Extraction status
    try:
        status = RequirementExtractionStatus(req.extraction_status.upper())
    except ValueError:
        status = RequirementExtractionStatus.PARTIAL

    # Dimensional
    dim_reqs: list[DimensionalRequirement] = []
    for d in req.dimensional:
        nom = _to_decimal(d.nominal_value, f"dimensional[{d.req_id}].nominal_value")
        if nom is None:
            continue
        dim_reqs.append(DimensionalRequirement(
            req_id=d.req_id,
            dimension_type=d.dimension_type,
            nominal_value=nom,
            unit=d.unit,
            tolerance_upper=_to_decimal(d.tolerance_upper, "tolerance_upper"),
            tolerance_lower=_to_decimal(d.tolerance_lower, "tolerance_lower"),
            tolerance_type=d.tolerance_type,
            authority=d.authority,
            source_dimension_id=d.source_dimension_id,
            notes=d.notes,
        ))

    # Geometric
    geom_reqs: list[GeometricRequirement] = []
    for g in req.geometric:
        try:
            fcf = _build_fcf(g.fcf)
        except HTTPException:
            continue
        geom_reqs.append(GeometricRequirement(
            req_id=g.req_id,
            fcf=fcf,
            feature_ref=g.feature_ref,
            authority=g.authority,
            source_fcf_id=g.source_fcf_id,
        ))

    # Surface finish
    sf_reqs: list[SurfaceFinishRequirement] = []
    for s in req.surface_finish:
        ra = _to_decimal(s.ra_um, f"surface_finish[{s.req_id}].ra_um")
        rz = _to_decimal(s.rz_um, f"surface_finish[{s.req_id}].rz_um")
        if ra is None and rz is None:
            continue
        sf_reqs.append(SurfaceFinishRequirement(
            req_id=s.req_id,
            ra_um=ra,
            rz_um=rz,
            feature_ref=s.feature_ref,
            authority=s.authority,
        ))

    # Threads
    thread_reqs: list[ThreadRequirement] = []
    for t in req.threads:
        thread_reqs.append(ThreadRequirement(
            req_id=t.req_id,
            designation=t.designation,
            standard=t.standard,
            hand=t.hand if t.hand in ("RH", "LH") else "RH",
            nominal_diameter_mm=_to_decimal(t.nominal_diameter_mm, "nominal_diameter_mm"),
            pitch_mm=_to_decimal(t.pitch_mm, "pitch_mm"),
            thread_class=t.thread_class,
            note_text=t.note_text,
        ))

    # Material
    material: MaterialRequirement | None = None
    if req.material is not None:
        mat = req.material
        material = MaterialRequirement(
            req_id=mat.req_id,
            raw_designation=mat.raw_designation,
            standard=mat.standard,
            match_confidence="NONE",
        )

    # Heat treatment
    ht_reqs: list[HeatTreatmentRequirement] = []
    for ht in req.heat_treatment:
        ht_reqs.append(HeatTreatmentRequirement(
            req_id=ht.req_id,
            raw_note=ht.raw_note,
            condition_code=ht.condition_code,
            hardness_target_hb=ht.hardness_target_hb,
            hardness_target_hrc=ht.hardness_target_hrc,
        ))

    return DrawingRequirementSet(
        source_id=req.source_id,
        drawing_number=req.drawing_number,
        revision=req.revision,
        extraction_status=status,
        dimensional=tuple(dim_reqs),
        geometric=tuple(geom_reqs),
        surface_finish=tuple(sf_reqs),
        threads=tuple(thread_reqs),
        material=material,
        heat_treatment=tuple(ht_reqs),
    )


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_plan(plan, material_result=None) -> dict:
    steps = [
        {
            "step_id": s.step_id,
            "sequence_number": s.sequence_number,
            "operation": s.operation.value,
            "feature_id": s.feature_id,
            "route_id": s.route_id,
            "is_inspection": s.is_inspection,
            "notes": s.notes,
        }
        for s in plan.steps
    ]
    best_routes = [
        {
            "route_id": sr.route.route_id,
            "feature_id": sr.route.feature_id,
            "feature_type": sr.route.feature_type.value,
            "operations": [op.value for op in sr.route.operations],
            "required_ra_um": str(sr.route.required_ra_um) if sr.route.required_ra_um else None,
            "achievable_ra_um": str(sr.route.achievable_ra_um),
            "requires_grinding": sr.route.requires_grinding,
            "route_description": sr.route.route_description,
            "score": {
                "total": sr.score.total,
                "completeness": sr.score.completeness,
                "efficiency": sr.score.efficiency,
                "seq_compliance": sr.score.seq_compliance,
                "dfm_compliance": sr.score.dfm_compliance,
                "availability": sr.score.availability,
            },
        }
        for sr in plan.best_routes
    ]
    route_results = [
        {
            "feature_id": rr.feature_id,
            "feature_type": rr.feature_type.value,
            "route_count": len(rr.routes),
            "rejection_count": len(rr.rejections),
            "rejections": [
                {
                    "route_id": rej.route_id,
                    "reason": rej.reason.value,
                    "detail": rej.detail,
                }
                for rej in rr.rejections
            ],
        }
        for rr in plan.route_results
    ]
    traceability = [
        {
            "req_id": e.req_id,
            "feature_id": e.feature_id,
            "step_id": e.step_id,
            "recognition_rule": e.recognition_rule,
            "operation": e.operation,
        }
        for e in plan.traceability.entries
    ]

    result: dict = {
        "plan_id": plan.plan_id,
        "source_id": plan.source_id,
        "drawing_number": plan.drawing_number,
        "revision": plan.revision,
        "status": plan.status.value,
        "step_count": plan.step_count,
        "steps": steps,
        "best_routes": best_routes,
        "route_results": route_results,
        "traceability": traceability,
        "generation_warnings": list(plan.generation_warnings),
        "disclaimer": plan.disclaimer,
    }
    if material_result is not None:
        result["material_resolution"] = {
            "raw_designation": material_result.raw_designation,
            "matched_material_id": material_result.matched_material_id,
            "matched_designation": material_result.matched_designation,
            "iso_group": material_result.iso_group,
            "confidence": material_result.confidence,
        }
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate")
def generate_drawing_to_process(req: DrawingToProcessRequest) -> dict:
    """Generate a draft process plan from drawing requirements.

    AUTO_GENERATED_PLAN_MARKED_APPROVED=NO — status is always DRAFT.
    """
    try:
        req_set = _build_req_set(req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    # Material resolution
    material_result = None
    if req_set.material is not None:
        bridge = MaterialBridge()
        material_result = bridge.resolve(req_set.material.raw_designation)

    # Feature recognition
    recognition = recognize_features(req_set, part_id=req.part_id)

    # Inspection plan
    inspection_plan = build_inspection_plan(req_set)

    # Generate plan
    plan = generate_plan(req_set, recognition, inspection_plan, part_id=req.part_id)

    return _serialize_plan(plan, material_result)


@router.get("/schema")
def get_schema() -> dict:
    """Return the schema for the drawing-to-process generate endpoint."""
    return {
        "endpoint": "POST /api/drawing-to-process/generate",
        "disclaimer": _DISCLAIMER,
        "supported_gdt_characteristics": [c.value for c in GdtCharacteristic],
        "supported_gdt_modifiers": [m.value for m in GdtModifier],
        "extraction_status_values": [s.value for s in RequirementExtractionStatus],
        "plan_status_values": ["DRAFT", "PARTIAL", "INSUFFICIENT_DATA"],
        "security_invariants": {
            "AUTO_GENERATED_PLAN_MARKED_APPROVED": "NO",
            "FABRICATED_DRAWING_REQUIREMENT": "NO",
            "FABRICATED_FEATURE": "NO",
            "LLM_REQUIRED_FOR_ROUTE_GENERATION": "NO",
            "UNKNOWN_REQUIREMENT_TREATED_AS_SATISFIED": "NO",
        },
    }
