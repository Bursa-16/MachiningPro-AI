"""Process Route Optimization API — EPIC_04E Phase 2.

6 endpoints:
  POST /api/process-routes/generate          — generate route alternatives for one feature
  POST /api/process-routes/optimize          — optimize routes for a whole part
  GET  /api/process-routes/{plan_id}         — retrieve a stored plan (in-memory cache)
  GET  /api/process-routes/{plan_id}/alternatives — list alternative sets
  POST /api/process-routes/{plan_id}/select  — select a route for a feature
  POST /api/process-routes/{plan_id}/override — apply an engineer override

FABRICATED_ROUTE=NO
AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
BLACK_BOX_AI_SCORE_USED=NO
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.drawing_intelligence.route_benchmark import compute_benchmark
from backend.drawing_intelligence.route_domain import (
    OptimizedProcessPlan,
    OverrideType,
    RouteAlternativeSet,
    RouteOptimizationConfig,
    RouteOverride,
    RouteStatus,
)
from backend.drawing_intelligence.route_optimizer import (
    FeatureRouteRequest,
    PartRouteRequest,
    RouteOptimizer,
)
from backend.drawing_intelligence.route_strategies import RouteStrategy

router = APIRouter(prefix="/api/process-routes", tags=["process-routes"])

_DISCLAIMER = (
    "Results are REFERENCE_ONLY — DRAFT status, NOT approved for production. "
    "AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO. "
    "Validate through engineering review before manufacturing use."
)

# In-memory plan store (session-scope; replaced by DB in production)
_plan_store: dict[str, OptimizedProcessPlan] = {}
_alt_store: dict[str, list[RouteAlternativeSet]] = {}


# ──────────────────────────────────────────────────────────────────────────────
# Request/response models
# ──────────────────────────────────────────────────────────────────────────────

class FeatureRouteRequestBody(BaseModel):
    feature_id: str
    feature_type: str
    required_ra_um: float | None = None
    required_it_grade: str | None = None
    diameter_mm: float | None = None
    has_tight_position: bool = False
    has_runout: bool = False
    has_profile: bool = False
    has_inspection: bool = False
    iso_material_group: str | None = None
    material_machinability: str | None = None
    spindle_interface: str | None = None
    available_machine_type_codes: list[str] | None = None
    material_incompatible_ops: list[str] | None = None
    inspection_notes: list[str] | None = None
    pattern_count: int = 1
    strategy: str = RouteStrategy.BALANCED


class PartRouteRequestBody(BaseModel):
    source_id: str
    drawing_number: str | None = None
    revision: str | None = None
    features: list[FeatureRouteRequestBody]
    same_setup_pairs: list[list[str]] | None = None
    datum_constraints: dict[str, str] | None = None
    strategy: str = RouteStrategy.BALANCED
    max_routes_per_feature: int = 5
    max_machine_candidates: int = 3
    max_tool_candidates: int = 3
    max_holder_candidates: int = 2
    beam_width: int = 3
    include_pareto: bool = True
    max_setups: int = 6


class SelectRouteBody(BaseModel):
    feature_id: str
    route_id: str
    rationale: str | None = None


class OverrideBody(BaseModel):
    feature_id: str
    override_type: str
    target_id: str
    value: str
    applied_by: str = "engineer"
    note: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Serializers (dataclass → dict)
# ──────────────────────────────────────────────────────────────────────────────

def _candidate_dict(c) -> dict:
    return {
        "route_id": c.route_id,
        "feature_id": c.feature_id,
        "strategy": c.strategy,
        "status": c.status.value,
        "is_feasible": c.is_feasible,
        "feasibility": {
            "status": c.feasibility.status.value,
            "reason": c.feasibility.reason,
            "requirement_coverage": c.feasibility.requirement_coverage,
            "unresolved_items": list(c.feasibility.unresolved_items),
        },
        "op_count": c.op_count,
        "setup_count": c.setup_count,
        "operations": [
            {
                "op_id": op.op_id,
                "sequence_no": op.sequence_no,
                "operation_type": op.operation_type.value,
                "sub_operation": op.sub_operation,
                "setup_id": op.setup_id,
                "feature_id": op.feature_id,
                "tool_type_required": (  # noqa: E501
                    op.tool_type_required.value if op.tool_type_required else None
                ),
                "is_inspection": op.is_inspection,
                "notes": op.notes,
            }
            for op in c.operations
        ],
        "machine_candidates": [
            {
                "machine_id": m.machine_id,
                "manufacturer": m.manufacturer,
                "model": m.model,
                "machine_type_code": m.machine_type_code,
                "spindle_interface": m.spindle_interface,
                "suitability_score": m.suitability_score,
                "notes": m.notes,
                "REFERENCE_ONLY": m.REFERENCE_ONLY,
            }
            for m in c.machine_candidates
        ],
        "tool_candidates": [
            {
                "tool_id": t.tool_id,
                "manufacturer": t.manufacturer,
                "product_name": t.product_name,
                "tool_type_code": t.tool_type_code,
                "suitability_score": t.suitability_score,
                "notes": t.notes,
                "REFERENCE_ONLY": t.REFERENCE_ONLY,
            }
            for t in c.tool_candidates
        ],
        "holder_candidates": [
            {
                "holder_id": h.holder_id,
                "manufacturer": h.manufacturer,
                "product_name": h.product_name,
                "machine_interface_key": h.machine_interface_key,
                "suitability_score": h.suitability_score,
                "notes": h.notes,
                "REFERENCE_ONLY": h.REFERENCE_ONLY,
            }
            for h in c.holder_candidates
        ],
        "parameter_context": (
            {
                "material_iso_group": c.parameter_context.material_iso_group,
                "variants": [
                    {
                        "variant": v.variant,
                        "vc_m_min": v.vc_m_min,
                        "fz_mm": v.fz_mm,
                        "ap_mm": v.ap_mm,
                        "confidence": v.confidence.value,
                        "notes": v.notes,
                    }
                    for v in c.parameter_context.variants
                ],
                "REFERENCE_ONLY": c.parameter_context.REFERENCE_ONLY,
            }
            if c.parameter_context else None
        ),
        "score": {
            "total": c.score.total,
            "technical_feasibility": c.score.technical_feasibility,
            "requirement_coverage": c.score.requirement_coverage,
            "process_capability": c.score.process_capability,
            "gdt_confidence": c.score.gdt_confidence,
            "machine_compatibility": c.score.machine_compatibility,
            "tool_compatibility": c.score.tool_compatibility,
            "setup_efficiency": c.score.setup_efficiency,
            "cycle_time": c.score.cycle_time,
            "data_completeness": c.score.data_completeness,
            "risk_penalty": c.score.risk_penalty,
            "strategy_bonus": c.score.strategy_bonus,
        },
        "risk": {
            "overall_risk": c.risk.overall_risk.value,
            "flag_count": c.risk.flag_count,
            "critical_count": c.risk.critical_count,
            "high_count": c.risk.high_count,
            "flags": [
                {
                    "flag_id": f.flag_id,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "description": f.description,
                    "mitigation_note": f.mitigation_note,
                }
                for f in c.risk.flags
            ],
        },
        "explanation": {
            "why_selected": c.explanation.why_selected,
            "gdt_tolerance_decisions": list(c.explanation.gdt_tolerance_decisions),
            "machine_selection_rationale": c.explanation.machine_selection_rationale,
            "tool_selection_rationale": c.explanation.tool_selection_rationale,
            "rejected_alternatives_summary": list(c.explanation.rejected_alternatives_summary),
            "uncertain_data_items": list(c.explanation.uncertain_data_items),
        },
        "unresolved_items": list(c.unresolved_items),
        "rejection_reasons": [
            {"reason": r.reason.value, "detail": r.detail}
            for r in c.rejection_reasons
        ],
        "traceability_fingerprint": c.traceability_fingerprint,
    }


def _alt_set_dict(a: RouteAlternativeSet) -> dict:
    return {
        "source_id": a.source_id,
        "feature_id": a.feature_id,
        "selected_route_id": a.selected_route_id,
        "selection_rationale": a.selection_rationale,
        "feasible_count": a.feasible_count,
        "candidate_count": len(a.candidates),
        "pareto_count": sum(1 for p in a.pareto_frontier if p.is_pareto_optimal),
        "candidates": [_candidate_dict(c) for c in a.candidates],
        "pareto_frontier": [
            {
                "route_id": p.route_id,
                "score_total": p.score_total,
                "op_count": p.op_count,
                "setup_count": p.setup_count,
                "risk_level": p.risk_level.value,
                "is_pareto_optimal": p.is_pareto_optimal,
                "dominated_by": list(p.dominated_by),
            }
            for p in a.pareto_frontier
        ],
    }


def _plan_dict(plan: OptimizedProcessPlan) -> dict:
    return {
        "plan_id": plan.plan_id,
        "source_id": plan.source_id,
        "drawing_number": plan.drawing_number,
        "revision": plan.revision,
        "status": plan.status.value,
        "strategy": plan.strategy,
        "step_count": len(plan.steps),
        "alternative_set_count": len(plan.alternative_sets),
        "risk": {
            "overall_risk": plan.risk.overall_risk.value,
            "flag_count": plan.risk.flag_count,
        },
        "traceability_fingerprint": plan.traceability_fingerprint,
        "generation_warnings": list(plan.generation_warnings),
        "disclaimer": _DISCLAIMER,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_feature_routes(body: FeatureRouteRequestBody):
    """Generate route alternatives for a single feature.

    FABRICATED_ROUTE=NO
    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
    """
    feat_req = FeatureRouteRequest(
        feature_id=body.feature_id,
        feature_type=body.feature_type,
        required_ra_um=body.required_ra_um,
        required_it_grade=body.required_it_grade,
        diameter_mm=body.diameter_mm,
        has_tight_position=body.has_tight_position,
        has_runout=body.has_runout,
        has_profile=body.has_profile,
        has_inspection=body.has_inspection,
        iso_material_group=body.iso_material_group,
        material_machinability=body.material_machinability,
        spindle_interface=body.spindle_interface,
        available_machine_type_codes=body.available_machine_type_codes,
        material_incompatible_ops=body.material_incompatible_ops,
        inspection_notes=body.inspection_notes,
        pattern_count=body.pattern_count,
    )

    strategy = body.strategy
    try:
        RouteStrategy(strategy)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy '{strategy}'. "
                   f"Valid: {[s for s in RouteStrategy.__members__]}",
        ) from exc

    optimizer = RouteOptimizer()
    alt_set = optimizer.optimize_feature(feat_req, strategy=strategy)

    return {
        "feature_id": body.feature_id,
        "strategy": strategy,
        "alternative_set": _alt_set_dict(alt_set),
        "disclaimer": _DISCLAIMER,
    }


@router.post("/optimize")
async def optimize_part_routes(body: PartRouteRequestBody):
    """Optimize routes across all features in a part.

    FABRICATED_ROUTE=NO
    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO
    BLACK_BOX_AI_SCORE_USED=NO
    """
    strategy = body.strategy
    try:
        RouteStrategy(strategy)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy '{strategy}'.",
        ) from exc

    feat_reqs = [
        FeatureRouteRequest(
            feature_id=f.feature_id,
            feature_type=f.feature_type,
            required_ra_um=f.required_ra_um,
            required_it_grade=f.required_it_grade,
            diameter_mm=f.diameter_mm,
            has_tight_position=f.has_tight_position,
            has_runout=f.has_runout,
            has_profile=f.has_profile,
            has_inspection=f.has_inspection,
            iso_material_group=f.iso_material_group,
            material_machinability=f.material_machinability,
            spindle_interface=f.spindle_interface,
            available_machine_type_codes=f.available_machine_type_codes,
            material_incompatible_ops=f.material_incompatible_ops,
            inspection_notes=f.inspection_notes,
            pattern_count=f.pattern_count,
        )
        for f in body.features
    ]

    config = RouteOptimizationConfig(
        strategy=strategy,
        max_routes_per_feature=body.max_routes_per_feature,
        max_machine_candidates=body.max_machine_candidates,
        max_tool_candidates=body.max_tool_candidates,
        max_holder_candidates=body.max_holder_candidates,
        beam_width=body.beam_width,
        include_pareto=body.include_pareto,
        max_setups=body.max_setups,
    )

    part_req = PartRouteRequest(
        source_id=body.source_id,
        drawing_number=body.drawing_number,
        revision=body.revision,
        features=feat_reqs,
        same_setup_pairs=[tuple(p) for p in (body.same_setup_pairs or [])],  # type: ignore[misc]
        datum_constraints=body.datum_constraints,
        strategy=strategy,
        config=config,
    )

    optimizer = RouteOptimizer()
    result = optimizer.optimize_part(part_req)

    plan = result.optimized_plan
    benchmark = compute_benchmark(plan, result.alternative_sets)

    # Cache
    _plan_store[plan.plan_id] = plan
    _alt_store[plan.plan_id] = result.alternative_sets

    return {
        "plan": _plan_dict(plan),
        "alternative_sets": [_alt_set_dict(a) for a in result.alternative_sets],
        "benchmark": {
            "total_candidates_generated": benchmark.total_candidates_generated,
            "feasible_candidates": benchmark.feasible_candidates,
            "infeasible_candidates": benchmark.infeasible_candidates,
            "valid_route_recall": benchmark.valid_route_recall,
            "setup_count": benchmark.setup_count,
            "requirement_coverage": benchmark.requirement_coverage,
            "determinism_rate": benchmark.determinism_rate,
            "FABRICATED_ROUTE": benchmark.FABRICATED_ROUTE,
            "AUTO_SELECTED_ROUTE_MARKED_APPROVED": benchmark.AUTO_SELECTED_ROUTE_MARKED_APPROVED,
            "BLACK_BOX_AI_SCORE_USED": benchmark.BLACK_BOX_AI_SCORE_USED,
        },
        "disclaimer": _DISCLAIMER,
    }


@router.get("/{plan_id}")
async def get_plan(plan_id: str):
    """Retrieve a stored optimized plan by ID."""
    plan = _plan_store.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")
    return {
        "plan": _plan_dict(plan),
        "steps": [
            {
                "step_id": s.step_id,
                "setup_no": s.setup_no,
                "operation_no": s.operation_no,
                "feature_id": s.feature_id,
                "operation_type": s.operation_type.value,
                "sub_operation": s.sub_operation,
                "confidence": s.confidence.value,
                "why_selected": s.why_selected,
                "unresolved_data": list(s.unresolved_data),
                "machine_count": len(s.machine_candidates),
                "tool_count": len(s.tool_candidates),
            }
            for s in plan.steps
        ],
        "disclaimer": _DISCLAIMER,
    }


@router.get("/{plan_id}/alternatives")
async def get_alternatives(plan_id: str):
    """List alternative sets for a stored plan."""
    alt_sets = _alt_store.get(plan_id)
    if alt_sets is None:
        raise HTTPException(status_code=404, detail=f"Alternatives for plan '{plan_id}' not found.")
    return {
        "plan_id": plan_id,
        "alternative_sets": [_alt_set_dict(a) for a in alt_sets],
        "disclaimer": _DISCLAIMER,
    }


@router.post("/{plan_id}/select")
async def select_route(plan_id: str, body: SelectRouteBody):
    """Select a specific route for a feature in an existing plan.

    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO — selection does NOT approve the plan.
    """
    plan = _plan_store.get(plan_id)
    alt_sets = _alt_store.get(plan_id)
    if not plan or alt_sets is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    import dataclasses

    updated_sets: list[RouteAlternativeSet] = []
    updated = False
    for alt in alt_sets:
        if alt.feature_id == body.feature_id:
            if not any(c.route_id == body.route_id for c in alt.candidates):
                raise HTTPException(
                    status_code=422,
                    detail=f"Route '{body.route_id}' not found in feature '{body.feature_id}'.",
                )
            updated_sets.append(dataclasses.replace(
                alt,
                selected_route_id=body.route_id,
                selection_rationale=body.rationale or f"Engineer selected {body.route_id}.",
            ))
            updated = True
        else:
            updated_sets.append(alt)

    if not updated:
        raise HTTPException(
            status_code=422,
            detail=f"Feature '{body.feature_id}' not found in plan.",
        )

    _alt_store[plan_id] = updated_sets

    return {
        "plan_id": plan_id,
        "feature_id": body.feature_id,
        "selected_route_id": body.route_id,
        "status": RouteStatus.DRAFT.value,
        "note": "Plan remains DRAFT. AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO.",
    }


@router.post("/{plan_id}/override")
async def apply_override(plan_id: str, body: OverrideBody):
    """Apply an engineer override to a plan's route.

    AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO — override does NOT approve the plan.
    """
    alt_sets = _alt_store.get(plan_id)
    if alt_sets is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found.")

    try:
        override_type = OverrideType(body.override_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown override type '{body.override_type}'.",
        ) from exc

    import uuid

    override = RouteOverride(
        override_id=str(uuid.uuid4())[:8],
        override_type=override_type,
        target_id=body.target_id,
        value=body.value,
        applied_by=body.applied_by,
        note=body.note or "",
    )

    from backend.drawing_intelligence.route_override import RouteOverrideEngine

    engine = RouteOverrideEngine()
    updated_sets: list[RouteAlternativeSet] = []
    for alt in alt_sets:
        if alt.feature_id == body.feature_id:
            updated_sets.append(engine.apply(alt, override))
        else:
            updated_sets.append(alt)

    _alt_store[plan_id] = updated_sets

    return {
        "plan_id": plan_id,
        "feature_id": body.feature_id,
        "override_id": override.override_id,
        "override_type": body.override_type,
        "note": "Plan remains DRAFT. AUTO_SELECTED_ROUTE_MARKED_APPROVED=NO.",
    }
